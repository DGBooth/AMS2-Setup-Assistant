"""
Technique tab — live input readout and per-corner coaching feedback.

Shows:
  • Live throttle, brake, and steering bars updated every poll cycle
  • A scrollable list of per-corner coaching summaries, newest first

No setup suggestions — this is purely about driving technique.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from analysis.corner_analyzer import CornerReport
from analysis.signal_smoother import SmoothedSignals


class _InputBar(QWidget):
    """Labelled progress bar for a single driver input channel."""

    def __init__(self, label: str, color: str, centered: bool = False, parent=None):
        super().__init__(parent)
        self._centered = centered
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        lbl = QLabel(label)
        lbl.setFixedWidth(54)
        lbl.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(10)
        self._bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._bar.setStyleSheet(
            f"QProgressBar {{ background: rgba(40,40,60,180); border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
        )
        layout.addWidget(self._bar)

        self._pct_label = QLabel("0%")
        self._pct_label.setFixedWidth(36)
        self._pct_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._pct_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        layout.addWidget(self._pct_label)

    def set_value(self, value: float) -> None:
        """value: 0.0–1.0 for throttle/brake; −1.0…+1.0 for steering."""
        if self._centered:
            pct = abs(value)
            self._bar.setValue(int(pct * 100))
            if value > 0.02:
                self._pct_label.setText(f"{pct:.0%} R")
            elif value < -0.02:
                self._pct_label.setText(f"{pct:.0%} L")
            else:
                self._pct_label.setText("0%")
        else:
            clamped = max(0.0, min(1.0, value))
            self._bar.setValue(int(clamped * 100))
            self._pct_label.setText(f"{clamped:.0%}")


class _CornerCard(QFrame):
    """Coaching card for a single completed corner."""

    _COLOR_CLEAN = "#44ff88"
    _COLOR_ISSUE = "#ffaa00"

    def __init__(self, report: CornerReport, index: int, parent=None):
        super().__init__(parent)
        self.setObjectName("cornerCard")
        color = self._COLOR_ISSUE if report.had_issues else self._COLOR_CLEAN
        self.setStyleSheet(
            f"#cornerCard {{ background: rgba(30,30,45,160); border-radius: 3px; "
            f"border-left: 3px solid {color}; margin: 2px 4px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(3)

        # Header
        corner_label = "Last corner" if index == 0 else f"{index + 1} corners ago"
        header_text = (
            f"{corner_label}  ·  Peak {report.peak_lat_g:.2f}g  ·  "
            f"{report.min_speed_kph:.0f}–{report.max_speed_kph:.0f} kph"
        )
        header = QLabel(header_text)
        header.setStyleSheet(f"font-weight: bold; font-size: 10px; color: {color};")
        layout.addWidget(header)

        if report.had_issues:
            for issue in report.issues:
                row = QLabel(f"• {issue}")
                row.setWordWrap(True)
                row.setStyleSheet("color: #cccccc; font-size: 10px; padding-left: 2px;")
                layout.addWidget(row)
        else:
            ok = QLabel("Clean corner — good technique")
            ok.setStyleSheet(f"color: {self._COLOR_CLEAN}; font-size: 10px;")
            layout.addWidget(ok)


class TechniquePanel(QWidget):
    """
    Live driver input bars and scrollable per-corner coaching history.
    """

    _MAX_CORNERS = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reports: list[CornerReport] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Live inputs ──────────────────────────────────────────────────
        inputs_header = QLabel("LIVE INPUTS")
        inputs_header.setObjectName("sectionHeader")
        inputs_header.setStyleSheet(
            "color: #888888; font-size: 10px; font-weight: bold; "
            "letter-spacing: 1px; padding: 6px 8px 4px 8px;"
        )
        layout.addWidget(inputs_header)

        inputs_box = QWidget()
        inputs_layout = QVBoxLayout(inputs_box)
        inputs_layout.setContentsMargins(8, 0, 8, 6)
        inputs_layout.setSpacing(3)

        self._throttle_bar = _InputBar("THROTTLE", "#44cc66")
        self._brake_bar    = _InputBar("BRAKE",    "#ff5555")
        self._steering_bar = _InputBar("STEERING", "#44aaff", centered=True)
        inputs_layout.addWidget(self._throttle_bar)
        inputs_layout.addWidget(self._brake_bar)
        inputs_layout.addWidget(self._steering_bar)
        layout.addWidget(inputs_box)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: rgba(80,80,120,100);")
        layout.addWidget(divider)

        # ── Corner analysis ───────────────────────────────────────────────
        history_header = QLabel("CORNER ANALYSIS")
        history_header.setObjectName("sectionHeader")
        history_header.setStyleSheet(
            "color: #888888; font-size: 10px; font-weight: bold; "
            "letter-spacing: 1px; padding: 6px 8px 2px 8px;"
        )
        layout.addWidget(history_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)

        self._history_widget = QWidget()
        self._history_layout = QVBoxLayout(self._history_widget)
        self._history_layout.setContentsMargins(0, 2, 0, 2)
        self._history_layout.setSpacing(2)
        self._history_layout.addStretch()

        scroll.setWidget(self._history_widget)
        layout.addWidget(scroll, 1)

        self._empty_label = QLabel("Waiting for corner data…")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #444466; font-size: 11px; padding: 12px;")
        layout.addWidget(self._empty_label)

        self._scroll_area = scroll
        self._refresh_visibility()

    # ------------------------------------------------------------------
    # Public update API
    # ------------------------------------------------------------------

    def update_telemetry(self, sig: SmoothedSignals) -> None:
        """Called every poll cycle to update live input bars."""
        self._throttle_bar.set_value(sig.unfiltered_throttle)
        self._brake_bar.set_value(sig.unfiltered_brake)
        self._steering_bar.set_value(sig.unfiltered_steering)

    def add_corner_report(self, report: CornerReport) -> None:
        """Add a new corner report to the top of the history list."""
        self._reports.insert(0, report)
        if len(self._reports) > self._MAX_CORNERS:
            self._reports = self._reports[:self._MAX_CORNERS]
        self._rebuild_history()

    def clear(self) -> None:
        """Clear all corner history (e.g. on garage exit)."""
        self._reports.clear()
        self._rebuild_history()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild_history(self) -> None:
        while self._history_layout.count() > 1:
            item = self._history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, report in enumerate(self._reports):
            card = _CornerCard(report, i)
            self._history_layout.insertWidget(self._history_layout.count() - 1, card)

        self._refresh_visibility()

    def _refresh_visibility(self) -> None:
        has_data = bool(self._reports)
        self._scroll_area.setVisible(has_data)
        self._empty_label.setVisible(not has_data)
