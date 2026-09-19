from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def _make_icon() -> QIcon:
    """A small generated glyph - keeps the app self-contained, no asset file."""
    pm = QPixmap(64, 64)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(60, 120, 220))
    p.setPen(QColor(20, 40, 80))
    p.drawEllipse(4, 4, 56, 56)
    p.setPen(QColor(255, 255, 255))
    font = p.font()
    font.setBold(True)
    font.setPointSize(28)
    p.setFont(font)
    p.drawText(pm.rect(), Qt.AlignCenter, "R")
    p.end()
    return QIcon(pm)


class TrayIcon(QSystemTrayIcon):
    settings_requested = Signal()
    reset_requested = Signal()
    undo_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(_make_icon(), parent)
        self.setToolTip("PoE2 Rune Tracker")

        menu = QMenu()
        settings_action = menu.addAction("Settings...")
        settings_action.triggered.connect(self.settings_requested.emit)

        undo_action = menu.addAction("Undo last capture")
        undo_action.triggered.connect(self.undo_requested.emit)

        reset_action = menu.addAction("Reset tracker")
        reset_action.triggered.connect(self.reset_requested.emit)

        menu.addSeparator()

        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_requested.emit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.settings_requested.emit()
