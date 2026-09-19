import json
import time
import uuid
from dataclasses import asdict, dataclass, fields

from PIL import Image

from .config import CONFIG


@dataclass
class RecordedRune:
    ts: float
    name: str
    is_passable: bool
    icon_file: str  # relative to data_dir


@dataclass(frozen=True)
class TrackResult:
    entry: RecordedRune
    added: bool


class TrackerState:
    def __init__(self):
        self.entries: list[RecordedRune] = []
        self.map_area_name: str | None = None
        self.map_started_at: float = time.time()
        self._load_session()

    # -- mutation -----------------------------------------------------
    def add_passable(self, name: str, icon: Image.Image) -> TrackResult:
        existing = next((entry for entry in self.entries if entry.name.lower() == name.lower()), None)
        if existing is not None:
            return TrackResult(existing, added=False)

        CONFIG.captured_icons_dir  # ensures the folder exists before writing into it
        icon_filename = f"captured_icons/{uuid.uuid4().hex}.png"
        icon.save(CONFIG.data_dir / icon_filename)

        entry = RecordedRune(
            ts=time.time(),
            name=name,
            is_passable=True,
            icon_file=icon_filename,
        )
        self.entries.append(entry)
        self._save_session()
        return TrackResult(entry, added=True)

    def remove(self, icon_file: str):
        """Discard a single captured entry (identified by its unique icon file)."""
        self.entries = [e for e in self.entries if e.icon_file != icon_file]
        self._save_session()
        self._delete_icon_file(icon_file)

    def undo_last(self) -> RecordedRune | None:
        """Discard the most recently added entry. Returns it, or None if empty."""
        if not self.entries:
            return None
        entry = self.entries.pop()
        self._save_session()
        self._delete_icon_file(entry.icon_file)
        return entry

    @staticmethod
    def _delete_icon_file(icon_file: str):
        try:
            (CONFIG.data_dir / icon_file).unlink(missing_ok=True)
        except OSError:
            pass

    def reset(self, new_area_name: str | None = None):
        if self.entries:
            self._append_history()
        self.entries = []
        self.map_area_name = new_area_name
        self.map_started_at = time.time()
        self._save_session()

    # -- queries --------------------------------------------------------
    def passable_count(self) -> int:
        return sum(1 for e in self.entries if e.is_passable)

    def total(self) -> int:
        return len(self.entries)

    # -- persistence ------------------------------------------------------
    def _save_session(self):
        data = {
            "map_area_name": self.map_area_name,
            "map_started_at": self.map_started_at,
            "entries": [asdict(e) for e in self.entries],
        }
        temporary_path = CONFIG.session_path.with_suffix(".json.tmp")
        temporary_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temporary_path.replace(CONFIG.session_path)

    def _load_session(self):
        if not CONFIG.session_path.exists():
            return
        try:
            data = json.loads(CONFIG.session_path.read_text(encoding="utf-8"))
            self.map_area_name = data.get("map_area_name")
            self.map_started_at = data.get("map_started_at", time.time())
            # Tolerate old session files with now-removed fields (e.g. a
            # dropped "description" column) instead of crashing on load.
            valid_keys = {f.name for f in fields(RecordedRune)}
            loaded = [
                RecordedRune(**{k: v for k, v in e.items() if k in valid_keys})
                for e in data.get("entries", [])
            ]
            seen_names = set()
            self.entries = []
            for entry in loaded:
                key = entry.name.lower()
                if not entry.is_passable or key in seen_names:
                    continue
                seen_names.add(key)
                self.entries.append(entry)
        except Exception:
            pass

    def _append_history(self):
        record = {
            "map_area_name": self.map_area_name,
            "map_started_at": self.map_started_at,
            "map_ended_at": time.time(),
            "entries": [asdict(e) for e in self.entries],
        }
        with CONFIG.history_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")


TRACKER = TrackerState()
