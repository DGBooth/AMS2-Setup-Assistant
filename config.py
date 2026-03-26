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
TYRE_OPTIMAL_LOW_K            = 333.15  # 60 °C  — below → undertemp
TYRE_OPTIMAL_HIGH_K           = 378.15  # 105 °C — above → overtemp (warning)
TYRE_OVERHEAT_K               = 388.15  # 115 °C — above → overheating (critical)
TYRE_UNDERTEMP_SUSTAINED      = 3       # consecutive samples below threshold to flag

# Wheel lock (brake lock-up without ABS)
WHEEL_LOCK_BRAKE_MIN          = 0.30   # minimum brake input before checking for lock
WHEEL_LOCK_RPS_RATIO          = 0.15   # wheel RPS below this fraction of expected → locked
WHEEL_RADIUS_M                = 0.33   # assumed tyre radius for expected RPS calculation

# ABS calibration
ABS_LOW_SETTING_MAX           = 2      # settings at or below this are considered "low"
ABS_OVER_INTERVENTION_BRAKE   = 0.45  # ABS firing below this brake input → too aggressive
ABS_OVER_INTERVENTION_STEER   = 0.15  # ignore if driver is cornering (ABS in corner is normal)

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
