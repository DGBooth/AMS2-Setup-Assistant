"""
Per-corner technique analysis.

Accumulates technique-relevant symptoms during each corner and emits a
CornerReport when the driver exits.  Coaching text is driver-focused —
what to do differently — not setup changes.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from analysis.signal_smoother import SmoothedSignals
from analysis.symptom_detector import Symptom, SymptomType
from config import (
    CORNER_DETECT_STEER_MIN,
    CORNER_DETECT_LAT_G_MIN,
    MIN_SPEED_CORNER_KPH,
    CORNER_PEAK_LAT_G_MIN,
    SLOW_EXIT_WINDOW_SAMPLES,
)

# Symptom types relevant to driving technique (captured by the analyzer)
TECHNIQUE_SYMPTOM_TYPES = frozenset({
    SymptomType.LATE_BRAKING,
    SymptomType.EARLY_THROTTLE,
    SymptomType.SLOW_CORNER_EXIT,
    SymptomType.UNDERSTEER_ENTRY,
    SymptomType.UNDERSTEER_EXIT,
    SymptomType.OVERSTEER_ENTRY,
    SymptomType.OVERSTEER_EXIT,
    SymptomType.TRACTION_LOSS,
})

# Symptom types that ONLY belong to technique coaching — filter these out of setup tab
PURE_TECHNIQUE_TYPES = frozenset({
    SymptomType.LATE_BRAKING,
    SymptomType.EARLY_THROTTLE,
    SymptomType.SLOW_CORNER_EXIT,
})

# Coaching text: driver-focused, not setup-focused.  Order matters — used to
# sort issues by priority in the report.
_COACHING: dict[SymptomType, str] = {
    SymptomType.LATE_BRAKING:     "Release brake as you add steering — overlapping inputs overloads the front tyres",
    SymptomType.EARLY_THROTTLE:   "Wait for the apex before full throttle — the car was still loaded laterally",
    SymptomType.UNDERSTEER_ENTRY: "Reduce speed into turn-in, or try a lighter, later brake application",
    SymptomType.UNDERSTEER_EXIT:  "Ease off the throttle until the car tracks out, then reapply progressively",
    SymptomType.OVERSTEER_ENTRY:  "Brake a touch earlier or more gently into this corner",
    SymptomType.OVERSTEER_EXIT:   "Squeeze the throttle on — be more progressive rather than stabbing it",
    SymptomType.TRACTION_LOSS:    "Apply throttle more gradually on exit — the rear is stepping out",
    SymptomType.SLOW_CORNER_EXIT: "Pick up the throttle sooner after the apex — you left time on the table",
}


@dataclass
class CornerReport:
    peak_lat_g: float
    max_speed_kph: float
    min_speed_kph: float
    issues: list[str]   # coaching sentences, in detection-priority order

    @property
    def had_issues(self) -> bool:
        return bool(self.issues)


class CornerAnalyzer:
    """
    Call update() every poll cycle with the current signals and symptom list.
    Returns a CornerReport when a corner finishes (after the slow-exit window
    so SLOW_CORNER_EXIT can be captured), otherwise returns None.
    """

    def __init__(self) -> None:
        self._in_corner = False
        self._post_corner_samples = 0
        self._reset_corner()

    def _reset_corner(self) -> None:
        self._peak_lat_g = 0.0
        self._max_speed_kph = 0.0
        self._min_speed_kph = 9999.0
        self._seen_types: set[SymptomType] = set()

    def update(self, sig: SmoothedSignals, symptoms: list[Symptom]) -> CornerReport | None:
        cornering_now = (
            abs(sig.steering) > CORNER_DETECT_STEER_MIN
            and abs(sig.lateral_g) > CORNER_DETECT_LAT_G_MIN
            and sig.speed_kph > MIN_SPEED_CORNER_KPH
        )

        if cornering_now:
            if not self._in_corner:
                # Corner entry — reset accumulators and cancel any pending post-corner window
                self._reset_corner()
                self._post_corner_samples = 0
            self._in_corner = True
            lat_g_abs = abs(sig.lateral_g)
            self._peak_lat_g = max(self._peak_lat_g, lat_g_abs)
            self._max_speed_kph = max(self._max_speed_kph, sig.speed_kph)
            self._min_speed_kph = min(self._min_speed_kph, sig.speed_kph)
            for s in symptoms:
                if s.symptom_type in TECHNIQUE_SYMPTOM_TYPES:
                    self._seen_types.add(s.symptom_type)
            return None

        # Not cornering
        if self._in_corner:
            # Corner just ended — start post-corner window to catch SLOW_CORNER_EXIT
            self._in_corner = False
            self._post_corner_samples = 1
            return None

        if 1 <= self._post_corner_samples <= SLOW_EXIT_WINDOW_SAMPLES:
            for s in symptoms:
                if s.symptom_type == SymptomType.SLOW_CORNER_EXIT:
                    self._seen_types.add(s.symptom_type)
            self._post_corner_samples += 1

            if self._post_corner_samples > SLOW_EXIT_WINDOW_SAMPLES:
                self._post_corner_samples = 0
                if self._peak_lat_g >= CORNER_PEAK_LAT_G_MIN:
                    issues = [_COACHING[t] for t in _COACHING if t in self._seen_types]
                    return CornerReport(
                        peak_lat_g=round(self._peak_lat_g, 2),
                        max_speed_kph=round(self._max_speed_kph, 1),
                        min_speed_kph=round(self._min_speed_kph, 1),
                        issues=issues,
                    )

        return None
