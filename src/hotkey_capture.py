"""A button that captures a single keypress and turns it into a pynput
hotkey string (e.g. "<f9>", "<ctrl>+<f9>", "a"), for live-editable settings.

pynput's format is different from Qt's QKeySequence format, so this maps
Qt key events directly rather than going through QKeySequenceEdit.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

_SPECIAL_KEYS = {
    Qt.Key_F1: "f1", Qt.Key_F2: "f2", Qt.Key_F3: "f3", Qt.Key_F4: "f4",
    Qt.Key_F5: "f5", Qt.Key_F6: "f6", Qt.Key_F7: "f7", Qt.Key_F8: "f8",
    Qt.Key_F9: "f9", Qt.Key_F10: "f10", Qt.Key_F11: "f11", Qt.Key_F12: "f12",
    Qt.Key_F13: "f13", Qt.Key_F14: "f14", Qt.Key_F15: "f15", Qt.Key_F16: "f16",
    Qt.Key_Space: "space", Qt.Key_Escape: "esc", Qt.Key_Tab: "tab",
    Qt.Key_Backspace: "backspace", Qt.Key_Return: "enter", Qt.Key_Enter: "enter",
    Qt.Key_Delete: "delete", Qt.Key_Insert: "insert",
    Qt.Key_Home: "home", Qt.Key_End: "end",
    Qt.Key_PageUp: "page_up", Qt.Key_PageDown: "page_down",
    Qt.Key_Up: "up", Qt.Key_Down: "down", Qt.Key_Left: "left", Qt.Key_Right: "right",
    Qt.Key_CapsLock: "caps_lock", Qt.Key_Print: "print_screen", Qt.Key_Pause: "pause",
}

_MODIFIER_ONLY_KEYS = {
    Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta,
    Qt.Key_AltGr, Qt.Key_Super_L, Qt.Key_Super_R,
}


def qevent_to_pynput_string(event) -> str | None:
    key = event.key()
    if key in _MODIFIER_ONLY_KEYS:
        return None  # wait for a real key

    parts = []
    mods = event.modifiers()
    if mods & Qt.ControlModifier:
        parts.append("<ctrl>")
    if mods & Qt.AltModifier:
        parts.append("<alt>")
    if mods & Qt.ShiftModifier:
        parts.append("<shift>")

    if key in _SPECIAL_KEYS:
        parts.append(f"<{_SPECIAL_KEYS[key]}>")
    else:
        text = event.text()
        if text and text.isprintable():
            parts.append(text.lower())
        else:
            return None

    return "+".join(parts)


class HotkeyCaptureButton(QPushButton):
    """Click, then press the key combo you want. Click again to change it."""

    def __init__(self, initial_hotkey: str, parent=None):
        super().__init__(parent)
        self._value = initial_hotkey
        self._listening = False
        self._update_text()
        self.clicked.connect(self._start_listening)
        self.setStyleSheet(
            "QPushButton { background: rgba(40,40,40,220); color: white;"
            " border: 1px solid #555; border-radius: 4px; padding: 4px; }"
            "QPushButton:hover { background: rgba(60,60,60,230); }"
        )

    @property
    def value(self) -> str:
        return self._value

    def _update_text(self):
        self.setText(f"Hotkey: {self._value}" if not self._listening else "Press a key...")

    def _start_listening(self):
        self._listening = True
        self._update_text()
        self.setFocus(Qt.OtherFocusReason)
        self.grabKeyboard()

    def keyPressEvent(self, event):
        if not self._listening:
            super().keyPressEvent(event)
            return
        hotkey = qevent_to_pynput_string(event)
        if hotkey is None:
            return  # modifier-only press, keep waiting
        self._value = hotkey
        self._listening = False
        self.releaseKeyboard()
        self._update_text()

    def focusOutEvent(self, event):
        if self._listening:
            self._listening = False
            self.releaseKeyboard()
            self._update_text()
        super().focusOutEvent(event)
