"""Tails PoE2's Client.txt to detect zone transitions.

Detection is heuristic (see README "Reset detection accuracy" section):
- "You have entered <Area>." marks any zone transition.
- Hideout = area name contains "Hideout".
- Likely-map = the entry is immediately preceded by a "Generating level ..."
  log line (procedurally generated instances log this; fixed hubs/story
  zones generally don't). This is the same signal tools like Exile Diary
  use for PoE1 and is expected to carry over, but hasn't been verified
  against a live PoE2 Client.txt yet - tune COMMON_LOG_PATHS / the regexes
  below if your log format differs.
"""
import queue
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .config import CONFIG

ENTERED_RE = re.compile(r"You have entered (.+)\.\s*$")
GENERATING_RE = re.compile(r"Generating level", re.IGNORECASE)

COMMON_LOG_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\Path of Exile 2\logs\Client.txt",
    r"C:\Program Files\Steam\steamapps\common\Path of Exile 2\logs\Client.txt",
    r"C:\Program Files (x86)\Grinding Gear Games\Path of Exile 2\logs\Client.txt",
    r"C:\Program Files\Grinding Gear Games\Path of Exile 2\logs\Client.txt",
    r"D:\SteamLibrary\steamapps\common\Path of Exile 2\logs\Client.txt",
    r"D:\Steam\steamapps\common\Path of Exile 2\logs\Client.txt",
]


@dataclass
class AreaEvent:
    area_name: str
    is_hideout: bool
    likely_map: bool
    ts: float


def find_log_path() -> Path | None:
    configured = CONFIG.client_log_path
    if configured:
        p = Path(configured)
        if p.exists():
            return p
    for candidate in COMMON_LOG_PATHS:
        p = Path(candidate)
        if p.exists():
            return p
    return None


class LogWatcher:
    def __init__(self, event_queue: "queue.Queue[AreaEvent]"):
        self.event_queue = event_queue
        self.path: Path | None = find_log_path()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._recent_lines: list[str] = []

    @property
    def status(self) -> str:
        if self.path is None:
            return "Client.txt not found - auto-reset disabled (set the path in Settings)"
        return f"Watching {self.path}"

    def start(self):
        if self.path is None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def restart(self):
        """Call after CONFIG.client_log_path changes to re-resolve and re-tail it live."""
        self.stop()
        self.path = find_log_path()
        self._recent_lines = []
        self.start()

    def _run(self):
        with self.path.open("r", encoding="utf-8", errors="ignore") as fh:
            fh.seek(0, 2)  # start at end - only react to new zone changes
            while not self._stop.is_set():
                line = fh.readline()
                if not line:
                    time.sleep(CONFIG.log_poll_interval_sec)
                    continue
                self._handle_line(line.rstrip("\n"))

    def _handle_line(self, line: str):
        self._recent_lines.append(line)
        if len(self._recent_lines) > 10:
            self._recent_lines.pop(0)

        m = ENTERED_RE.search(line)
        if not m:
            return

        area_name = m.group(1).strip()
        is_hideout = "hideout" in area_name.lower()
        likely_map = (not is_hideout) and any(
            GENERATING_RE.search(l) for l in self._recent_lines[-6:]
        )
        self.event_queue.put(AreaEvent(
            area_name=area_name,
            is_hideout=is_hideout,
            likely_map=likely_map,
            ts=time.time(),
        ))
