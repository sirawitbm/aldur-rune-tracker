import sys
from pathlib import Path

from PySide6.QtGui import QIcon


def resource_path(*parts: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return bundle_root.joinpath(*parts)


def app_icon() -> QIcon:
    return QIcon(str(resource_path("data", "RA.jpg")))