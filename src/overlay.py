import math

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import positions, winutil
from .config import CONFIG
from .icon_db import ICON_LIBRARY
from .tracker_state import TRACKER

ROW_STYLE = """
QLabel#warn { color: #ff5c5c; font-size: 16px; font-weight: bold; }
"""


def _grid_shape(entry_count: int, available_height: int, row_height: int) -> tuple[int, int]:
    if entry_count <= 0:
        return 0, 0
    max_rows = max(1, available_height // row_height)
    rows = min(entry_count, max_rows)
    return rows, math.ceil(entry_count / rows)


def _frameless_overlay_flags():
    return (
        Qt.FramelessWindowHint
        | Qt.WindowStaysOnTopHint
        | Qt.Tool
        | Qt.WindowDoesNotAcceptFocus
        | Qt.NoDropShadowWindowHint
    )


class _DragHelper:
    """Click-and-drag-to-move for a frameless window, with position persistence.

    Composition instead of a QWidget mixin - PySide6 widgets don't play well
    with extra multiple-inheritance bases.
    """

    def __init__(self, widget: QWidget, position_key: str, enabled_fn=lambda: True):
        self._widget = widget
        self._key = position_key
        self._enabled_fn = enabled_fn
        self._offset = None

    def press(self, event) -> bool:
        if not self._enabled_fn() or event.button() != Qt.LeftButton:
            return False
        self._offset = event.globalPosition().toPoint() - self._widget.pos()
        return True

    def move(self, event) -> bool:
        if self._offset is None or not (event.buttons() & Qt.LeftButton):
            return False
        self._widget.move(event.globalPosition().toPoint() - self._offset)
        return True

    def release(self, event) -> bool:
        if self._offset is None:
            return False
        self._offset = None
        pos = self._widget.pos()
        positions.save_position(self._key, pos.x(), pos.y())
        return True


class RuneListOverlay(QWidget):
    """Click-through vertical list, docked to the right edge of the screen.

    The discard ("x") buttons only receive clicks while unlocked (same
    toggle used for dragging) - while locked the window is click-through
    so gameplay clicks pass through it, which necessarily means our own
    buttons can't receive clicks either.
    """

    discard_requested = Signal(str)  # icon_file of the entry to remove

    def __init__(self):
        super().__init__()
        self.setWindowFlags(_frameless_overlay_flags())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(ROW_STYLE)

        self._locked = True
        self._auto_position = positions.get_position("list_overlay") is None
        self._default_top = 140
        self._drag = _DragHelper(self, "list_overlay", enabled_fn=lambda: not self._locked)
        self._hover_targets: list[tuple[QWidget, object]] = []  # (row_widget, RecordedRune)

        self.title = QLabel("Passed Runes")
        self.title.setWordWrap(True)
        self.title.setAlignment(Qt.AlignRight)
        self.title.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.rows_layout = QGridLayout()
        self.rows_layout.setSpacing(2)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)
        outer.addWidget(self.title)
        outer.addLayout(self.rows_layout)
        outer.addStretch()

        self._apply_title_style()
        self.resize(110, 640)
        saved = positions.get_position("list_overlay")
        if saved:
            self.move(*saved)
        else:
            self._position()

    def _position(self):
        screen = QGuiApplication.primaryScreen().geometry()
        x = screen.right() - self.width() - 10
        y = self._default_top
        self.move(x, y)

    def place_below(self, widget: QWidget):
        if not self._auto_position:
            return
        self._default_top = widget.geometry().bottom() + 8
        self._position()

    def _apply_title_style(self):
        if self._locked:
            self.title.setText("Passed Runes")
            self.title.setStyleSheet(
                "color: white; font-size: 14px; font-weight: bold;"
                "background: rgba(20,20,20,180); padding: 4px 8px; border-radius: 4px;"
            )
            self.title.setVisible(TRACKER.total() > 0)
        else:
            self.title.setText("Drag to move - click 'Lock position' when done")
            self.title.setStyleSheet(
                "color: black; font-size: 13px; font-weight: bold;"
                "background: rgba(255,180,40,230); padding: 4px 8px; border-radius: 4px;"
            )
            self.title.setVisible(True)

    def set_locked(self, locked: bool):
        self._locked = locked
        winutil.make_click_through(int(self.winId()), locked)
        self._apply_title_style()
        self.refresh()

    def mousePressEvent(self, event):
        if self._drag.press(event):
            self._auto_position = False
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._drag.move(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self._drag.release(event):
            super().mouseReleaseEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        winutil.make_click_through(int(self.winId()), self._locked)

    def refresh(self):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._hover_targets = []

        entries = TRACKER.entries
        if self._locked:
            self.title.setVisible(len(entries) > 0)

        if not entries:
            self.hide()
            return
        if not self.isVisible():
            self.show()

        visible_entries = entries
        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        available_height = max(1, screen.availableGeometry().bottom() - self.y() - 48)
        row_height = CONFIG.overlay_icon_size + 8
        max_rows, _columns = _grid_shape(len(visible_entries), available_height, row_height)

        for index, entry in enumerate(visible_entries):
            # Compact by default (icon only) since a chain can stack 9+
            # entries - full name/effect text shows up in a hover popup
            # (see HoverInfoPopup / hit_test) instead of taking up
            # permanent space. Native QToolTip can't be used here: this
            # window is click-through while locked, and a click-through
            # window never receives the mouse-move/hover events Qt's
            # tooltip mechanism needs - so hovering is instead detected by
            # polling the global cursor position against these rows'
            # geometry (works regardless of click-through state).
            row = QWidget()
            row.setFixedSize(154, row_height)
            row.setStyleSheet("background: rgba(20,20,20,150); border-radius: 4px;")
            h = QHBoxLayout(row)
            h.setContentsMargins(4, 2, 4, 2)
            h.setSpacing(4)

            name_label = QLabel(entry.name.removesuffix(" Rune"))
            name_label.setStyleSheet("color: white; font-size: 11px;")
            name_label.setFixedWidth(72)
            name_label.setToolTip(entry.name)
            h.addWidget(name_label)

            discard_btn = QPushButton("x")
            discard_btn.setFixedSize(18, 18)
            discard_btn.setToolTip("Untrack this capture")
            discard_btn.setVisible(not self._locked)
            discard_btn.setStyleSheet(
                "QPushButton { color: #ff8080; background: rgba(60,20,20,180); border: none;"
                " border-radius: 9px; font-weight: bold; font-size: 11px; padding: 0px; }"
                "QPushButton:hover { background: rgba(120,30,30,220); }"
            )
            discard_btn.clicked.connect(lambda _checked=False, key=entry.icon_file: self.discard_requested.emit(key))
            h.addWidget(discard_btn)

            icon_label = QLabel()
            pm = QPixmap(str(CONFIG.data_dir / entry.icon_file))
            if not pm.isNull():
                size = CONFIG.overlay_icon_size
                icon_label.setPixmap(pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            h.addWidget(icon_label)

            grid_row = index % max_rows
            grid_column = index // max_rows
            self.rows_layout.addWidget(row, grid_row, grid_column)
            self._hover_targets.append((row, entry))

        self.title.setText(f"Passed Runes ({len(entries)})")
        self.adjustSize()
        if self._auto_position:
            self._position()
        self._keep_on_screen()

    def _keep_on_screen(self):
        screen = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        bounds = screen.availableGeometry()
        x = min(max(self.x(), bounds.left()), bounds.right() - self.width() + 1)
        y = min(max(self.y(), bounds.top()), bounds.bottom() - self.height() + 1)
        self.move(x, y)

    def hit_test(self, global_pos: QPoint):
        """Returns the RecordedRune whose row is under global_pos, or None."""
        for row, entry in self._hover_targets:
            top_left = self.pos() + row.pos()
            rect = row.rect().translated(top_left)
            if rect.contains(global_pos):
                return entry
        return None


class ControlPanel(QWidget):
    """Small always-visible panel: manual reset, overlay lock toggle, status.

    Always draggable (grab any empty space in the panel) since it's never
    click-through to begin with.
    """

    reset_clicked = Signal()
    lock_toggled = Signal(bool)  # new locked state

    def __init__(self):
        super().__init__()
        self.setWindowFlags(_frameless_overlay_flags())
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._drag = _DragHelper(self, "control_panel")
        self._locked = True

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #bbbbbb; font-size: 10px;")
        self.status_label.setWordWrap(True)
        self.status_label.setFixedWidth(200)

        reset_btn = QPushButton("Reset tracker")
        reset_btn.setStyleSheet(
            "QPushButton { background: rgba(120,20,20,220); color: white; border-radius: 4px; padding: 4px; }"
            "QPushButton:hover { background: rgba(160,30,30,230); }"
        )
        reset_btn.clicked.connect(self.reset_clicked.emit)

        self.lock_btn = QPushButton("Unlock rune list to move it")
        self.lock_btn.setStyleSheet(
            "QPushButton { background: rgba(40,60,100,220); color: white; border-radius: 4px; padding: 4px; }"
            "QPushButton:hover { background: rgba(60,90,140,230); }"
        )
        self.lock_btn.clicked.connect(self._on_toggle_lock)

        container = QWidget()
        container.setStyleSheet("background: rgba(15,15,15,200); border-radius: 6px;")
        inner = QVBoxLayout(container)
        inner.setContentsMargins(8, 8, 8, 8)
        inner.setSpacing(4)
        inner.addWidget(reset_btn)
        inner.addWidget(self.lock_btn)
        inner.addWidget(self.status_label)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        self.resize(220, 100)
        saved = positions.get_position("control_panel")
        if saved:
            self.move(*saved)
        else:
            self._position()

    def _position(self):
        screen = QGuiApplication.primaryScreen().geometry()
        x = screen.right() - self.width() - 10
        y = screen.top() + 10
        self.move(x, y)

    def _on_toggle_lock(self):
        self._locked = not self._locked
        self.lock_btn.setText(
            "Unlock rune list to move it" if self._locked else "Lock rune list in place"
        )
        self.lock_toggled.emit(self._locked)

    def showEvent(self, event):
        super().showEvent(event)
        winutil.make_noactivate_tool_window(int(self.winId()))

    def set_status(self, text: str):
        self.status_label.setText(text)

    def mousePressEvent(self, event):
        if not self._drag.press(event):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._drag.move(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self._drag.release(event):
            super().mouseReleaseEvent(event)


class HoverInfoPopup(QWidget):
    """Floating name+effects panel shown near the cursor while it's over a
    tracked rune's icon (driven by polling QCursor.pos() against
    RuneListOverlay.hit_test - see the note in RuneListOverlay.refresh()
    for why native hover/tooltip events don't work here).
    """

    def __init__(self):
        super().__init__()
        self.setWindowFlags(_frameless_overlay_flags())
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.label = QLabel("")
        self.label.setStyleSheet(
            "color: white; font-size: 12px; background: rgba(15,15,15,235);"
            "padding: 6px 10px; border-radius: 6px;"
        )
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

        self._shown_for = None  # currently-displayed entry, to avoid flicker on re-show
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        winutil.make_click_through(int(self.winId()), True)

    def show_near(self, entry, anchor_global_pos: QPoint):
        if entry is self._shown_for:
            return
        self._shown_for = entry
        # Effect text comes from the database (by name), never from OCR -
        # `entry` here is just the tracked capture record (name + when).
        db_entry = ICON_LIBRARY.find_by_name(entry.name) if entry.name else None
        if db_entry and db_entry.mods:
            body = "<br>".join(db_entry.mods)
            self.label.setText(f"<b>{entry.name}</b><br>{body}")
        else:
            self.label.setText(f"<b>{entry.name or '(unreadable)'}</b>")
        self.adjustSize()

        screen = QGuiApplication.primaryScreen().geometry()
        x = anchor_global_pos.x() - self.width() - 16
        if x < screen.left():
            x = anchor_global_pos.x() + 16
        y = min(anchor_global_pos.y(), screen.bottom() - self.height())
        self.move(x, y)
        self.show()
        self.raise_()

    def hide_popup(self):
        if self._shown_for is not None:
            self._shown_for = None
            self.hide()


class CaptureToast(QWidget):
    """Brief confirmation of what a capture was just identified as, so you
    can glance at it to confirm without checking the tracked-runes column
    or the control panel status line. Purely informational - click-through,
    no buttons, auto-dismisses. Positioned per CONFIG.toast_position:
    "cursor" (default - right where you were already looking, next to the
    tooltip you just hovered) or "bottom"/"top"/"center" of the screen."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(_frameless_overlay_flags())
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        winutil.make_click_through(int(self.winId()), True)

    def show_message(
        self,
        text: str,
        warning: bool = False,
        duration_ms: int = 2800,
        cursor_pos: tuple[int, int] | None = None,
    ):
        color = "#ff6b6b" if warning else "#ffffff"
        self.label.setText(text)
        self.label.setStyleSheet(
            f"color: {color}; font-size: 20px; font-weight: bold;"
            "background: rgba(15,15,15,225); padding: 12px 24px; border-radius: 10px;"
        )
        self.adjustSize()
        self._position(cursor_pos)
        self.show()
        self.raise_()
        self._timer.start(duration_ms)

    def _position(self, cursor_pos: tuple[int, int] | None):
        screen = QGuiApplication.primaryScreen().geometry()
        mode = getattr(CONFIG, "toast_position", "cursor")

        if mode == "cursor" and cursor_pos is not None:
            cx, cy = cursor_pos
            x = cx - self.width() // 2
            y = cy + 40  # below the cursor, clear of the tooltip/icon itself
            x = max(screen.left() + 10, min(x, screen.right() - self.width() - 10))
            y = min(y, screen.bottom() - self.height() - 10)
        elif mode == "top":
            x = screen.center().x() - self.width() // 2
            y = screen.top() + 70
        elif mode == "center":
            x = screen.center().x() - self.width() // 2
            y = screen.center().y() - self.height() // 2
        else:  # "bottom" (also the fallback if mode == "cursor" but no position was given)
            x = screen.center().x() - self.width() // 2
            y = screen.bottom() - self.height() - 70

        self.move(x, y)
