import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src.tracker_state import TrackerState


class _TestConfig:
    def __init__(self, root: Path):
        self.data_dir = root
        self.session_path = root / "session.json"
        self.history_path = root / "history.jsonl"
        self.captured_icons_dir = root / "captured_icons"
        self.captured_icons_dir.mkdir()


class TrackerStateTests(unittest.TestCase):
    def test_duplicate_passable_rune_is_not_added_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            config = _TestConfig(Path(directory))
            with patch("src.tracker_state.CONFIG", config):
                tracker = TrackerState()
                icon = Image.new("RGB", (12, 12), "red")

                first = tracker.add_passable("Fire Rune", icon)
                duplicate = tracker.add_passable("fire rune", icon)

                self.assertTrue(first.added)
                self.assertFalse(duplicate.added)
                self.assertEqual(tracker.total(), 1)
                self.assertEqual(len(list(config.captured_icons_dir.iterdir())), 1)

    def test_undo_removes_last_unique_rune(self):
        with tempfile.TemporaryDirectory() as directory:
            config = _TestConfig(Path(directory))
            with patch("src.tracker_state.CONFIG", config):
                tracker = TrackerState()
                icon = Image.new("RGB", (12, 12), "red")
                tracker.add_passable("Fire Rune", icon)
                tracker.add_passable("Cold Rune", icon)

                undone = tracker.undo_last()

                self.assertEqual(undone.name, "Cold Rune")
                self.assertEqual([entry.name for entry in tracker.entries], ["Fire Rune"])

    def test_load_migrates_to_unique_passable_runes(self):
        with tempfile.TemporaryDirectory() as directory:
            config = _TestConfig(Path(directory))
            config.session_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {"ts": 1, "name": "Fire Rune", "is_passable": False, "icon_file": "old.png"},
                            {"ts": 2, "name": "Cold Rune", "is_passable": True, "icon_file": "cold.png"},
                            {"ts": 3, "name": "cold rune", "is_passable": True, "icon_file": "duplicate.png"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch("src.tracker_state.CONFIG", config):
                tracker = TrackerState()

            self.assertEqual([entry.name for entry in tracker.entries], ["Cold Rune"])

    def test_remove_discards_only_selected_rune_and_its_icon(self):
        with tempfile.TemporaryDirectory() as directory:
            config = _TestConfig(Path(directory))
            with patch("src.tracker_state.CONFIG", config):
                tracker = TrackerState()
                icon = Image.new("RGB", (12, 12), "red")
                fire = tracker.add_passable("Fire Rune", icon).entry
                tracker.add_passable("Cold Rune", icon)

                tracker.remove(fire.icon_file)

                self.assertEqual([entry.name for entry in tracker.entries], ["Cold Rune"])
                self.assertFalse((config.data_dir / fire.icon_file).exists())


if __name__ == "__main__":
    unittest.main()