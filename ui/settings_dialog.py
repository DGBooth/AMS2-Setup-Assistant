"""
Settings dialog — opacity slider, position lock, and optional AI API key.
"""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal, Qt, QSettings
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QLabel, QLineEdit,
    QSlider, QVBoxLayout, QWidget,
)

from config import OVERLAY_OPACITY


class SettingsDialog(QDialog):
    opacity_changed = pyqtSignal(float)

    def __init__(self, parent=None, current_opacity: float = OVERLAY_OPACITY):
        super().__init__(parent)
        self._settings = QSettings("AMS2SetupAdvisor", "Overlay")
        self.setWindowTitle("AMS2 Setup Advisor — Settings")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ---- Display ----
        display_group = QGroupBox("Display")
        display_form = QFormLayout(display_group)

        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(20, 100)
        self._opacity_slider.setValue(int(current_opacity * 100))
        self._opacity_slider.setTickInterval(10)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)

        self._opacity_label = QLabel(f"{int(current_opacity * 100)}%")
        self._opacity_label.setFixedWidth(36)

        opacity_row = QWidget()
        opacity_row_layout = __import__("PyQt5.QtWidgets", fromlist=["QHBoxLayout"]).QHBoxLayout(opacity_row)
        opacity_row_layout.setContentsMargins(0, 0, 0, 0)
        opacity_row_layout.addWidget(self._opacity_slider)
        opacity_row_layout.addWidget(self._opacity_label)

        display_form.addRow("Opacity:", opacity_row)
        layout.addWidget(display_group)

        # ---- AI mode ----
        ai_group = QGroupBox("AI Mode (optional)")
        ai_layout = QFormLayout(ai_group)

        self._ai_enabled = QCheckBox("Enable AI suggestions")
        saved_enabled = self._settings.value("ai_enabled", False, type=bool)
        self._ai_enabled.setChecked(saved_enabled)
        ai_layout.addRow(self._ai_enabled)

        self._api_key_edit = QLineEdit()
        self._api_key_edit.setPlaceholderText("sk-ant-api03-…")
        self._api_key_edit.setEchoMode(QLineEdit.Password)
        saved_key = self._settings.value("api_key", "")
        self._api_key_edit.setText(saved_key)

        ai_layout.addRow("Anthropic API key:", self._api_key_edit)

        ai_note = QLabel(
            "Your API key is stored locally in Windows registry via QSettings.\n"
            "AI mode calls claude-opus-4-6 when you click 'Ask AI' on a suggestion."
        )
        ai_note.setStyleSheet("color: #666688; font-size: 10px;")
        ai_note.setWordWrap(True)
        ai_layout.addRow(ai_note)

        layout.addWidget(ai_group)

        # ---- Buttons ----
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_opacity_changed(self, value: int):
        opacity = value / 100.0
        self._opacity_label.setText(f"{value}%")
        self.opacity_changed.emit(opacity)

    def _save_and_accept(self):
        self._settings.setValue("opacity", self._opacity_slider.value() / 100.0)
        self._settings.setValue("ai_enabled", self._ai_enabled.isChecked())
        self._settings.setValue("api_key", self._api_key_edit.text().strip())
        self.accept()

    @staticmethod
    def load_api_key() -> str:
        s = QSettings("AMS2SetupAdvisor", "Overlay")
        return s.value("api_key", "")

    @staticmethod
    def ai_enabled() -> bool:
        s = QSettings("AMS2SetupAdvisor", "Overlay")
        return s.value("ai_enabled", False, type=bool)
