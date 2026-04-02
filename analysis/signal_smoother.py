"""
Rolling-average smoother over the last N telemetry snapshots.

Keeps a circular buffer and exposes a SmoothedSignals object with
pre-computed averages used by the symptom detector.  This eliminates
single-frame noise (kerbs, bumps, sensor spikes) without adding latency
worse than (N × poll_interval) ≈ 2.5 s.
"""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field

from config import FL, FR, RL, RR, SMOOTHER_WINDOW
from data_layer.data_models import TelemetrySnapshot


@dataclass
class SmoothedSignals:
    """Averaged / processed signals ready for rule evaluation."""

    # ---- Dynamics ----
    speed_kph: float = 0.0
    yaw_rate: float = 0.0           # rad/s  (positive = right)
    lateral_g: float = 0.0          # g
    longitudinal_g: float = 0.0     # g

    # ---- Driver inputs ----
    steering: float = 0.0           # filtered steering (−1…+1)
    throttle: float = 0.0
    brake: float = 0.0
    unfiltered_steering: float = 0.0
    unfiltered_throttle: float = 0.0
    unfiltered_brake: float = 0.0

    # ---- Tyres ----
    tyre_rps: list[float] = field(default_factory=lambda: [0.0]*4)       # per wheel
    tyre_slip_speed: list[float] = field(default_factory=lambda: [0.0]*4)  # m/s per wheel
    tyre_grip: list[float] = field(default_factory=lambda: [1.0]*4)
    tyre_tread_temp_k: list[float] = field(default_factory=lambda: [293.15]*4)  # Kelvin
    tyre_carcass_temp_k: list[float] = field(default_factory=lambda: [293.15]*4)

    # ---- Brakes ----
    brake_temp_c: list[float] = field(default_factory=lambda: [0.0]*4)   # Celsius

    # ---- Suspension ----
    suspension_travel: list[float] = field(default_factory=lambda: [0.0]*4)  # metres
    ride_height: list[float] = field(default_factory=lambda: [0.05]*4)      # metres

    # ---- Flags / settings (most-recent sample, not averaged) ----
    abs_active: bool = False
    abs_setting: int = -1               # -1 = unavailable; 0 = off; 1+ = active level
    tc_active: bool = False
    game_running: bool = False

    # ---- Vehicle identity (most-recent sample, not averaged) ----
    car_class: str = ""                 # mCarClassName from CREST2 — used for per-class thresholds

    # ---- Derived convenience ----
    @property
    def rear_spin_delta(self) -> float:
        """Rear wheel RPS minus front wheel RPS average (positive = rears spinning faster).

        Uses absolute values because CREST2 reports RPS as negative for forward rotation.
        """
        front_avg = (abs(self.tyre_rps[FL]) + abs(self.tyre_rps[FR])) / 2.0
        rear_avg  = (abs(self.tyre_rps[RL]) + abs(self.tyre_rps[RR])) / 2.0
        return rear_avg - front_avg

    @property
    def brake_temp_left_right_delta(self) -> float:
        """Max left-right brake temperature difference across axles."""
        front_delta = abs(self.brake_temp_c[FL] - self.brake_temp_c[FR])
        rear_delta  = abs(self.brake_temp_c[RL] - self.brake_temp_c[RR])
        return max(front_delta, rear_delta)

    @property
    def expected_yaw_rate(self) -> float:
        """
        Bicycle-model estimate of yaw rate from speed and steering.
        Used to gauge whether actual yaw is under or over expected.

        Returns rad/s.  Wheelbase assumed 2.6 m as a reasonable default —
        the actual value affects only the threshold calibration, not the
        direction of the symptom.
        """
        WHEELBASE = 2.6  # metres
        # Convert speed to m/s
        speed_ms = self.speed_kph / 3.6
        if speed_ms < 1.0:
            return 0.0
        # Simplified: yaw = (speed / wheelbase) * sin(steer_angle)
        # For small angles: sin(x) ≈ x, steer ∈ [−1, 1] maps to ~30° max lock
        MAX_STEER_RAD = 0.52  # ~30 degrees
        steer_rad = self.steering * MAX_STEER_RAD
        return (speed_ms / WHEELBASE) * steer_rad


class SignalSmoother:
    """
    Maintains a circular buffer of TelemetrySnapshot objects and
    computes SmoothedSignals on each update call.
    """

    def __init__(self, window: int = SMOOTHER_WINDOW):
        self._window = window
        self._buffer: deque[TelemetrySnapshot] = deque(maxlen=window)

    def update(self, snapshot: TelemetrySnapshot) -> SmoothedSignals:
        self._buffer.append(snapshot)
        return self._compute()

    def _compute(self) -> SmoothedSignals:
        buf = list(self._buffer)
        n = len(buf)
        if n == 0:
            return SmoothedSignals()

        def avg_scalar(getter) -> float:
            return sum(getter(s) for s in buf) / n

        def avg_list(getter, length: int) -> list[float]:
            totals = [0.0] * length
            for s in buf:
                vals = getter(s)
                for i in range(length):
                    totals[i] += vals[i]
            return [t / n for t in totals]

        latest = buf[-1]

        return SmoothedSignals(
            speed_kph=avg_scalar(lambda s: s.speed_kph),
            yaw_rate=avg_scalar(lambda s: s.yaw_rate),
            lateral_g=avg_scalar(lambda s: s.lateral_g),
            longitudinal_g=avg_scalar(lambda s: s.longitudinal_g),

            steering=avg_scalar(lambda s: s.car_state.mSteering),
            throttle=avg_scalar(lambda s: s.car_state.mThrottle),
            brake=avg_scalar(lambda s: s.car_state.mBrake),
            unfiltered_steering=avg_scalar(lambda s: s.inputs.mUnfilteredSteering),
            unfiltered_throttle=avg_scalar(lambda s: s.inputs.mUnfilteredThrottle),
            unfiltered_brake=avg_scalar(lambda s: s.inputs.mUnfilteredBrake),

            tyre_rps=avg_list(lambda s: s.wheels.mTyreRPS, 4),
            tyre_slip_speed=avg_list(lambda s: s.wheels.mTyreSlipSpeed, 4),
            tyre_grip=avg_list(lambda s: s.wheels.mTyreGrip, 4),
            tyre_tread_temp_k=avg_list(lambda s: s.wheels.mTyreTreadTemp, 4),
            tyre_carcass_temp_k=avg_list(lambda s: s.wheels.mTyreCarcassTemp, 4),
            brake_temp_c=avg_list(lambda s: s.wheels.mBrakeTempCelsius, 4),
            suspension_travel=avg_list(lambda s: s.wheels.mSuspensionTravel, 4),
            ride_height=avg_list(lambda s: s.wheels.mRideHeight, 4),

            abs_active=latest.car_state.mAntiLockActive,
            abs_setting=latest.car_state.mAntiLockSetting,
            tc_active=latest.car_state.mTractionControlActive,
            game_running=latest.game_running,
            car_class=latest.vehicle_info.mCarClassName,
        )
