import json
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Running as a PyInstaller .exe - keep config.json/data/ next to the
    # executable, not buried inside the bundle's internal temp/data dir.
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent

CONFIG_PATH = ROOT / "config.json"

DEFAULT_CONFIG = {
    "record_hotkey": "<ctrl>+3",
    "undo_hotkey": "<ctrl>+4",
    "reset_hotkey": "<ctrl>+<shift>+4",
    "hide_hotkey": "<ctrl>+5",
    "panel_hotkey": "<ctrl>+<shift>+5",
    "capture_delay_ms": 150,
    "capture_width": 900,
    "capture_height": 700,
    "capture_offset_x": 0,
    "capture_offset_y": 0,
    "icon_crop_size": 60,
    "overlay_icon_size": 36,
    "toast_position": "cursor",
    "collect_recognition_samples": False,
    "ocr_lang": "en",
    "data_dir": "data",
}

_REMOVED_CONFIG_KEYS = (
    "client_log_path",
    "log_poll_interval_sec",
    "map_popup_timeout_sec",
)


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self._path = path
        if not path.exists():
            path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        self._data = json.loads(path.read_text(encoding="utf-8"))
        removed_old_setting = False
        for key in _REMOVED_CONFIG_KEYS:
            if key in self._data:
                del self._data[key]
                removed_old_setting = True
        if removed_old_setting:
            self.save()

    def __getattr__(self, item):
        try:
            return self._data[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def set(self, key: str, value):
        self._data[key] = value

    def save(self):
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    @property
    def data_dir(self) -> Path:
        d = ROOT / self._data["data_dir"]
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def session_path(self) -> Path:
        return self.data_dir / "session.json"

    @property
    def history_path(self) -> Path:
        return self.data_dir / "history.jsonl"

    @property
    def captured_icons_dir(self) -> Path:
        d = self.data_dir / "captured_icons"
        d.mkdir(parents=True, exist_ok=True)
        return d


CONFIG = Config()
