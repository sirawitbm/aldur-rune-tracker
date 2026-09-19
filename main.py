import queue
import sys

from PySide6.QtCore import QDir, QLockFile, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication
from PIL import ImageDraw

from src import winutil
from src.capture import capture_around_cursor
from src.config import CONFIG
from src.hotkeys import HotkeyListener
from src.icon_db import ICON_LIBRARY, MATCH_THRESHOLD
from src.log_watcher import AreaEvent, LogWatcher
from src.name_prompt import DisambiguationDialog, NamePromptDialog
from src.overlay import CaptureToast, ControlPanel, HoverInfoPopup, MapChangePopup, RuneListOverlay
from src.recognition_samples import save_recognition_sample
from src.resources import app_icon
from src.rune_vision import crop_detected_icon, detect_passable_rune
from src.settings_dialog import SettingsDialog
from src.tooltip_parse import parse_tooltip
from src.tracker_state import TRACKER
from src.tray import TrayIcon
from src.version import __version__
from src.visibility import WindowVisibilityController, toggle_widget


def identify(result, parsed):
    """Runs the full identification pipeline and registers the result.
    Returns the registered LibraryEntry, or None if the user explicitly
    chose to skip this capture (no confident match, and no name picked)."""

    def finish(name: str, *, trust_visual: bool):
        # Every successful path lands here, so every one of them also feeds
        # the OCR alias learner with whatever OCR guessed on *this* capture
        # - most valuable right after an image-match win (independent
        # ground truth), since that's how a recurring garbled OCR reading
        # gets fixed outright for next time instead of relying on fuzzy
        # matching (or asking again) every single time. See
        # icon_db.learn_ocr_alias.
        #
        # trust_visual gates whether this capture's icon is allowed to
        # shape *future* image matching for `name` (see
        # icon_db.register_capture's docstring for why a text-only
        # resolution must never do this - it's what caused every capture
        # after the first to misidentify as the same rune in the field:
        # one bare OCR/fuzzy guess injected a foreign icon into that
        # rune's history, which then made it an easier catch-all for the
        # *next* capture too, snowballing within a handful of presses).
        if parsed.name:
            ICON_LIBRARY.learn_ocr_alias(parsed.name, name)
        return ICON_LIBRARY.register_capture(name, result.icon, trust_visual=trust_visual)

    # Resolve both independent signals before accepting either one. Any
    # disagreement asks instead of allowing a confident image match to
    # silently override even a fuzzy OCR title match.
    entry = ICON_LIBRARY.find_match(result.icon)
    close_candidates = ICON_LIBRARY.find_close_candidates(result.icon)
    ocr_entry, ocr_confirmed = ICON_LIBRARY.resolve_ocr_guess(parsed.name)

    if entry is not None and ocr_entry is not None and ocr_entry is not entry:
        ocr_label = "exact OCR match" if ocr_confirmed else "fuzzy OCR match"
        options = [(entry, "image match"), (ocr_entry, ocr_label)]
        dlg = DisambiguationDialog(options)
        if dlg.exec() == DisambiguationDialog.Accepted and dlg.value:
            return finish(dlg.value.name, trust_visual=dlg.value is entry)
        entry = None
        ocr_entry = None
        ocr_confirmed = False
    elif entry is not None:
        return finish(entry.name, trust_visual=True)

    if ocr_confirmed:
        return finish(ocr_entry.name, trust_visual=False)

    # 3) Image match found a close call between a couple of visually
    #    similar icons and OCR didn't resolve it outright - one click
    #    settles it instead of guessing or making you navigate the full
    #    33-name list. A fuzzy (non-exact) OCR guess, if there is one and
    #    it's not already among the image candidates, gets folded in as an
    #    extra one-click option too - it's a decent signal on its own, just
    #    not independent/confident enough to auto-accept over an image
    #    ambiguity. Explicitly saying "none of these" means none of them
    #    are right - falls through to the full list below - and critically
    #    does NOT then silently fall back to using that OCR guess anyway,
    #    since it was already offered as a button and declined right along
    #    with the others.
    if close_candidates:
        options = [(entry, f"score {score:.0f}") for entry, score in close_candidates]
        if ocr_entry is not None and not any(entry is ocr_entry for entry, _ in close_candidates):
            options.append((ocr_entry, "OCR guess"))
        dlg = DisambiguationDialog(options)
        if dlg.exec() == DisambiguationDialog.Accepted and dlg.value:
            # Trust the pick only if it was one image matching itself
            # already thought plausible - not the bolted-on "OCR guess"
            # button, which has no image evidence behind it at all.
            picked_from_image = any(dlg.value is c for c, _ in close_candidates)
            return finish(dlg.value.name, trust_visual=picked_from_image)
    elif ocr_entry is not None:  # fuzzy (non-exact) OCR resolution, no image ambiguity to ask about
        return finish(ocr_entry.name, trust_visual=False)

    # 4) Last resort: ask which of the prepared names it is. Surfaces *why*
    #    every prior step failed directly in the dialog, so this can be
    #    diagnosed by reading the popup instead of exchanging screenshots.
    best_entry, best_score = ICON_LIBRARY.best_match_debug(result.icon)
    image_debug = (
        f"closest icon match: '{best_entry.name}' (score {best_score:.0f}, "
        f"needs <={MATCH_THRESHOLD})" if best_entry else "no icons in library yet"
    )
    ocr_debug = f"OCR saw: {parsed.raw_lines}" if parsed.raw_lines else "OCR saw no text at all"
    debug_text = f"{image_debug}\n{ocr_debug}"

    prompt = NamePromptDialog(ICON_LIBRARY.names(), suggested_name=parsed.name, debug_text=debug_text)
    if prompt.exec() != NamePromptDialog.Accepted or not prompt.value:
        return None
    return finish(prompt.value, trust_visual=False)


