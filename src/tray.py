from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from src.resources import app_icon


class TrayIcon(QSystemTrayIcon):
    settings_requested = Signal()
    reset_requested = Signal()
    undo_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(app_icon(), parent)
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
