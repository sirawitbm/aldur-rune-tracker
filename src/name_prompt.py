from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .config import CONFIG


class NamePromptDialog(QDialog):
    """Last resort only: shown when neither image matching nor OCR could
    confidently identify a capture. Picks from the SAME prepared database
    names used everywhere else - never free-typed info - so the app never
    ends up displaying something that isn't a real, known rune name.
    Typing filters the list (combobox is editable but not insertable); if
    truly nothing in the list matches (a rune type not yet in the database)
    typing a new name is still possible as an explicit last-resort escape
    hatch, clearly distinct from picking a known entry.
    """

    def __init__(
        self,
        known_names: list[str],
        suggested_name: str | None = None,
        debug_text: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Which rune is this?")
        self.setModal(True)

        label = QLabel(
            "Unrecognized icon - pick its name from the list\n"
            "(type to filter; only pick 'type a new name' if it's genuinely not listed)"
        )

        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.addItems(known_names)
        if suggested_name and suggested_name in known_names:
            self.combo.setCurrentText(suggested_name)
        else:
            self.combo.setCurrentText(suggested_name or "")

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        skip_btn = QPushButton("Skip this capture")
        skip_btn.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(skip_btn)
        btn_row.addWidget(ok_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(self.combo)

        if debug_text:
            debug_label = QLabel(debug_text)
            debug_label.setWordWrap(True)
            debug_label.setStyleSheet("color: #999; font-size: 10px;")
            debug_label.setTextInteractionFlags(debug_label.textInteractionFlags() | Qt.TextSelectableByMouse)
            layout.addWidget(debug_label)

        layout.addLayout(btn_row)
        self.resize(400, 170 if debug_text else 130)

    @property
    def value(self) -> str:
        return self.combo.currentText().strip()


class DisambiguationDialog(QDialog):
    """A close call between a couple of visually-similar icons (see
    icon_db.AMBIGUITY_MARGIN) - one click on the right one settles it,
    instead of making you navigate a dropdown of all 33 names for what's
    really a choice between 2-3 candidates. Candidates can come from image
    matching (labeled with their score) or a fuzzy OCR guess not already
    among them (labeled "OCR guess") - either way, clicking one is you
    deliberately confirming it, so there's no risk of quietly trusting a
    weaker signal the way silently falling back to it would be."""

    def __init__(self, candidates: list[tuple[object, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Which rune is this?")
        self.setModal(True)
        self._chosen = None

        label = QLabel("Close match - click the correct one:")

        btn_row = QHBoxLayout()
        for entry, sublabel in candidates:
            btn = QPushButton()
            btn.setText(f"{entry.name}\n({sublabel})")
            btn.setMinimumSize(110, 90)
            pm = QPixmap(str(CONFIG.data_dir / entry.icon_file))
            if not pm.isNull():
                btn.setIcon(pm.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                btn.setIconSize(QSize(40, 40))
            btn.clicked.connect(lambda _checked=False, e=entry: self._choose(e))
            btn_row.addWidget(btn)

        skip_btn = QPushButton("None of these")
        skip_btn.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addLayout(btn_row)
        layout.addWidget(skip_btn)
        self.resize(120 * len(candidates) + 40, 160)

    def _choose(self, entry):
        self._chosen = entry
        self.accept()

    @property
    def value(self):
        return self._chosen
