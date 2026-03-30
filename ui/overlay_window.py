"""
Main overlay window.

Transparent, frameless, always-on-top window that hosts the symptom and
suggestion panels.  Draggable by clicking the header bar.  Position and
opacity are persisted via QSettings.
"""

from __future__ import annotations
import os

from PyQt5.QtCore import Qt, QPoint, QSettings, pyqtSlot
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QSizeGrip, QSizePolicy, QStyle, QTabWidget,
    QVBoxLayout, QWidget,
)

from config import (
    COLOR_ACCENT, OVERLAY_DEFAULT_X, OVERLAY_DEFAULT_Y,
    OVERLAY_HEIGHT, OVERLAY_OPACITY, OVERLAY_WIDTH,
)
from data_layer.data_models import TelemetrySnapshot
from analysis.symptom_detector import Symptom, SymptomType
from analysis.suggestion_table import SuggestionEntry
from ui.symptom_panel import SymptomPanel
from ui.suggestion_panel import SuggestionPanel
from ui.fuel_calculator import FuelCalculatorPanel

# Symptom types that belong on the Technique tab rather than the Setup tab
_TECHNIQUE_SYMPTOM_TYPES = frozenset({
    SymptomType.LATE_BRAKING,
    SymptomType.EARLY_THROTTLE,
    SymptomType.SLOW_CORNER_EXIT,
})


