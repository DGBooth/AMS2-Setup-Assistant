"""
Global configuration: CREST2 connection, poll interval, and detection thresholds.
All tunable values live here — no magic numbers in the analysis or UI modules.
"""

# ---------------------------------------------------------------------------
# CREST2-AMS2 connection
# ---------------------------------------------------------------------------
CREST_BASE_URL = "http://localhost:8180/crest2/v1/api"
POLL_INTERVAL_MS = 500          # milliseconds between telemetry fetches
HTTP_TIMEOUT_S = 0.45           # single-request timeout (must be < poll interval)

# Single endpoint — CREST2 returns all sections in one call.
# Individual ?section=true queries are unreliable across versions.
CREST_ENDPOINT = ""

# ---------------------------------------------------------------------------
# Tyre wheel index order (consistent across all modules)
# FL=0  FR=1  RL=2  RR=3
# ---------------------------------------------------------------------------
FL, FR, RL, RR = 0, 1, 2, 3

# ---------------------------------------------------------------------------
# Signal smoother
# ---------------------------------------------------------------------------
SMOOTHER_WINDOW = 5             # samples (~2.5 s at 500 ms poll)

# ---------------------------------------------------------------------------
# Detection thresholds
# ---------------------------------------------------------------------------

# Speed gates — suppress suggestions at very low speed
MIN_SPEED_CORNER_KPH = 40       # minimum speed to flag cornering symptoms
MIN_SPEED_TRACTION_KPH = 20     # minimum speed to flag traction loss

# Understeer
UNDERSTEER_STEERING_THRESHOLD = 0.20    # normalised steering angle (−1…1) to consider "significant"
UNDERSTEER_YAW_DEFICIT_RATIO  = 0.70   # yaw_rate < expected_yaw * this ratio → understeer
UNDERSTEER_LATERAL_G_LOW      = 0.30   # lateral G below which front is not loaded (entry)

# Oversteer
OVERSTEER_YAW_EXCESS_RATIO    = 1.45   # yaw_rate > expected_yaw * this ratio → oversteer
OVERSTEER_STEERING_CORRECTION = 0.20   # counter-steer threshold (opposite lock applied)

# Traction loss
TRACTION_SPIN_DELTA_RPS       = 3.0    # rear wheel RPS excess over fronts → spin
TRACTION_THROTTLE_MIN         = 0.45   # only flag when driver is on throttle

# Brake instability
BRAKE_INPUT_MIN               = 0.55   # driver must be braking meaningfully
BRAKE_TEMP_ASYMMETRY_C        = 40.0   # L/R brake temp difference → instability

# Tyre temperatures (Kelvin — CREST reports Kelvin)
# Default window — used when the car class is not in TYRE_WINDOW_BY_CLASS
TYRE_OPTIMAL_LOW_K            = 333.15  # 60 °C  — below → undertemp
TYRE_OPTIMAL_HIGH_K           = 378.15  # 105 °C — above → overtemp (warning)
TYRE_OVERHEAT_K               = 388.15  # 115 °C — above → overheating (critical)
TYRE_UNDERTEMP_SUSTAINED      = 3       # consecutive samples below threshold to flag

# Per-class tyre temperature windows.
# Keys are lowercase substrings matched against mCarClassName (case-insensitive).
# Values are (optimal_low_°C, optimal_high_°C, overheat_°C).
# The first matching key wins, so list more-specific entries first.
_TYRE_WINDOW_BY_CLASS_C: dict[str, tuple[float, float, float]] = {
    "vintage":  (45.0,  80.0, 95.0),   # Formula Vintage, Group C Vintage, etc.
    "classic":  (50.0,  85.0, 100.0),  # Formula Classic, Classic GT
    "grupo a":  (55.0,  90.0, 105.0),  # Grupo A (touring, bias-ply)
    "copa truck": (60.0, 95.0, 110.0),
    "stock car": (60.0, 95.0, 110.0),
    "gt4":      (65.0, 100.0, 115.0),
    "gt3":      (70.0, 105.0, 120.0),
    "lmp":      (75.0, 110.0, 125.0),
    "formula":  (70.0, 105.0, 120.0),  # modern Formula (catch-all — must come after vintage/classic)
}

_KELVIN_OFFSET = 273.15


