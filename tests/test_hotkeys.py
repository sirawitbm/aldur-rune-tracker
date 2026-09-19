import queue
import unittest
from unittest.mock import patch

from src.hotkeys import HotkeyListener


class _Config:
    record_hotkey = "<ctrl>+3"
    undo_hotkey = "<ctrl>+4"
    hide_hotkey = "<ctrl>+5"


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


if __name__ == "__main__":
    unittest.main()