def main():
    winutil.enable_dpi_awareness()

    app = QApplication(sys.argv)
    app.setApplicationName("PoE2 Rune Tracker")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)

    instance_lock = QLockFile(QDir.temp().filePath("aldur-rune-tracker.lock"))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(100):
        return

    list_overlay = RuneListOverlay()
    control_panel = ControlPanel()
    map_popup = MapChangePopup(timeout_sec=12)
    hover_popup = HoverInfoPopup()
    capture_toast = CaptureToast()
    tray = TrayIcon()

    list_overlay.show()
    control_panel.show()
    tray.show()
    list_overlay.refresh()
    list_overlay.place_below(control_panel)
    visibility = WindowVisibilityController(app.topLevelWidgets)

    action_queue: "queue.Queue[str]" = queue.Queue()
    area_queue: "queue.Queue[AreaEvent]" = queue.Queue()
    capture_in_progress = False

    hotkeys = HotkeyListener(action_queue)
    log_watcher = LogWatcher(area_queue)

    control_panel.set_status(log_watcher.status)

    def do_reset(new_area_name: str | None = None):
        TRACKER.reset(new_area_name)
        list_overlay.refresh()

    def on_record():
        result = capture_around_cursor()
        # Always dump the last capture to disk (overwritten each press) so
        # mismatches between the capture box and the actual tooltip
        # position can be diagnosed by just opening the PNG, instead of
        # guessing at capture_offset_x/y blind.
        result.image.save(CONFIG.data_dir / "last_capture_debug.png")

        cursor_in_image = (result.cursor_x - result.box[0], result.cursor_y - result.box[1])
        visual = detect_passable_rune(result.image, cursor_in_image, CONFIG.icon_crop_size)
        parsed = parse_tooltip(result.image)
        if not parsed.has_passable_text:
            save_recognition_sample(
                result,
                visual,
                resolved_name=None,
                outcome="not_passable",
                parsed_name=parsed.name,
                has_passable_text=parsed.has_passable_text,
                raw_ocr_lines=parsed.raw_lines,
            )
            control_panel.set_status("This rune is not marked passable - nothing was tracked.")
            capture_toast.show_message(
                "NOT PASSABLE",
                warning=True,
                cursor_pos=(result.cursor_x, result.cursor_y),
            )
            return

        if visual is not None:
            result.icon = crop_detected_icon(result.image, visual)
        result.icon.save(CONFIG.data_dir / "last_capture_icon_debug.png")
        if visual is not None:
            detection_debug = result.image.copy()
            debug_draw = ImageDraw.Draw(detection_debug)
            debug_draw.rectangle(visual.marker_box, outline=(255, 220, 0), width=3)
            debug_draw.rectangle(visual.icon_box, outline=(0, 220, 255), width=3)
            detection_debug.save(CONFIG.data_dir / "last_detection_debug.png")

        entry = identify(result, parsed)
        if entry is None:
            save_recognition_sample(
                result,
                visual,
                resolved_name=None,
                outcome="unrecognized",
                parsed_name=parsed.name,
                has_passable_text=parsed.has_passable_text,
                raw_ocr_lines=parsed.raw_lines,
            )
            control_panel.set_status(
                "Capture skipped - unrecognized icon and no name picked "
                "(see data/last_capture_debug.png)."
            )
            return

        tracked = TRACKER.add_passable(entry.name, entry.load_icon())
        save_recognition_sample(
            result,
            visual,
            resolved_name=entry.name,
            outcome="added" if tracked.added else "duplicate",
            parsed_name=parsed.name,
            has_passable_text=parsed.has_passable_text,
            raw_ocr_lines=parsed.raw_lines,
        )
        list_overlay.refresh()

        cursor_pos = (result.cursor_x, result.cursor_y)
        if tracked.added:
            control_panel.set_status(f"Captured '{entry.name}' - passable confirmed by tooltip text.")
            capture_toast.show_message(entry.name, cursor_pos=cursor_pos)
        else:
            control_panel.set_status(f"'{entry.name}' is already in the passed-rune set.")
            capture_toast.show_message(f"{entry.name} - ALREADY TRACKED", warning=True, cursor_pos=cursor_pos)

    def on_discard(icon_file: str):
        TRACKER.remove(icon_file)
        list_overlay.refresh()

    def on_undo():
        undone = TRACKER.undo_last()
        list_overlay.refresh()
        if undone is None:
            control_panel.set_status("Nothing to undo.")
        else:
            control_panel.set_status(f"Undid '{undone.name}'.")

    def on_area_event(evt: AreaEvent):
        if evt.is_hideout:
            return
        if evt.likely_map and not visibility.hidden:
            map_popup.announce(evt.area_name)

    def open_settings():
        dialog = SettingsDialog()
        if dialog.exec() == SettingsDialog.Accepted:
            dialog.apply_to_config()
            hotkeys.rebuild()
            log_watcher.restart()
            control_panel.set_status(log_watcher.status)
            list_overlay.refresh()

    control_panel.reset_clicked.connect(lambda: do_reset(None))
    control_panel.lock_toggled.connect(list_overlay.set_locked)
    list_overlay.discard_requested.connect(on_discard)
    map_popup.reset_clicked.connect(lambda: do_reset(map_popup.label.text()))

    tray.settings_requested.connect(open_settings)
    tray.reset_requested.connect(lambda: do_reset(None))
    tray.undo_requested.connect(on_undo)
    tray.quit_requested.connect(app.quit)

    def run_record_delayed():
        nonlocal capture_in_progress
        if visibility.hidden:
            return
        if capture_in_progress:
            control_panel.set_status("Finish the current rune prompt before capturing again.")
            return
        capture_in_progress = True
        try:
            on_record()
        except Exception as exc:  # noqa: BLE001 - surface it, never fail silently
            control_panel.set_status(f"Error handling 'record': {exc}")
        finally:
            capture_in_progress = False

    def poll_queues():
        try:
            while True:
                action = action_queue.get_nowait()
                try:
                    if action == "record":
                        if visibility.hidden:
                            continue
                        # Games commonly have a short hover delay before a
                        # tooltip actually updates to the newly-hovered
                        # target - capturing instantly on keypress can catch
                        # the *previous* tooltip still on screen (icon looks
                        # right, OCR reads stale text), which shows up as
                        # "it thinks this is the same rune as last time"
                        # even though you moved to a new one. A short delay
                        # gives the game time to catch up before the grab.
                        QTimer.singleShot(CONFIG.capture_delay_ms, run_record_delayed)
                    elif action == "undo":
                        if not visibility.hidden:
                            on_undo()
                    elif action == "reset":
                        do_reset(None)
                    elif action == "toggle_visibility":
                        hover_popup.hide_popup()
                        visibility.toggle()
                    elif action == "toggle_control_panel":
                        if not visibility.hidden:
                            toggle_widget(control_panel)
                except Exception as exc:  # noqa: BLE001 - surface it, never fail silently
                    control_panel.set_status(f"Error handling '{action}': {exc}")
        except queue.Empty:
            pass

        try:
            while True:
                evt = area_queue.get_nowait()
                on_area_event(evt)
        except queue.Empty:
            pass

    def poll_hover():
        if visibility.hidden:
            hover_popup.hide_popup()
            return
        pos = QCursor.pos()
        entry = list_overlay.hit_test(pos)
        if entry is None:
            hover_popup.hide_popup()
        else:
            hover_popup.show_near(entry, pos)

    timer = QTimer()
    timer.timeout.connect(poll_queues)
    timer.start(100)

    hover_timer = QTimer()
    hover_timer.timeout.connect(poll_hover)
    hover_timer.start(120)

    hotkeys.start()
    log_watcher.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
