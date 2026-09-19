import queue
import unittest
from unittest.mock import patch

from src.hotkeys import HotkeyListener


class _Config:
    record_hotkey = "<ctrl>+3"
    undo_hotkey = "<ctrl>+4"
    reset_hotkey = "<ctrl>+<shift>+4"
    hide_hotkey = "<ctrl>+5"
    panel_hotkey = "<ctrl>+<shift>+5"


class _GlobalHotKeys:
    def __init__(self, bindings):
        self.bindings = bindings

    def start(self):
        pass

    def stop(self):
        pass


class HotkeyListenerTests(unittest.TestCase):
    def test_visibility_hotkey_queues_toggle_action(self):
        actions = queue.Queue()
        with patch("src.hotkeys.CONFIG", _Config), patch(
            "src.hotkeys.keyboard.GlobalHotKeys", _GlobalHotKeys
        ):
            listener = HotkeyListener(actions)
            listener.start()
            listener._listener.bindings["<ctrl>+5"]()

        self.assertEqual(actions.get_nowait(), "toggle_visibility")

    def test_reset_and_panel_hotkeys_queue_actions(self):
        actions = queue.Queue()
        with patch("src.hotkeys.CONFIG", _Config), patch(
            "src.hotkeys.keyboard.GlobalHotKeys", _GlobalHotKeys
        ):
            listener = HotkeyListener(actions)
            listener.start()
            listener._listener.bindings["<ctrl>+<shift>+4"]()
            listener._listener.bindings["<ctrl>+<shift>+5"]()

        self.assertEqual(actions.get_nowait(), "reset")
        self.assertEqual(actions.get_nowait(), "toggle_control_panel")


if __name__ == "__main__":
    unittest.main()