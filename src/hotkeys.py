import queue

from pynput import keyboard

from .config import CONFIG


class HotkeyListener:
    """Global hotkeys that work even while PoE2 has focus.

    Puts an action name onto the queue for each configured hotkey pressed.
    Supports being rebuilt live so Settings changes apply without restarting.
    """

    def __init__(self, action_queue: "queue.Queue[str]"):
        self.action_queue = action_queue
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self):
        self._rebuild()

    def rebuild(self):
        """Call after CONFIG.record_hotkey/undo_hotkey changes to apply live."""
        self._rebuild()

    def _rebuild(self):
        if self._listener is not None:
            self._listener.stop()

        bindings = {
            CONFIG.record_hotkey: lambda: self.action_queue.put("record"),
        }
        undo_hotkey = getattr(CONFIG, "undo_hotkey", None)
        if undo_hotkey and undo_hotkey != CONFIG.record_hotkey:
            bindings[undo_hotkey] = lambda: self.action_queue.put("undo")
        reset_hotkey = getattr(CONFIG, "reset_hotkey", "<ctrl>+<shift>+4")
        if reset_hotkey and reset_hotkey not in bindings:
            bindings[reset_hotkey] = lambda: self.action_queue.put("reset")
        hide_hotkey = getattr(CONFIG, "hide_hotkey", "<ctrl>+5")
        if hide_hotkey and hide_hotkey not in bindings:
            bindings[hide_hotkey] = lambda: self.action_queue.put("toggle_visibility")
        panel_hotkey = getattr(CONFIG, "panel_hotkey", "<ctrl>+<shift>+5")
        if panel_hotkey and panel_hotkey not in bindings:
            bindings[panel_hotkey] = lambda: self.action_queue.put("toggle_control_panel")

        self._listener = keyboard.GlobalHotKeys(bindings)
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
