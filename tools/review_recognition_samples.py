import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config import CONFIG
from src.icon_db import ICON_LIBRARY


class SampleReviewer(QWidget):
    def __init__(self, sample_files: list[Path]):
        super().__init__()
        self.sample_files = sample_files
        self.index = 0
        self.setWindowTitle("Aldur Rune Recognition Sample Reviewer")

        self.position_label = QLabel()
        self.capture_label = QLabel()
        self.capture_label.setAlignment(Qt.AlignCenter)
        self.capture_label.setMinimumSize(720, 420)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(120, 120)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.details_label = QLabel()
        self.details_label.setWordWrap(True)

        self.marker_check = QCheckBox("This capture is a passable Remnant rune")
        self.name_combo = QComboBox()
        self.name_combo.addItem("Unrecognized / not a rune", None)
        for name in ICON_LIBRARY.names():
            self.name_combo.addItem(name, name)

        previous_button = QPushButton("Previous")
        previous_button.clicked.connect(self.previous)
        save_button = QPushButton("Save and next")
        save_button.clicked.connect(self.save_and_next)
        button_row = QHBoxLayout()
        button_row.addWidget(previous_button)
        button_row.addStretch()
        button_row.addWidget(save_button)

        content_row = QHBoxLayout()
        content_row.addWidget(self.capture_label, 1)
        content_row.addWidget(self.icon_label)

        layout = QVBoxLayout(self)
        layout.addWidget(self.position_label)
        layout.addLayout(content_row)
        layout.addWidget(self.details_label)
        layout.addWidget(self.marker_check)
        layout.addWidget(self.name_combo)
        layout.addLayout(button_row)
        self.resize(1040, 650)
        self.load_current()

    def load_current(self):
        path = self.sample_files[self.index]
        data = json.loads(path.read_text(encoding="utf-8"))
        sample_dir = path.parent
        capture = QPixmap(str(sample_dir / data["capture_file"]))
        self.capture_label.setPixmap(
            capture.scaled(self.capture_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        icon = QPixmap(str(sample_dir / data["icon_file"]))
        self.icon_label.setPixmap(icon.scaled(110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.position_label.setText(f"Sample {self.index + 1} of {len(self.sample_files)}: {path.name}")
        self.details_label.setText(
            f"App prediction: {data.get('predicted_name') or '(none)'} | "
            f"Outcome: {data.get('outcome')} | Marker detector: {data.get('marker_detected')}"
        )
        verified_marker = data.get("verified_passable", data.get("verified_marker"))
        detected_passable = data.get("has_passable_text")
        if detected_passable is None:
            detected_passable = data.get("outcome") in ("added", "duplicate")
        self.marker_check.setChecked(
            detected_passable if verified_marker is None else verified_marker
        )
        selected_name = data.get("verified_name") or data.get("predicted_name")
        combo_index = self.name_combo.findData(selected_name)
        self.name_combo.setCurrentIndex(max(0, combo_index))

    def save_current(self):
        path = self.sample_files[self.index]
        data = json.loads(path.read_text(encoding="utf-8"))
        data["verified_passable"] = self.marker_check.isChecked()
        data["verified_name"] = self.name_combo.currentData()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_and_next(self):
        self.save_current()
        if self.index + 1 >= len(self.sample_files):
            QMessageBox.information(self, "Review complete", "All recognition samples are verified.")
            return
        self.index += 1
        self.load_current()

    def previous(self):
        self.save_current()
        if self.index > 0:
            self.index -= 1
            self.load_current()


def main():
    app = QApplication(sys.argv)
    sample_dir = CONFIG.data_dir / "recognition_samples"
    sample_files = sorted(sample_dir.glob("*.json")) if sample_dir.exists() else []
    if not sample_files:
        QMessageBox.information(
            None,
            "No samples",
            "Enable recognition sample collection in Settings and capture some passable runes first.",
        )
        return 0
    reviewer = SampleReviewer(sample_files)
    reviewer.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())