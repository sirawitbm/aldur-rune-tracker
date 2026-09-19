import queue

from pynput import keyboard

from .config import CONFIG


class HotkeyListener:
    """Global hotkeys that work even while PoE2 has focus.

    Puts an action name ("record" / "undo" / "toggle_visibility") onto the queue for each
    configured hotkey pressed. Supports being rebuilt live (stop old
    listener, start a new one reading current CONFIG values) so Settings
    changes apply without restarting the app.
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
        hide_hotkey = getattr(CONFIG, "hide_hotkey", "<ctrl>+5")
        if hide_hotkey and hide_hotkey not in bindings:
            bindings[hide_hotkey] = lambda: self.action_queue.put("toggle_visibility")

        self._listener = keyboard.GlobalHotKeys(bindings)
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
