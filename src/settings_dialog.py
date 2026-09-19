from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

from .config import CONFIG
from .hotkey_capture import HotkeyCaptureButton


class SettingsDialog(QDialog):
    """Live-editable settings, applied immediately on Save - no restart needed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PoE2 Rune Tracker - Settings")
        self.setModal(True)

        self.hotkey_btn = HotkeyCaptureButton(CONFIG.record_hotkey)
        self.undo_hotkey_btn = HotkeyCaptureButton(getattr(CONFIG, "undo_hotkey", "<f8>"))
        self.capture_delay = self._spin(0, 1000, getattr(CONFIG, "capture_delay_ms", 150))

        self.log_path_edit = QLineEdit(CONFIG.client_log_path or "")
        self.log_path_edit.setPlaceholderText("auto-detect")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_log_path)
        log_row = QHBoxLayout()
        log_row.addWidget(self.log_path_edit)
        log_row.addWidget(browse_btn)

        self.capture_w = self._spin(200, 2000, CONFIG.capture_width)
        self.capture_h = self._spin(150, 1500, CONFIG.capture_height)
        self.offset_x = self._spin(-1000, 1000, CONFIG.capture_offset_x)
        self.offset_y = self._spin(-1000, 1000, CONFIG.capture_offset_y)
        self.icon_crop_size = self._spin(16, 200, CONFIG.icon_crop_size)
        self.overlay_icon_size = self._spin(12, 128, CONFIG.overlay_icon_size)

        self.toast_position = QComboBox()
        self.toast_position.addItems(["cursor", "bottom", "top", "center"])
        self.toast_position.setCurrentText(getattr(CONFIG, "toast_position", "cursor"))

        form = QFormLayout()
        form.addRow("Capture hotkey:", self.hotkey_btn)
        form.addRow("Undo-last hotkey:", self.undo_hotkey_btn)
        form.addRow("Capture delay (ms):", self.capture_delay)
        form.addRow("Client.txt path:", log_row)
        form.addRow("Capture width:", self.capture_w)
        form.addRow("Capture height:", self.capture_h)
        form.addRow("Capture offset X:", self.offset_x)
        form.addRow("Capture offset Y:", self.offset_y)
        form.addRow("Icon crop size (capture):", self.icon_crop_size)
        form.addRow("Icon size (on overlay):", self.overlay_icon_size)
        form.addRow("Capture toast position:", self.toast_position)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(btn_row)
        self.resize(360, 350)

    @staticmethod
    def _spin(lo, hi, value):
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(value)
        return s

    def _browse_log_path(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Client.txt", filter="Log files (*.txt);;All files (*)")
        if path:
            self.log_path_edit.setText(path)

    def _on_save(self):
        if self.hotkey_btn.value == self.undo_hotkey_btn.value:
            QMessageBox.warning(
                self, "Hotkey conflict",
                "Capture hotkey and Undo-last hotkey can't be the same key.",
            )
            return
        self.accept()

    def apply_to_config(self):
        """Writes the dialog's values into CONFIG and persists them. Call after exec() == Accepted."""
        CONFIG.set("record_hotkey", self.hotkey_btn.value)
        CONFIG.set("undo_hotkey", self.undo_hotkey_btn.value)
        CONFIG.set("capture_delay_ms", self.capture_delay.value())
        CONFIG.set("client_log_path", self.log_path_edit.text().strip() or None)
        CONFIG.set("capture_width", self.capture_w.value())
        CONFIG.set("capture_height", self.capture_h.value())
        CONFIG.set("capture_offset_x", self.offset_x.value())
        CONFIG.set("capture_offset_y", self.offset_y.value())
        CONFIG.set("icon_crop_size", self.icon_crop_size.value())
        CONFIG.set("overlay_icon_size", self.overlay_icon_size.value())
        CONFIG.set("toast_position", self.toast_position.currentText())
        CONFIG.save()
