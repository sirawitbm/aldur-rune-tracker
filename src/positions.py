"""Persists user-dragged window positions across restarts.

Separate from config.json (tunables you edit by hand) - this is runtime
state the app writes to itself, same spirit as session.json/history.jsonl.
"""
import json

from .config import CONFIG


def _path():
    return CONFIG.data_dir / "positions.json"


def load() -> dict:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_position(key: str, x: int, y: int):
    data = load()
    data[key] = [x, y]
    _path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_position(key: str):
    pos = load().get(key)
    if pos and len(pos) == 2:
        return int(pos[0]), int(pos[1])
    return None
