"""
Unit tests for the symptom detector.

Run with:  python -m pytest tests/ -v
No game or CREST2 server required.
"""

import pytest
from analysis.signal_smoother import SmoothedSignals
from analysis.symptom_detector import SymptomDetector, SymptomType, Severity


def _base_signals(**overrides) -> SmoothedSignals:
    """Build a SmoothedSignals with sane defaults, then apply overrides."""
    defaults = dict(
        speed_kph=120.0,
        yaw_rate=0.20,
        lateral_g=0.5,
        longitudinal_g=0.0,
        steering=0.20,
        throttle=0.5,
        brake=0.0,
        unfiltered_steering=0.20,
        unfiltered_throttle=0.5,
        unfiltered_brake=0.0,
        tyre_rps=[42.0, 42.0, 42.0, 42.0],
        tyre_grip=[0.95, 0.95, 0.95, 0.95],
        tyre_tread_temp_k=[358.15]*4,
        tyre_carcass_temp_k=[348.15]*4,
        brake_temp_c=[220.0, 220.0, 180.0, 180.0],
        suspension_travel=[0.025]*4,
        ride_height=[0.040]*4,
        abs_active=False,
        tc_active=False,
        game_running=True,
        car_class="",
    )
    defaults.update(overrides)
    return SmoothedSignals(**defaults)


@pytest.fixture
def detector():
    return SymptomDetector()


# ---------------------------------------------------------------------------
# Game not running
# ---------------------------------------------------------------------------

def test_no_symptoms_when_game_not_running(detector):
    sig = _base_signals(game_running=False)
    assert detector.detect(sig) == []


# ---------------------------------------------------------------------------
# Understeer
# ---------------------------------------------------------------------------

