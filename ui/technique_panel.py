"""
Technique tab — live input readout and lap-vs-reference trace chart.

Shows:
  • Live throttle, brake, and steering bars updated every poll cycle
  • A mini chart comparing throttle and brake traces of the current lap
    against the session's fastest reference lap, aligned by track distance
"""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar,
    QSizePolicy, QVBoxLayout, QWidget,
)

from analysis.lap_recorder import LapData, LapSample
from analysis.signal_smoother import SmoothedSignals
from data_layer.data_models import TelemetrySnapshot


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


class _LapTraceChart(QWidget):
    """
    Mini chart showing throttle and brake traces aligned by track distance.

    Reference lap (fastest this session) drawn as faded lines.
    Current in-progress lap drawn as bright lines.
    A vertical cursor marks the car's current position on track.
    """

    _BUCKETS = 250  # distance bins — ~17 m each on a 4.3 km track

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(82)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._ref_throttle: list[float | None] = []
        self._ref_brake: list[float | None] = []
        self._cur_throttle: list[float | None] = []
        self._cur_brake: list[float | None] = []
        self._cur_pos_frac: float = 0.0
        self._has_ref: bool = False

    def update_data(
        self,
        ref_lap: LapData | None,
        cur_samples: list[LapSample],
        cur_distance: float,
        track_length: float,
    ) -> None:
        self._has_ref = ref_lap is not None
        if track_length > 0:
            self._ref_throttle, self._ref_brake = self._bucket(
                ref_lap.samples if ref_lap else [], track_length
            )
            self._cur_throttle, self._cur_brake = self._bucket(cur_samples, track_length)
            self._cur_pos_frac = (
                max(0.0, min(1.0, cur_distance / track_length))
                if cur_distance >= 0 else 0.0
            )
        self.update()

    @classmethod
    def _bucket(
        cls, samples: list[LapSample], track_length: float
    ) -> tuple[list[float | None], list[float | None]]:
        n = cls._BUCKETS
        t_acc: list[list[float]] = [[] for _ in range(n)]
        b_acc: list[list[float]] = [[] for _ in range(n)]
        for s in samples:
            idx = min(int(s.distance / track_length * n), n - 1)
            t_acc[idx].append(s.throttle)
            b_acc[idx].append(s.brake)
        throttle = [sum(lst) / len(lst) if lst else None for lst in t_acc]
        brake    = [sum(lst) / len(lst) if lst else None for lst in b_acc]
        return throttle, brake

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        pad = 4
        cw = w - 2 * pad
        ch = h - 2 * pad

        # Background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(18, 18, 28))
        painter.drawRoundedRect(0, 0, w, h, 3, 3)

        if not self._has_ref:
            f = painter.font()
            f.setPixelSize(10)
            painter.setFont(f)
            painter.setPen(QColor(70, 70, 100))
            painter.drawText(pad, pad, cw, ch, Qt.AlignCenter,
                             "Complete a lap to set reference")
            painter.end()
            return

        n = self._BUCKETS
        bw = cw / n

        def draw_trace(values, r, g, b, alpha, line_width):
            if not any(v is not None for v in values):
                return
            pen = QPen(QColor(r, g, b, alpha))
            pen.setWidthF(line_width)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            path = QPainterPath()
            started = False
            for i, v in enumerate(values):
                if v is None:
                    started = False
                    continue
                x = pad + (i + 0.5) * bw
                y = pad + ch * (1.0 - v)
                if not started:
                    path.moveTo(x, y)
                    started = True
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)

        # Reference traces — faded
        draw_trace(self._ref_throttle,  68, 204, 102,  75, 1.0)
        draw_trace(self._ref_brake,    255,  85,  85,  75, 1.0)

        # Current lap traces — bright
        draw_trace(self._cur_throttle,  68, 204, 102, 220, 1.5)
        draw_trace(self._cur_brake,    255,  85,  85, 220, 1.5)

        # Current position cursor
        if self._cur_pos_frac > 0:
            x = int(pad + self._cur_pos_frac * cw)
            pen = QPen(QColor(255, 255, 255, 100))
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.drawLine(x, pad, x, pad + ch)

        painter.end()


class TechniquePanel(QWidget):
    """
    Live driver input bars and lap-vs-reference trace chart.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
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

        # ── Lap comparison ────────────────────────────────────────────────
        comp_header_row = QWidget()
        comp_header_layout = QHBoxLayout(comp_header_row)
        comp_header_layout.setContentsMargins(8, 6, 8, 2)
        comp_header_layout.setSpacing(6)

        comp_title = QLabel("LAP COMPARISON")
        comp_title.setObjectName("sectionHeader")
        comp_title.setStyleSheet(
            "color: #888888; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        )
        comp_header_layout.addWidget(comp_title)
        comp_header_layout.addStretch()

        self._ref_label = QLabel("Complete a lap to set reference")
        self._ref_label.setStyleSheet("color: #555577; font-size: 10px;")
        comp_header_layout.addWidget(self._ref_label)

        layout.addWidget(comp_header_row)

        # Legend
        legend = QLabel(
            "<span style='color:#44cc66;'>━</span> Throttle &nbsp;"
            "<span style='color:#ff5555;'>━</span> Brake &nbsp;"
            "<span style='color:rgba(68,204,102,80);'>─ ─</span> Reference"
        )
        legend.setTextFormat(Qt.RichText)
        legend.setStyleSheet("color: #666688; font-size: 9px; padding: 0 8px 2px 8px;")
        layout.addWidget(legend)

        # Chart
        chart_box = QWidget()
        chart_layout = QVBoxLayout(chart_box)
        chart_layout.setContentsMargins(8, 2, 8, 8)
        self._chart = _LapTraceChart()
        chart_layout.addWidget(self._chart)
        layout.addWidget(chart_box, 1)

    # ------------------------------------------------------------------
    # Public update API
    # ------------------------------------------------------------------

    def update_telemetry(self, sig: SmoothedSignals) -> None:
        """Called every poll cycle to update live input bars."""
        self._throttle_bar.set_value(sig.unfiltered_throttle)
        self._brake_bar.set_value(sig.unfiltered_brake)
        self._steering_bar.set_value(sig.unfiltered_steering)

    def update_lap_comparison(
        self,
        ref_lap: LapData | None,
        cur_samples: list[LapSample],
        snapshot: TelemetrySnapshot,
    ) -> None:
        """Called every poll cycle to update the lap trace chart."""
        track_length = snapshot.event_info.mTrackLength
        cur_distance = snapshot.lap_distance

        # Update reference label
        if ref_lap is not None:
            t = ref_lap.lap_time
            mins = int(t // 60)
            secs = t % 60
            self._ref_label.setText(f"Best: {mins}:{secs:06.3f}")
            self._ref_label.setStyleSheet("color: #44cc66; font-size: 10px;")
        else:
            self._ref_label.setText("Complete a lap to set reference")
            self._ref_label.setStyleSheet("color: #555577; font-size: 10px;")

        self._chart.update_data(ref_lap, cur_samples, cur_distance, track_length)