def get_tyre_window_k(car_class: str) -> tuple[float, float, float]:
    """Return (optimal_low_K, optimal_high_K, overheat_K) for *car_class*.

    Matches the first key in ``_TYRE_WINDOW_BY_CLASS_C`` that appears as a
    case-insensitive substring of *car_class*.  Falls back to the global
    defaults if no match is found.
    """
    lower = car_class.lower()
    for keyword, (lo_c, hi_c, oh_c) in _TYRE_WINDOW_BY_CLASS_C.items():
        if keyword in lower:
            return (lo_c + _KELVIN_OFFSET, hi_c + _KELVIN_OFFSET, oh_c + _KELVIN_OFFSET)
    return (TYRE_OPTIMAL_LOW_K, TYRE_OPTIMAL_HIGH_K, TYRE_OVERHEAT_K)

# Wheel lock (brake lock-up without ABS)
WHEEL_LOCK_BRAKE_MIN          = 0.30   # minimum brake input before checking for lock
WHEEL_LOCK_RPS_RATIO          = 0.15   # wheel RPS below this fraction of expected → locked
WHEEL_RADIUS_M                = 0.33   # assumed tyre radius for expected RPS calculation

# ABS calibration
ABS_LOW_SETTING_MAX           = 2      # settings at or below this are considered "low"
ABS_OVER_INTERVENTION_BRAKE   = 0.45  # ABS firing below this brake input → too aggressive
ABS_OVER_INTERVENTION_STEER   = 0.15  # ignore if driver is cornering (ABS in corner is normal)

# Corner phase tracking (used by CornerTracker)
CORNER_DETECT_STEER_MIN       = 0.25   # minimum steering to consider car "in corner"
CORNER_DETECT_LAT_G_MIN       = 0.40   # minimum lateral G to confirm cornering
CORNER_RESET_SAMPLES          = 8      # non-cornering samples before corner state fully resets
CORNER_PEAK_LAT_G_MIN         = 0.60   # minimum peak G for a corner to qualify as significant

# Late braking — braking hard while already significantly steered
LATE_BRAKE_INPUT_MIN          = 0.45   # minimum brake input to flag
LATE_BRAKE_STEER_MIN          = 0.30   # minimum steering confirming car is mid-corner

# Early throttle — throttle applied before the car reaches the apex
EARLY_THROTTLE_MIN            = 0.60   # minimum throttle to flag
EARLY_THROTTLE_LAT_G          = 0.75   # minimum lateral G confirming still mid-corner
EARLY_THROTTLE_STEER_MIN      = 0.25   # minimum steering confirming car is still turning

# Slow corner exit — car is straight post-apex but driver is not on throttle
SLOW_EXIT_THROTTLE_MAX        = 0.15   # throttle below this = missing the exit
SLOW_EXIT_STEER_MAX           = 0.15   # steering below this = car is straight
SLOW_EXIT_MIN_SPEED_KPH       = 60     # only flag at meaningful speeds
SLOW_EXIT_WINDOW_SAMPLES      = 3      # samples after corner exit to flag late throttle

# Suspension bottoming
SUSPENSION_TRAVEL_MAXED_RATIO = 0.92   # travel / max_travel above this → bottoming risk
RIDE_HEIGHT_FLOOR_MM          = 15.0   # mm — below this → touching down

# ---------------------------------------------------------------------------
# UI defaults
# ---------------------------------------------------------------------------
OVERLAY_OPACITY          = 0.82        # 0.0 (invisible) … 1.0 (opaque)
OVERLAY_WIDTH            = 380
OVERLAY_HEIGHT           = 480
OVERLAY_DEFAULT_X        = 40          # pixels from left
OVERLAY_DEFAULT_Y        = 40          # pixels from top
MAX_SUGGESTIONS_SHOWN    = 3           # top N suggestions per active symptom
SUGGESTION_COOLDOWN_S    = 8.0         # seconds before same suggestion repeats

# Colours (CSS strings used in QSS / painter)
COLOR_BG                 = "rgba(15, 15, 20, 210)"
COLOR_HEADER             = "#1a1a2e"
COLOR_CRITICAL           = "#ff4444"
COLOR_WARNING            = "#ffaa00"
COLOR_INFO               = "#44aaff"
COLOR_TEXT               = "#e8e8e8"
COLOR_SUBTEXT            = "#888888"
COLOR_ACCENT             = "#2d6a9f"

# ---------------------------------------------------------------------------
# AI mode
# ---------------------------------------------------------------------------
AI_MODEL                 = "claude-opus-4-6"
AI_MAX_TOKENS            = 600
