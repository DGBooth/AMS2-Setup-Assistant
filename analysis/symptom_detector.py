"""
Rule-based symptom detection engine.

Takes a SmoothedSignals object and returns a list of active Symptom objects,
each carrying a severity level (LOW / MEDIUM / HIGH) and context values for
the suggestion engine.

All thresholds are imported from config.py — never hardcoded here.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto

from config import (
    FL, FR, RL, RR,
    ABS_LOW_SETTING_MAX,
    ABS_OVER_INTERVENTION_BRAKE,
    ABS_OVER_INTERVENTION_STEER,
    BRAKE_INPUT_MIN,
    BRAKE_TEMP_ASYMMETRY_C,
    CORNER_DETECT_STEER_MIN,
    CORNER_DETECT_LAT_G_MIN,
    CORNER_RESET_SAMPLES,
    CORNER_PEAK_LAT_G_MIN,
    EARLY_THROTTLE_LAT_G,
    EARLY_THROTTLE_MIN,
    EARLY_THROTTLE_STEER_MIN,
    LATE_BRAKE_INPUT_MIN,
    LATE_BRAKE_STEER_MIN,
    MIN_SPEED_CORNER_KPH,
    MIN_SPEED_TRACTION_KPH,
    OVERSTEER_STEERING_CORRECTION,
    OVERSTEER_YAW_EXCESS_RATIO,
    RIDE_HEIGHT_FLOOR_MM,
    SLOW_EXIT_MIN_SPEED_KPH,
    SLOW_EXIT_STEER_MAX,
    SLOW_EXIT_THROTTLE_MAX,
    SLOW_EXIT_WINDOW_SAMPLES,
    SUSPENSION_TRAVEL_MAXED_RATIO,
    TRACTION_SPIN_DELTA_RPS,
    TRACTION_THROTTLE_MIN,
    TYRE_OPTIMAL_HIGH_K,
    TYRE_OPTIMAL_LOW_K,
    TYRE_OVERHEAT_K,
    UNDERSTEER_LATERAL_G_LOW,
    UNDERSTEER_STEERING_THRESHOLD,
    UNDERSTEER_YAW_DEFICIT_RATIO,
    WHEEL_LOCK_BRAKE_MIN,
    WHEEL_LOCK_RPS_RATIO,
    WHEEL_RADIUS_M,
)
from analysis.signal_smoother import SmoothedSignals


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SymptomType(Enum):
    UNDERSTEER_ENTRY    = auto()
    UNDERSTEER_EXIT     = auto()
    OVERSTEER_ENTRY     = auto()
    OVERSTEER_EXIT      = auto()
    TRACTION_LOSS       = auto()
    BRAKE_INSTABILITY   = auto()
    TYRE_OVERHEATING    = auto()
    TYRE_UNDERTEMP      = auto()
    SUSPENSION_BOTTOMING= auto()
    WHEEL_LOCK          = auto()
    ABS_INSUFFICIENT    = auto()
    ABS_OVER_INTERVENTION = auto()
    OFF_TRACK           = auto()
    LATE_BRAKING        = auto()
    EARLY_THROTTLE      = auto()
    SLOW_CORNER_EXIT    = auto()


@dataclass
class Symptom:
    symptom_type: SymptomType
    severity: Severity
    context: dict = field(default_factory=dict)
    # context carries diagnostic values useful for AI prompts and display
    # e.g. {"yaw_deficit_ratio": 0.42, "speed_kph": 112.5}

    @property
    def label(self) -> str:
        return _LABELS.get(self.symptom_type, self.symptom_type.name)

    @property
    def severity_colour(self) -> str:
        """Returns a CSS colour string matching config palette."""
        return {
            Severity.HIGH:   "#ff4444",
            Severity.MEDIUM: "#ffaa00",
            Severity.LOW:    "#44aaff",
        }[self.severity]


_LABELS: dict[SymptomType, str] = {
    SymptomType.UNDERSTEER_ENTRY:     "Understeer (turn-in)",
    SymptomType.UNDERSTEER_EXIT:      "Understeer (exit)",
    SymptomType.OVERSTEER_ENTRY:      "Oversteer (entry)",
    SymptomType.OVERSTEER_EXIT:       "Oversteer (exit / snap)",
    SymptomType.TRACTION_LOSS:        "Traction loss",
    SymptomType.BRAKE_INSTABILITY:    "Brake instability",
    SymptomType.TYRE_OVERHEATING:     "Tyre overheating",
    SymptomType.TYRE_UNDERTEMP:       "Tyre undertemperature",
    SymptomType.SUSPENSION_BOTTOMING: "Suspension bottoming",
    SymptomType.WHEEL_LOCK:           "Wheel lock-up",
    SymptomType.ABS_INSUFFICIENT:     "ABS setting too low",
    SymptomType.ABS_OVER_INTERVENTION: "ABS too aggressive",
    SymptomType.OFF_TRACK:            "Off-track",
    SymptomType.LATE_BRAKING:         "Late braking (in-corner)",
    SymptomType.EARLY_THROTTLE:       "Early throttle (pre-apex)",
    SymptomType.SLOW_CORNER_EXIT:     "Slow corner exit (late throttle)",
}


class CornerTracker:
    """
    Lightweight state machine that tracks whether the car is currently in, or
    has recently exited, a corner.  Updated once per poll cycle by
    SymptomDetector before the technique checks run.

    A "corner" is defined as sustained steering + lateral G above threshold at
    racing speed.  The tracker records the peak lateral G reached so that
    trivial bends can be ignored when checking for slow exits.
    """

    def __init__(self) -> None:
        self._in_corner: bool = False
        self._samples_since_exit: int = 999   # large value = no recent corner
        self._peak_lat_g_current: float = 0.0  # accumulates while in corner
        self._peak_lat_g_last: float = 0.0     # snapshot from the corner just exited

    def update(self, sig: SmoothedSignals) -> None:
        steer_abs = abs(sig.steering)
        lat_g_abs = abs(sig.lateral_g)

        cornering_now = (
            steer_abs > CORNER_DETECT_STEER_MIN
            and lat_g_abs > CORNER_DETECT_LAT_G_MIN
            and sig.speed_kph > MIN_SPEED_CORNER_KPH
        )

        if cornering_now:
            if not self._in_corner:
                # Corner entry — reset current-corner accumulator
                self._peak_lat_g_current = 0.0
            self._in_corner = True
            self._samples_since_exit = 0
            self._peak_lat_g_current = max(self._peak_lat_g_current, lat_g_abs)
        else:
            if self._in_corner:
                # Transition: just left the corner
                self._in_corner = False
                self._peak_lat_g_last = self._peak_lat_g_current
                self._peak_lat_g_current = 0.0
                self._samples_since_exit = 1
            elif self._samples_since_exit < 999:
                self._samples_since_exit += 1
                if self._samples_since_exit > CORNER_RESET_SAMPLES:
                    # Corner fully complete — stop tracking this exit
                    self._samples_since_exit = 999

    @property
    def in_corner(self) -> bool:
        return self._in_corner

    @property
    def recently_exited(self) -> bool:
        """True for the first SLOW_EXIT_WINDOW_SAMPLES cycles after leaving a corner."""
        return 1 <= self._samples_since_exit <= SLOW_EXIT_WINDOW_SAMPLES

    @property
    def peak_lat_g_last(self) -> float:
        """Peak lateral G from the most recently completed corner."""
        return self._peak_lat_g_last


class SymptomDetector:
    """
    Rule evaluator.  Call detect() every poll cycle with the current
    SmoothedSignals and receive a (possibly empty) list of Symptoms.

    Maintains a CornerTracker instance to support timing-based technique
    checks that require state across multiple poll cycles.
    """

    def __init__(self) -> None:
        self._corner_tracker = CornerTracker()

    def detect(self, sig: SmoothedSignals) -> list[Symptom]:
        if not sig.game_running:
            return []

        # Update corner phase tracker before any technique checks
        self._corner_tracker.update(sig)

        symptoms: list[Symptom] = []

        symptoms.extend(self._check_understeer(sig))
        symptoms.extend(self._check_oversteer(sig))
        symptoms.extend(self._check_traction_loss(sig))
        symptoms.extend(self._check_brake_instability(sig))
        symptoms.extend(self._check_tyre_temps(sig))
        symptoms.extend(self._check_suspension(sig))
        symptoms.extend(self._check_wheel_lock(sig))
        symptoms.extend(self._check_abs_calibration(sig))
        symptoms.extend(self._check_off_track(sig))
        symptoms.extend(self._check_late_braking(sig))
        symptoms.extend(self._check_early_throttle(sig))
        symptoms.extend(self._check_slow_corner_exit(sig))

        return symptoms

    # ------------------------------------------------------------------
    # Individual rules
    # ------------------------------------------------------------------

    def _check_understeer(self, sig: SmoothedSignals) -> list[Symptom]:
        results = []

        if sig.speed_kph < MIN_SPEED_CORNER_KPH:
            return results

        steer_abs = abs(sig.steering)
        if steer_abs < UNDERSTEER_STEERING_THRESHOLD:
            return results   # not asking for much rotation

        expected = abs(sig.expected_yaw_rate)
        actual   = abs(sig.yaw_rate)

        # Entry understeer: high steering demand, yaw not following
        if expected > 0.05 and actual < expected * UNDERSTEER_YAW_DEFICIT_RATIO:
            ratio = actual / expected if expected > 0 else 0
            # Severity: worse deficit → higher severity
            if ratio < 0.35:
                sev = Severity.HIGH
            elif ratio < 0.50:
                sev = Severity.MEDIUM
            else:
                sev = Severity.LOW

            results.append(Symptom(
                symptom_type=SymptomType.UNDERSTEER_ENTRY,
                severity=sev,
                context={
                    "yaw_deficit_ratio": round(ratio, 2),
                    "speed_kph": round(sig.speed_kph, 1),
                    "steering": round(sig.steering, 2),
                },
            ))

        # Exit understeer: on throttle, understeer persists at low lateral G
        if (sig.throttle > 0.55
                and abs(sig.lateral_g) < UNDERSTEER_LATERAL_G_LOW
                and steer_abs > UNDERSTEER_STEERING_THRESHOLD):
            results.append(Symptom(
                symptom_type=SymptomType.UNDERSTEER_EXIT,
                severity=Severity.MEDIUM,
                context={
                    "lateral_g": round(sig.lateral_g, 2),
                    "throttle": round(sig.throttle, 2),
                    "speed_kph": round(sig.speed_kph, 1),
                },
            ))

        return results

    def _check_oversteer(self, sig: SmoothedSignals) -> list[Symptom]:
        results = []

        if sig.speed_kph < MIN_SPEED_CORNER_KPH:
            return results

        expected = abs(sig.expected_yaw_rate)
        actual   = abs(sig.yaw_rate)

        if expected < 0.05:
            return results  # straight line, not meaningful

        ratio = actual / expected if expected > 0 else 1.0

        if ratio > OVERSTEER_YAW_EXCESS_RATIO:
            # Check for counter-steer: steering input opposite to yaw direction
            yaw_sign   = 1 if sig.yaw_rate > 0 else -1
            steer_sign = 1 if sig.steering > 0 else -1
            counter_steering = (steer_sign != yaw_sign and
                                abs(sig.steering) > OVERSTEER_CORRECTION_GUARD())

            sev = Severity.HIGH if ratio > 1.8 else Severity.MEDIUM

            sym_type = (SymptomType.OVERSTEER_EXIT
                        if sig.throttle > 0.3
                        else SymptomType.OVERSTEER_ENTRY)

            results.append(Symptom(
                symptom_type=sym_type,
                severity=sev,
                context={
                    "yaw_excess_ratio": round(ratio, 2),
                    "counter_steering": counter_steering,
                    "throttle": round(sig.throttle, 2),
                    "speed_kph": round(sig.speed_kph, 1),
                },
            ))

        return results

    def _check_traction_loss(self, sig: SmoothedSignals) -> list[Symptom]:
        if sig.speed_kph < MIN_SPEED_TRACTION_KPH:
            return []
        if sig.unfiltered_throttle < TRACTION_THROTTLE_MIN:
            return []

        delta = sig.rear_spin_delta
        if delta > TRACTION_SPIN_DELTA_RPS:
            sev = Severity.HIGH if delta > TRACTION_SPIN_DELTA_RPS * 2 else Severity.MEDIUM
            return [Symptom(
                symptom_type=SymptomType.TRACTION_LOSS,
                severity=sev,
                context={
                    "spin_delta_rps": round(delta, 2),
                    "throttle": round(sig.unfiltered_throttle, 2),
                    "speed_kph": round(sig.speed_kph, 1),
                },
            )]
        return []

    def _check_brake_instability(self, sig: SmoothedSignals) -> list[Symptom]:
        if sig.unfiltered_brake < BRAKE_INPUT_MIN:
            return []
        if sig.speed_kph < MIN_SPEED_CORNER_KPH:
            return []

        # ABS firing while steering applied → instability
        abs_and_steer = sig.abs_active and abs(sig.steering) > 0.15

        # Asymmetric brake temps even when not braking hard → worn / seized caliper
        temp_asym = sig.brake_temp_left_right_delta > BRAKE_TEMP_ASYMMETRY_C

        if abs_and_steer or temp_asym:
            sev = Severity.HIGH if abs_and_steer and temp_asym else Severity.MEDIUM
            return [Symptom(
                symptom_type=SymptomType.BRAKE_INSTABILITY,
                severity=sev,
                context={
                    "abs_active": sig.abs_active,
                    "brake_temp_delta_c": round(sig.brake_temp_left_right_delta, 1),
                    "steering": round(sig.steering, 2),
                },
            )]
        return []

    def _check_tyre_temps(self, sig: SmoothedSignals) -> list[Symptom]:
        results = []
        overheating_wheels = []
        undertemp_wheels   = []

        for i, label in [(FL, "FL"), (FR, "FR"), (RL, "RL"), (RR, "RR")]:
            temp = sig.tyre_tread_temp_k[i]
            if temp > TYRE_OVERHEAT_K:
                overheating_wheels.append((label, temp))
            elif temp > TYRE_OPTIMAL_HIGH_K:
                overheating_wheels.append((label, temp))  # still flag as warning
            elif temp < TYRE_OPTIMAL_LOW_K and sig.speed_kph > MIN_SPEED_CORNER_KPH:
                undertemp_wheels.append((label, temp))

        if overheating_wheels:
            max_temp = max(t for _, t in overheating_wheels)
            sev = Severity.HIGH if max_temp > TYRE_OVERHEAT_K else Severity.MEDIUM
            results.append(Symptom(
                symptom_type=SymptomType.TYRE_OVERHEATING,
                severity=sev,
                context={
                    "wheels": [w for w, _ in overheating_wheels],
                    "max_temp_c": round(max_temp - 273.15, 1),
                },
            ))

        if undertemp_wheels:
            results.append(Symptom(
                symptom_type=SymptomType.TYRE_UNDERTEMP,
                severity=Severity.LOW,
                context={
                    "wheels": [w for w, _ in undertemp_wheels],
                    "min_temp_c": round(min(t for _, t in undertemp_wheels) - 273.15, 1),
                },
            ))

        return results

    def _check_suspension(self, sig: SmoothedSignals) -> list[Symptom]:
        results = []
        bottoming_corners = []

        for i, label in [(FL, "FL"), (FR, "FR"), (RL, "RL"), (RR, "RR")]:
            rh_mm = sig.ride_height[i] * 1000.0   # convert m → mm
            if rh_mm < RIDE_HEIGHT_FLOOR_MM:
                bottoming_corners.append(label)

        if bottoming_corners:
            sev = Severity.HIGH if len(bottoming_corners) >= 2 else Severity.MEDIUM
            results.append(Symptom(
                symptom_type=SymptomType.SUSPENSION_BOTTOMING,
                severity=sev,
                context={
                    "corners": bottoming_corners,
                    "min_ride_height_mm": round(
                        min(sig.ride_height[i] for i in [FL, FR, RL, RR]) * 1000, 1
                    ),
                },
            ))
        return results

    def _check_wheel_lock(self, sig: SmoothedSignals) -> list[Symptom]:
        if sig.speed_kph < MIN_SPEED_TRACTION_KPH:
            return []
        if sig.unfiltered_brake < WHEEL_LOCK_BRAKE_MIN:
            return []

        expected_rps = (sig.speed_kph / 3.6) / WHEEL_RADIUS_M
        if expected_rps < 5.0:
            return []

        locked = []
        for i, label in [(FL, "FL"), (FR, "FR"), (RL, "RL"), (RR, "RR")]:
            if abs(sig.tyre_rps[i]) < expected_rps * WHEEL_LOCK_RPS_RATIO:
                locked.append(label)

        if not locked:
            return []

        # ABS is active but still locking → report as insufficient rather than plain lock
        if sig.abs_active:
            abs_low = 0 < sig.abs_setting <= ABS_LOW_SETTING_MAX
            return [Symptom(
                symptom_type=SymptomType.ABS_INSUFFICIENT,
                severity=Severity.MEDIUM,
                context={
                    "locked_wheels": locked,
                    "abs_setting": sig.abs_setting,
                    "abs_setting_low": abs_low,
                    "speed_kph": round(sig.speed_kph, 1),
                },
            )]

        sev = Severity.HIGH if len(locked) >= 2 else Severity.MEDIUM
        return [Symptom(
            symptom_type=SymptomType.WHEEL_LOCK,
            severity=sev,
            context={
                "locked_wheels": locked,
                "speed_kph": round(sig.speed_kph, 1),
                "brake_input": round(sig.unfiltered_brake, 2),
            },
        )]

    def _check_abs_calibration(self, sig: SmoothedSignals) -> list[Symptom]:
        """Detect ABS intervening at unexpectedly low brake inputs on a straight."""
        if not sig.abs_active:
            return []
        if sig.speed_kph < MIN_SPEED_TRACTION_KPH:
            return []
        # Only flag over-intervention on near-straight braking
        if abs(sig.steering) > ABS_OVER_INTERVENTION_STEER:
            return []
        if sig.unfiltered_brake < ABS_OVER_INTERVENTION_BRAKE:
            return []
        # ABS firing at moderate brake with little steering → oversensitive
        return [Symptom(
            symptom_type=SymptomType.ABS_OVER_INTERVENTION,
            severity=Severity.LOW,
            context={
                "brake_input": round(sig.unfiltered_brake, 2),
                "abs_setting": sig.abs_setting,
                "speed_kph": round(sig.speed_kph, 1),
            },
        )]

    def _check_late_braking(self, sig: SmoothedSignals) -> list[Symptom]:
        """Detect braking hard while the car is already significantly steered.

        True late-braking technique (progressive trail-braking) gradually
        releases the brake as steering is added.  Simultaneous heavy brake and
        high steering input indicates panic braking into the corner, which
        overloads the front tyres and causes lock-up or push.
        """
        if sig.speed_kph < MIN_SPEED_CORNER_KPH:
            return []

        brake = sig.unfiltered_brake
        steer_abs = abs(sig.steering)

        if brake < LATE_BRAKE_INPUT_MIN or steer_abs < LATE_BRAKE_STEER_MIN:
            return []

        # Severity scales with how deeply both inputs overlap
        overlap = brake * steer_abs
        sev = Severity.HIGH if overlap > 0.40 else Severity.MEDIUM
        return [Symptom(
            symptom_type=SymptomType.LATE_BRAKING,
            severity=sev,
            context={
                "brake_input": round(brake, 2),
                "steering": round(sig.steering, 2),
                "overlap_index": round(overlap, 2),
                "speed_kph": round(sig.speed_kph, 1),
            },
        )]

    def _check_early_throttle(self, sig: SmoothedSignals) -> list[Symptom]:
        """Detect heavy throttle applied while the car is still mid-corner.

        Getting on the throttle hard before the apex shifts weight rearward
        while the car is still generating significant lateral force, destabilising
        the rear and causing oversteer or a wide exit.  Flags when throttle is
        high and lateral G confirms the car is still in the body of the corner.
        """
        if sig.speed_kph < MIN_SPEED_CORNER_KPH:
            return []

        throttle = sig.unfiltered_throttle
        lat_g_abs = abs(sig.lateral_g)
        steer_abs = abs(sig.steering)

        if (throttle < EARLY_THROTTLE_MIN
                or lat_g_abs < EARLY_THROTTLE_LAT_G
                or steer_abs < EARLY_THROTTLE_STEER_MIN):
            return []

        sev = Severity.HIGH if throttle > 0.80 and lat_g_abs > 1.0 else Severity.MEDIUM
        return [Symptom(
            symptom_type=SymptomType.EARLY_THROTTLE,
            severity=sev,
            context={
                "throttle": round(throttle, 2),
                "lateral_g": round(sig.lateral_g, 2),
                "steering": round(sig.steering, 2),
                "speed_kph": round(sig.speed_kph, 1),
            },
        )]

    def _check_slow_corner_exit(self, sig: SmoothedSignals) -> list[Symptom]:
        """Detect a missed exit — car is straight post-apex but driver is off throttle.

        After the apex, as steering unwinds and lateral G drops, the driver
        should be progressively increasing throttle.  Staying off the throttle
        while the car is essentially straight at speed loses significant time
        and may indicate fear of a setup-induced exit snap or traction problem.
        """
        if not self._corner_tracker.recently_exited:
            return []
        # Require the corner itself was significant (not a gentle motorway bend)
        if self._corner_tracker.peak_lat_g_last < CORNER_PEAK_LAT_G_MIN:
            return []
        if sig.speed_kph < SLOW_EXIT_MIN_SPEED_KPH:
            return []
        if abs(sig.steering) > SLOW_EXIT_STEER_MAX:
            return []   # car is still turning
        if sig.unfiltered_throttle > SLOW_EXIT_THROTTLE_MAX:
            return []   # driver is on it

        return [Symptom(
            symptom_type=SymptomType.SLOW_CORNER_EXIT,
            severity=Severity.LOW,
            context={
                "throttle": round(sig.unfiltered_throttle, 2),
                "steering": round(sig.steering, 2),
                "peak_lateral_g": round(self._corner_tracker.peak_lat_g_last, 2),
                "speed_kph": round(sig.speed_kph, 1),
            },
        )]

    def _check_off_track(self, sig: SmoothedSignals) -> list[Symptom]:
        # Terrain enum: any non-zero value indicates off the racing surface.
        # We defer to the raw snapshot via context — here we can only check
        # the smoothed signal so we use a simple heuristic: if all tyres
        # show the same non-zero terrain. This is a best-effort check.
        # For full accuracy, raw terrain values from the latest snapshot
        # should be used — the detector is called from the UI layer which
        # can pass both smoothed and raw if needed.
        return []   # placeholder; fully implemented via raw snapshot in main loop


# ---------------------------------------------------------------------------
# Private helper (avoids circular import of config constant)
# ---------------------------------------------------------------------------
def OVERSTEER_CORRECTION_GUARD() -> float:
    return OVERSTEER_STEERING_CORRECTION
