"""
Fuel calculator panel — third tab of the overlay.

Auto-tracking (when CREST2 is connected):
  • Records fuel level at the start of each lap.
  • When a lap completes (last_lap_time changes) the used-fuel delta is
    computed automatically and the entry is logged without user input.

Manual fallback:
  • The user can also type in a lap time + fuel figure and click "+".
  • Useful for out-laps or laps where telemetry was interrupted.

In every calculation a 5 % safety buffer is added so the recommendation
is always slightly more than the bare minimum.
"""

from __future__ import annotations
import math

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup, QCheckBox, QDoubleSpinBox, QFrame, QHBoxLayout,
    QLabel, QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QWidget,
)

_SAFETY_BUFFER = 0.05   # 5 %


def _fmt_time(total_seconds: float) -> str:
    minutes = int(total_seconds) // 60
    secs = total_seconds - minutes * 60
    return f"{minutes}:{secs:04.1f}"


class FuelCalculatorPanel(QWidget):
    """Panel for the FUEL tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lap_data: list[tuple[float, float]] = []  # (lap_time_s, fuel_litres)

        # Auto-tracking state
        self._last_seen_lap_time: float = -1.0
        self._fuel_at_lap_start: float | None = None    # litres at start of current lap

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        layout.addWidget(_section_header("LAP DATA"))
        layout.addWidget(self._build_entry_row())
        layout.addWidget(self._build_avg_display())

        layout.addWidget(_divider())

        layout.addWidget(_section_header("RACE CALCULATION"))
        layout.addWidget(self._build_mode_row())
        layout.addWidget(self._build_race_inputs())

        calc_btn = QPushButton("CALCULATE")
        calc_btn.setObjectName("calcButton")
        calc_btn.clicked.connect(self._recalculate)
        layout.addWidget(calc_btn)

        layout.addWidget(self._build_result_frame())
        layout.addStretch()

    def _build_entry_row(self) -> QWidget:
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)

        hl.addWidget(_small_label("Lap:"))

        self._lap_min = QSpinBox()
        self._lap_min.setRange(0, 59)
        self._lap_min.setSuffix("m")
        self._lap_min.setFixedWidth(52)
        self._lap_min.setToolTip("Lap minutes")
        hl.addWidget(self._lap_min)

        self._lap_sec = QDoubleSpinBox()
        self._lap_sec.setRange(0.0, 59.9)
        self._lap_sec.setDecimals(1)
        self._lap_sec.setSuffix("s")
        self._lap_sec.setFixedWidth(62)
        self._lap_sec.setToolTip("Lap seconds")
        hl.addWidget(self._lap_sec)

        hl.addSpacing(6)
        hl.addWidget(_small_label("Fuel:"))

        self._lap_fuel = QDoubleSpinBox()
        self._lap_fuel.setRange(0.1, 30.0)
        self._lap_fuel.setDecimals(2)
        self._lap_fuel.setSuffix(" L")
        self._lap_fuel.setValue(2.00)
        self._lap_fuel.setFixedWidth(74)
        self._lap_fuel.setToolTip("Fuel used this lap")
        hl.addWidget(self._lap_fuel)

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(28)
        add_btn.setToolTip("Record this lap manually")
        add_btn.clicked.connect(self._add_lap_manual)
        hl.addWidget(add_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setToolTip("Remove all recorded laps")
        clear_btn.clicked.connect(self._clear_laps)
        hl.addWidget(clear_btn)

        hl.addStretch()
        return row

    def _build_avg_display(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("fuelStatsFrame")
        hl = QHBoxLayout(frame)
        hl.setContentsMargins(8, 5, 8, 5)
        hl.setSpacing(0)

        self._count_label = _stat_label("Laps: 0")
        self._avg_time_label = _stat_label("Avg time: —")
        self._avg_fuel_label = _stat_label("Avg fuel: —")

        for lbl in (self._count_label, self._avg_time_label, self._avg_fuel_label):
            hl.addWidget(lbl)
            hl.addStretch()

        return frame

    def _build_mode_row(self) -> QWidget:
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(14)

        self._mode_laps = QRadioButton("By laps")
        self._mode_time = QRadioButton("By time")
        self._mode_laps.setChecked(True)

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._mode_laps)
        self._mode_group.addButton(self._mode_time)

        hl.addWidget(self._mode_laps)
        hl.addWidget(self._mode_time)
        hl.addStretch()

        self._mode_laps.toggled.connect(self._on_mode_changed)
        return row

    def _build_race_inputs(self) -> QWidget:
        container = QWidget()
        vl = QVBoxLayout(container)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)

        # Laps row
        self._laps_row = QWidget()
        hl = QHBoxLayout(self._laps_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)
        hl.addWidget(_small_label("Number of laps:"))
        self._race_laps = QSpinBox()
        self._race_laps.setRange(1, 999)
        self._race_laps.setValue(30)
        self._race_laps.setFixedWidth(68)
        hl.addWidget(self._race_laps)
        hl.addStretch()
        vl.addWidget(self._laps_row)

        # Time rows
        self._time_rows = QWidget()
        tl = QVBoxLayout(self._time_rows)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(4)

        time_row = QWidget()
        hl2 = QHBoxLayout(time_row)
        hl2.setContentsMargins(0, 0, 0, 0)
        hl2.setSpacing(6)
        hl2.addWidget(_small_label("Race time:"))
        self._race_time_min = QSpinBox()
        self._race_time_min.setRange(1, 1440)
        self._race_time_min.setValue(60)
        self._race_time_min.setSuffix(" min")
        self._race_time_min.setFixedWidth(82)
        hl2.addWidget(self._race_time_min)
        hl2.addStretch()
        tl.addWidget(time_row)

        self._plus_one_lap = QCheckBox("Time + 1 lap  (extra lap after timer expires)")
        self._plus_one_lap.setToolTip(
            "Tick for race formats that run one extra lap after the timer expires."
        )
        tl.addWidget(self._plus_one_lap)

        self._time_rows.hide()
        vl.addWidget(self._time_rows)

        return container

    def _build_result_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("fuelResultFrame")
        vl = QVBoxLayout(frame)
        vl.setContentsMargins(10, 8, 10, 8)
        vl.setSpacing(3)

        self._result_main = QLabel("—")
        self._result_main.setObjectName("fuelResultMain")
        self._result_main.setAlignment(Qt.AlignCenter)
        vl.addWidget(self._result_main)

        self._result_detail = QLabel("")
        self._result_detail.setObjectName("fuelResultDetail")
        self._result_detail.setAlignment(Qt.AlignCenter)
        self._result_detail.setWordWrap(True)
        vl.addWidget(self._result_detail)

        return frame

    # ------------------------------------------------------------------
    # Public API — called from OverlayWindow on every telemetry tick
    # ------------------------------------------------------------------

    def update_snapshot(self, last_lap_time: float, fuel_litres: float) -> None:
        """
        Called every poll cycle with the latest telemetry values.

        - Tracks fuel level at the start of each lap.
        - Detects a completed lap when last_lap_time changes and
          automatically records (lap_time, fuel_used) without user input.
        - Also pre-fills the manual entry fields as a fallback.
        """
        # Initialise fuel tracking on first valid reading
        if self._fuel_at_lap_start is None and fuel_litres > 0.0:
            self._fuel_at_lap_start = fuel_litres

        lap_completed = (
            last_lap_time > 0.0
            and last_lap_time != self._last_seen_lap_time
        )

        if lap_completed:
            fuel_used = None
            if self._fuel_at_lap_start is not None and fuel_litres > 0.0:
                fuel_used = self._fuel_at_lap_start - fuel_litres

            if fuel_used is not None and fuel_used > 0.05:
                # Auto-log the completed lap
                self._log_lap(last_lap_time, fuel_used)
            else:
                # Telemetry unavailable — pre-fill time field for manual entry
                minutes = int(last_lap_time) // 60
                secs = last_lap_time - minutes * 60
                self._lap_min.setValue(minutes)
                self._lap_sec.setValue(round(secs, 1))

            self._last_seen_lap_time = last_lap_time
            # Reset lap-start fuel to current reading for the next lap
            self._fuel_at_lap_start = fuel_litres if fuel_litres > 0.0 else None

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _add_lap_manual(self):
        lap_time_s = self._lap_min.value() * 60.0 + self._lap_sec.value()
        if lap_time_s < 5.0:
            return
        self._log_lap(lap_time_s, self._lap_fuel.value())

    def _clear_laps(self):
        self._lap_data.clear()
        self._update_averages()
        self._result_main.setText("—")
        self._result_detail.setText("")

    def _on_mode_changed(self, laps_mode: bool):
        self._laps_row.setVisible(laps_mode)
        self._time_rows.setVisible(not laps_mode)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_lap(self, lap_time_s: float, fuel_used: float):
        self._lap_data.append((lap_time_s, fuel_used))
        self._update_averages()
        self._recalculate()

    def _update_averages(self):
        n = len(self._lap_data)
        self._count_label.setText(f"Laps: {n}")
        if n == 0:
            self._avg_time_label.setText("Avg time: —")
            self._avg_fuel_label.setText("Avg fuel: —")
            return
        avg_time = sum(t for t, _ in self._lap_data) / n
        avg_fuel = sum(f for _, f in self._lap_data) / n
        self._avg_time_label.setText(f"Avg time: {_fmt_time(avg_time)}")
        self._avg_fuel_label.setText(f"Avg fuel: {avg_fuel:.2f} L")

    def _recalculate(self):
        if not self._lap_data:
            self._result_main.setText("Add lap data first")
            self._result_detail.setText("")
            return

        n = len(self._lap_data)
        avg_time_s = sum(t for t, _ in self._lap_data) / n
        avg_fuel = sum(f for _, f in self._lap_data) / n

        if self._mode_laps.isChecked():
            race_laps = self._race_laps.value()
            base_fuel = avg_fuel * race_laps
            detail = f"{race_laps} laps × {avg_fuel:.2f} L/lap"
        else:
            race_secs = self._race_time_min.value() * 60.0
            race_laps = math.ceil(race_secs / avg_time_s)
            if self._plus_one_lap.isChecked():
                race_laps += 1
            base_fuel = avg_fuel * race_laps
            suffix = " (+1 lap)" if self._plus_one_lap.isChecked() else ""
            detail = (
                f"{self._race_time_min.value()} min{suffix} "
                f"≈ {race_laps} laps × {avg_fuel:.2f} L/lap"
            )

        recommended = base_fuel * (1.0 + _SAFETY_BUFFER)
        buffer_litres = recommended - base_fuel
        self._result_main.setText(f"{recommended:.1f} L")
        self._result_detail.setText(
            f"{detail}\n"
            f"+{int(_SAFETY_BUFFER * 100)}% safety buffer (+{buffer_litres:.2f} L)"
        )


# ------------------------------------------------------------------
# Widget helpers
# ------------------------------------------------------------------

def _section_header(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sectionHeader")
    return lbl


def _divider() -> QFrame:
    div = QFrame()
    div.setObjectName("divider")
    div.setFixedHeight(1)
    return div


def _small_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("fuelFieldLabel")
    return lbl


def _stat_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("fuelStatLabel")
    return lbl
