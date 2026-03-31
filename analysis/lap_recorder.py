"""
Lap telemetry recorder.

Records throttle, brake, and speed samples indexed by track distance for each
lap.  Keeps the fastest completed lap as the session reference.  Call update()
every poll cycle and clear() on garage exit.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from data_layer.data_models import TelemetrySnapshot


@dataclass
class LapSample:
    distance: float     # metres along the track
    throttle: float     # 0–1 (unfiltered)
    brake: float        # 0–1 (unfiltered)
    speed_kph: float


@dataclass
class LapData:
    samples: list[LapSample] = field(default_factory=list)
    lap_time: float = 0.0   # seconds


class LapRecorder:
    """
    Records per-lap telemetry and tracks the session's reference (best) lap.

    Call update() every poll cycle.  Returns True when a new reference lap is
    set so the UI can react (e.g., flash the label).
    Call clear() on garage exit to start fresh.
    """

    def __init__(self) -> None:
        self._current_samples: list[LapSample] = []
        self._reference_lap: LapData | None = None
        self._best_time: float = float("inf")
        self._last_lap_time: float = -1.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, snapshot: TelemetrySnapshot) -> bool:
        """
        Process one telemetry snapshot.

        Returns True if a new (faster) reference lap was just set.
        """
        # Accumulate samples while on a timed lap with valid distance data
        if snapshot.current_lap_time > 0 and snapshot.lap_distance >= 0:
            self._current_samples.append(LapSample(
                distance=snapshot.lap_distance,
                throttle=snapshot.inputs.mUnfilteredThrottle,
                brake=snapshot.inputs.mUnfilteredBrake,
                speed_kph=snapshot.speed_kph,
            ))

        # Detect lap completion when last_lap_time changes
        new_best = False
        last = snapshot.last_lap_time
        if last > 0 and last != self._last_lap_time:
            self._last_lap_time = last
            if self._current_samples and last < self._best_time:
                self._best_time = last
                self._reference_lap = LapData(
                    samples=list(self._current_samples),
                    lap_time=last,
                )
                new_best = True
            self._current_samples.clear()

        return new_best

    def clear(self) -> None:
        """Reset all data on garage exit."""
        self._current_samples.clear()
        self._reference_lap = None
        self._best_time = float("inf")
        self._last_lap_time = -1.0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def reference_lap(self) -> LapData | None:
        return self._reference_lap

    @property
    def current_samples(self) -> list[LapSample]:
        return self._current_samples

    @property
    def best_lap_time(self) -> float:
        """Best lap time in seconds, or inf if no lap completed."""
        return self._best_time
