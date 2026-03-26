"""
Symptom panel — left/top section of the overlay.

Shows a scrollable list of currently active handling symptoms, colour-coded
by severity.  Clicking a symptom emits symptom_selected so the suggestion
panel can update.
"""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal, Qt, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import (
    QFrame, QLabel, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from analysis.symptom_detector import Symptom, Severity, SymptomType
from config import MAX_SUGGESTIONS_SHOWN


def _context_summary(symptom: Symptom) -> str:
    """One-line context string shown below the symptom label."""
    ctx = symptom.context
    parts = []
    if "speed_kph" in ctx:
        parts.append(f"{ctx['speed_kph']:.0f} kph")
    if "yaw_deficit_ratio" in ctx:
        parts.append(f"yaw {ctx['yaw_deficit_ratio']:.0%} of expected")
    if "yaw_excess_ratio" in ctx:
        parts.append(f"yaw {ctx['yaw_excess_ratio']:.0%} of expected")
    if "spin_delta_rps" in ctx:
        parts.append(f"+{ctx['spin_delta_rps']:.1f} RPS spin")
    if "max_temp_c" in ctx:
        parts.append(f"{ctx['max_temp_c']:.0f} °C")
    if "min_temp_c" in ctx:
        parts.append(f"{ctx['min_temp_c']:.0f} °C")
    if "wheels" in ctx:
        parts.append(", ".join(ctx["wheels"]))
    if "brake_temp_delta_c" in ctx:
        parts.append(f"ΔT {ctx['brake_temp_delta_c']:.0f} °C L/R")
    if "min_ride_height_mm" in ctx:
        parts.append(f"{ctx['min_ride_height_mm']:.0f} mm clearance")
    return "  ·  ".join(parts)


class _SymptomItem(QFrame):
    clicked = pyqtSignal(object)  # emits Symptom

    _SEVERITY_COLOURS = {
        Severity.HIGH:   "#ff4444",
        Severity.MEDIUM: "#ffaa00",
        Severity.LOW:    "#44aaff",
    }

    def __init__(self, symptom: Symptom, parent=None):
        super().__init__(parent)
        self._symptom = symptom
        self.setObjectName("symptomItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        colour = self._SEVERITY_COLOURS[symptom.severity]
        self.setStyleSheet(
            f"#symptomItem {{ border-left: 3px solid {colour}; "
            f"background: rgba(30, 30, 45, 160); border-radius: 3px; "
            f"padding: 4px 8px; margin: 2px 4px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(1)

        label = QLabel(symptom.label)
        label.setObjectName("symptomLabel")
        label.setStyleSheet(f"font-weight: bold; color: {colour};")
        layout.addWidget(label)

        context_text = _context_summary(symptom)
        if context_text:
            ctx_label = QLabel(context_text)
            ctx_label.setObjectName("symptomContext")
            ctx_label.setStyleSheet("color: #888888; font-size: 10px;")
            layout.addWidget(ctx_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._symptom)


class SymptomPanel(QWidget):
    symptom_selected = pyqtSignal(object)  # Symptom

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_symptoms: list[Symptom] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Section header
        header = QLabel("ACTIVE SYMPTOMS")
        header.setObjectName("sectionHeader")
        header.setStyleSheet(
            "color: #888888; font-size: 10px; font-weight: bold; "
            "letter-spacing: 1px; padding: 6px 8px 2px 8px;"
        )
        outer.addWidget(header)

        # Scroll area for symptom items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(160)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 2, 0, 2)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        outer.addWidget(scroll)

        # "No issues detected" placeholder
        self._empty_label = QLabel("No issues detected")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet(
            "color: #444466; font-size: 11px; padding: 12px;"
        )
        outer.addWidget(self._empty_label)
        self._scroll_area = scroll

    def update_symptoms(self, symptoms: list[Symptom]):
        # Clear existing items (remove all except the stretch at the end)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._current_symptoms = symptoms
        has_symptoms = bool(symptoms)

        self._scroll_area.setVisible(has_symptoms)
        self._empty_label.setVisible(not has_symptoms)

        for symptom in symptoms:
            item = _SymptomItem(symptom)
            item.clicked.connect(self.symptom_selected)
            self._list_layout.insertWidget(self._list_layout.count() - 1, item)

        # Auto-select highest severity symptom
        if symptoms:
            priority_order = [Severity.HIGH, Severity.MEDIUM, Severity.LOW]
            for sev in priority_order:
                matching = [s for s in symptoms if s.severity == sev]
                if matching:
                    self.symptom_selected.emit(matching[0])
                    break