def test_understeer_entry_detected(detector):
    """High steering demand, low yaw rate → understeer entry."""
    sig = _base_signals(
        speed_kph=120.0,
        steering=0.55,              # heavy turn-in demand
        yaw_rate=0.05,              # very little yaw actually happening
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.UNDERSTEER_ENTRY in types


def test_understeer_not_at_low_speed(detector):
    sig = _base_signals(
        speed_kph=20.0,             # below MIN_SPEED_CORNER_KPH
        steering=0.60,
        yaw_rate=0.05,
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.UNDERSTEER_ENTRY not in types


def test_understeer_not_without_steering(detector):
    sig = _base_signals(
        speed_kph=120.0,
        steering=0.10,              # below UNDERSTEER_STEERING_THRESHOLD
        yaw_rate=0.10,
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.UNDERSTEER_ENTRY not in types


def test_understeer_severity_high(detector):
    sig = _base_signals(
        speed_kph=140.0,
        steering=0.65,
        yaw_rate=0.03,              # ratio < 0.35 → HIGH
    )
    symptoms = [s for s in detector.detect(sig) if s.symptom_type == SymptomType.UNDERSTEER_ENTRY]
    assert symptoms and symptoms[0].severity == Severity.HIGH


def test_understeer_exit_detected(detector):
    sig = _base_signals(
        speed_kph=80.0,
        steering=0.45,
        throttle=0.75,              # on throttle
        lateral_g=0.15,             # low lateral G
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.UNDERSTEER_EXIT in types


# ---------------------------------------------------------------------------
# Oversteer
# ---------------------------------------------------------------------------

def test_oversteer_exit_detected(detector):
    """Yaw rate much higher than expected, on throttle."""
    # At 80 kph, steering=0.10: expected yaw ≈ (22.2/2.6)*0.052 ≈ 0.44 rad/s
    # ratio = 1.1 / 0.44 ≈ 2.5 >> OVERSTEER_YAW_EXCESS_RATIO (1.45)
    sig = _base_signals(
        speed_kph=80.0,
        steering=0.10,              # modest steering angle
        yaw_rate=1.10,              # actual yaw >> expected
        throttle=0.70,
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.OVERSTEER_EXIT in types


# ---------------------------------------------------------------------------
# Traction loss
# ---------------------------------------------------------------------------

def test_traction_loss_detected(detector):
    sig = _base_signals(
        speed_kph=60.0,
        unfiltered_throttle=0.85,
        tyre_rps=[25.0, 25.0, 42.0, 45.0],   # rear spinning hard
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.TRACTION_LOSS in types


def test_traction_loss_not_off_throttle(detector):
    sig = _base_signals(
        speed_kph=60.0,
        unfiltered_throttle=0.20,   # below TRACTION_THROTTLE_MIN
        tyre_rps=[25.0, 25.0, 42.0, 45.0],
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.TRACTION_LOSS not in types


# ---------------------------------------------------------------------------
# Brake instability
# ---------------------------------------------------------------------------

def test_brake_instability_abs_and_steering(detector):
    sig = _base_signals(
        speed_kph=150.0,
        unfiltered_brake=0.90,
        steering=0.25,
        abs_active=True,
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.BRAKE_INSTABILITY in types


def test_brake_instability_temp_asymmetry(detector):
    sig = _base_signals(
        speed_kph=100.0,
        unfiltered_brake=0.70,
        brake_temp_c=[480.0, 300.0, 200.0, 200.0],  # 180°C FL/FR difference
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.BRAKE_INSTABILITY in types


# ---------------------------------------------------------------------------
# Tyre temperatures
# ---------------------------------------------------------------------------

def test_tyre_overheating_detected(detector):
    sig = _base_signals(
        tyre_tread_temp_k=[358.15, 358.15, 396.15, 399.15],  # rears over 115°C
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.TYRE_OVERHEATING in types


def test_tyre_undertemp_detected(detector):
    sig = _base_signals(
        speed_kph=80.0,
        tyre_tread_temp_k=[314.15, 312.15, 360.15, 360.15],  # fronts below 60°C
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.TYRE_UNDERTEMP in types


def test_tyre_undertemp_not_at_pit_speed(detector):
    sig = _base_signals(
        speed_kph=25.0,             # below MIN_SPEED_CORNER_KPH
        tyre_tread_temp_k=[314.15, 312.15, 360.15, 360.15],
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.TYRE_UNDERTEMP not in types


def test_vintage_class_lower_window_flags_undertemp(detector):
    # 55 °C (328.15 K) is above the default 60 °C threshold but below the
    # vintage window low of 45 °C — so it should NOT fire for vintage.
    # Use 40 °C (313.15 K) which is below the 45 °C vintage low.
    sig = _base_signals(
        speed_kph=80.0,
        car_class="Formula Vintage",
        tyre_tread_temp_k=[313.15]*4,  # 40 °C — below vintage low of 45 °C
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.TYRE_UNDERTEMP in types


def test_vintage_class_55c_not_undertemp(detector):
    # 55 °C sits inside the vintage window (45–80 °C) so should NOT flag.
    sig = _base_signals(
        speed_kph=80.0,
        car_class="Formula Vintage",
        tyre_tread_temp_k=[328.15]*4,  # 55 °C
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.TYRE_UNDERTEMP not in types


def test_default_class_55c_flags_undertemp(detector):
    # 55 °C is below the default 60 °C threshold, so with no car class set
    # it should still flag undertemp.
    sig = _base_signals(
        speed_kph=80.0,
        car_class="",
        tyre_tread_temp_k=[328.15]*4,  # 55 °C
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.TYRE_UNDERTEMP in types


# ---------------------------------------------------------------------------
# Suspension bottoming
# ---------------------------------------------------------------------------

def test_suspension_bottoming_detected(detector):
    sig = _base_signals(
        ride_height=[0.010, 0.011, 0.040, 0.040],  # fronts touching down
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.SUSPENSION_BOTTOMING in types


def test_no_bottoming_when_clear(detector):
    sig = _base_signals(
        ride_height=[0.040, 0.040, 0.042, 0.042],  # well above floor
    )
    symptoms = detector.detect(sig)
    types = [s.symptom_type for s in symptoms]
    assert SymptomType.SUSPENSION_BOTTOMING not in types


# ---------------------------------------------------------------------------
# Suggestion table integration
# ---------------------------------------------------------------------------

def test_suggestions_returned_for_all_symptoms(detector):
    from analysis.suggestion_table import get_suggestions
    from analysis.symptom_detector import SymptomType

    sig_understeer = _base_signals(speed_kph=120.0, steering=0.55, yaw_rate=0.05)
    symptoms = detector.detect(sig_understeer)
    assert symptoms, "Expected at least one symptom"

    for symptom in symptoms:
        suggestions = get_suggestions(symptom, max_count=3)
        assert len(suggestions) >= 1, f"No suggestions for {symptom.symptom_type}"
        assert all(s.title for s in suggestions), "Suggestion missing title"