class _ResizeGrip(QSizeGrip):
    """QSizeGrip with a painted dot-grid resize indicator."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(COLOR_ACCENT)
        color.setAlpha(180)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        dot, gap = 2, 4
        for row in range(3):
            for col in range(3):
                if col + row >= 2:  # lower-right triangle only
                    x = self.width()  - (3 - col) * gap
                    y = self.height() - (3 - row) * gap
                    painter.drawEllipse(x, y, dot, dot)


def _load_stylesheet() -> str:
    qss_path = os.path.join(os.path.dirname(__file__), "..", "assets", "style.qss")
    try:
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


class OverlayWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self._drag_pos: QPoint | None = None
        self._settings = QSettings("AMS2SetupAdvisor", "Overlay")
        self._minimised = False
        self._expanded_size: tuple[int, int] | None = None

        self._init_window()
        self._build_ui()
        self._restore_geometry()

        self.setStyleSheet(_load_stylesheet())

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _init_window(self):
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool               # no taskbar entry
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(
            float(self._settings.value("opacity", OVERLAY_OPACITY))
        )
        self.resize(OVERLAY_WIDTH, OVERLAY_HEIGHT)

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("overlayFrame")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 6)
        root_layout.setSpacing(0)

        # Header bar
        header = self._build_header()
        self._header_widget = header
        root_layout.addWidget(header)

        # Content area
        self._content_widget = QWidget()
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(0, 2, 0, 0)
        content_layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.setObjectName("mainTabs")

        # --- Setup tab ---
        setup_tab = QWidget()
        setup_layout = QVBoxLayout(setup_tab)
        setup_layout.setContentsMargins(0, 0, 0, 0)
        setup_layout.setSpacing(0)
        self._symptom_panel = SymptomPanel()
        self._suggestion_panel = SuggestionPanel()
        setup_layout.addWidget(self._symptom_panel)
        setup_layout.addWidget(self._suggestion_panel)
        tabs.addTab(setup_tab, "SETUP")

        # --- Technique tab ---
        technique_tab = QWidget()
        technique_layout = QVBoxLayout(technique_tab)
        technique_layout.setContentsMargins(0, 0, 0, 0)
        technique_layout.setSpacing(0)
        self._technique_panel = SymptomPanel(title="CORNER TECHNIQUE")
        self._technique_suggestion_panel = SuggestionPanel()
        technique_layout.addWidget(self._technique_panel)
        technique_layout.addWidget(self._technique_suggestion_panel)
        tabs.addTab(technique_tab, "TECHNIQUE")

        # --- Fuel tab ---
        self._fuel_panel = FuelCalculatorPanel()
        tabs.addTab(self._fuel_panel, "FUEL")

        content_layout.addWidget(tabs)
        root_layout.addWidget(self._content_widget)

        grip = _ResizeGrip(self)
        grip.setFixedSize(16, 16)
        root_layout.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)

        # Connect symptom selection → suggestion update for each tab
        self._symptom_panel.symptom_selected.connect(self._on_symptom_selected)
        self._technique_panel.symptom_selected.connect(self._on_technique_symptom_selected)

    def _build_header(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("headerBar")
        bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._conn_label = QLabel("●")
        self._conn_label.setObjectName("disconnectedDot")
        self._conn_label.setFixedWidth(12)

        title = QLabel("AMS2 Setup Advisor")
        title.setObjectName("titleLabel")

        layout.addWidget(self._conn_label)
        layout.addWidget(title)
        layout.addStretch()

        self._car_label = QLabel("")
        self._car_label.setObjectName("statusLabel")
        layout.addWidget(self._car_label)

        def _icon_btn(standard_pixmap: QStyle.StandardPixmap, tooltip: str) -> QPushButton:
            btn = QPushButton()
            btn.setIcon(self.style().standardIcon(standard_pixmap))
            btn.setFixedSize(22, 22)
            btn.setToolTip(tooltip)
            return btn

        settings_btn = _icon_btn(QStyle.SP_FileDialogDetailedView, "Settings")
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn)

        minimise_btn = _icon_btn(QStyle.SP_TitleBarMinButton, "Minimise")
        minimise_btn.clicked.connect(self._toggle_minimise)
        layout.addWidget(minimise_btn)

        close_btn = _icon_btn(QStyle.SP_TitleBarCloseButton, "Close")
        close_btn.clicked.connect(QApplication.quit)
        layout.addWidget(close_btn)

        return bar

    # ------------------------------------------------------------------
    # Public update API (called from main loop)
    # ------------------------------------------------------------------

    @pyqtSlot(object)
    def update_snapshot(self, snapshot: TelemetrySnapshot):
        """Receive raw snapshot to update connection status / car label."""
        connected = snapshot.game_running
        self._conn_label.setObjectName("connectedDot" if connected else "disconnectedDot")
        self._conn_label.setStyleSheet(
            "color: #44ff88;" if connected else "color: #ff4444;"
        )
        if snapshot.vehicle_info.mCarName:
            self._car_label.setText(snapshot.vehicle_info.mCarName)
        # Forward last_lap_time so the fuel tab can auto-fill the lap timer
        self._fuel_panel.update_snapshot(snapshot.last_lap_time)

    @pyqtSlot(list)
    def update_symptoms(self, symptoms: list[Symptom]):
        setup_symptoms = [s for s in symptoms if s.symptom_type not in _TECHNIQUE_SYMPTOM_TYPES]
        technique_symptoms = [s for s in symptoms if s.symptom_type in _TECHNIQUE_SYMPTOM_TYPES]
        self._symptom_panel.update_symptoms(setup_symptoms)
        self._technique_panel.update_symptoms(technique_symptoms)

    @pyqtSlot(object, list)
    def show_suggestions(self, symptom: Symptom, suggestions: list[SuggestionEntry]):
        self._suggestion_panel.show_suggestions(symptom, suggestions)

    # ------------------------------------------------------------------
    # Dragging
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._save_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._save_geometry()

    # ------------------------------------------------------------------
    # Minimise toggle
    # ------------------------------------------------------------------

    def _toggle_minimise(self):
        self._minimised = not self._minimised
        self._content_widget.setVisible(not self._minimised)
        if self._minimised:
            self._expanded_size = (self.width(), self.height())
            # Pin height to just the header — adjustSize() is unreliable on QMainWindow
            self.setFixedHeight(self._header_widget.sizeHint().height())
        else:
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)  # release fixed-height constraint
            if self._expanded_size is not None:
                self.resize(*self._expanded_size)
            else:
                self.adjustSize()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self):
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self, current_opacity=self.windowOpacity())
        dlg.opacity_changed.connect(self.setWindowOpacity)
        dlg.exec_()

    # ------------------------------------------------------------------
    # Geometry persistence
    # ------------------------------------------------------------------

    def _save_geometry(self):
        self._settings.setValue("x", self.x())
        self._settings.setValue("y", self.y())
        if not self._minimised:
            self._settings.setValue("w", self.width())
            self._settings.setValue("h", self.height())

    def _restore_geometry(self):
        w = int(self._settings.value("w", OVERLAY_WIDTH))
        h = int(self._settings.value("h", OVERLAY_HEIGHT))
        self.resize(w, h)
        x = int(self._settings.value("x", OVERLAY_DEFAULT_X))
        y = int(self._settings.value("y", OVERLAY_DEFAULT_Y))
        # Clamp to screen bounds
        screen = QApplication.primaryScreen().availableGeometry()
        x = max(0, min(x, screen.width()  - w))
        y = max(0, min(y, screen.height() - 60))
        self.move(x, y)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot(object)
    def _on_symptom_selected(self, symptom: Symptom):
        from analysis.suggestion_table import get_suggestions
        from config import MAX_SUGGESTIONS_SHOWN
        suggestions = get_suggestions(symptom, MAX_SUGGESTIONS_SHOWN)
        self._suggestion_panel.show_suggestions(symptom, suggestions)

    @pyqtSlot(object)
    def _on_technique_symptom_selected(self, symptom: Symptom):
        from analysis.suggestion_table import get_suggestions
        from config import MAX_SUGGESTIONS_SHOWN
        suggestions = get_suggestions(symptom, MAX_SUGGESTIONS_SHOWN)
        self._technique_suggestion_panel.show_suggestions(symptom, suggestions)

    # ------------------------------------------------------------------
    # Paint translucent background
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        # Background is handled by the central widget's QSS; nothing extra needed.
        super().paintEvent(event)
