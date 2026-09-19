import json
import tempfile
import unittest
from pathlib import Path

from src.config import Config, DEFAULT_CONFIG


class ConfigTests(unittest.TestCase):
    def test_removes_obsolete_log_watcher_settings(self):
        old_config = dict(DEFAULT_CONFIG)
        old_config.update({
            "client_log_path": r"C:\Games\Path of Exile 2\logs\Client.txt",
            "log_poll_interval_sec": 0.5,
            "map_popup_timeout_sec": 12,
        })

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(json.dumps(old_config), encoding="utf-8")

            config = Config(path)
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(config.record_hotkey, DEFAULT_CONFIG["record_hotkey"])
        self.assertNotIn("client_log_path", saved)
        self.assertNotIn("log_poll_interval_sec", saved)
        self.assertNotIn("map_popup_timeout_sec", saved)


if __name__ == "__main__":
    unittest.main()