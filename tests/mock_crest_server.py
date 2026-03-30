"""
Mock CREST2-AMS2 HTTP server for development and testing.

Run this instead of the real game:
    python tests/mock_crest_server.py [--scenario understeer]

Available scenarios:
    idle          - car sitting still (default)
    understeer    - corner entry understeer
    oversteer     - snap oversteer on exit
    traction      - rear wheel spin
    braking       - brake instability
    tyre_hot      - overheating rear tyres
    tyre_cold     - undertemperature front tyres
    bottoming     - suspension bottoming

The server runs at http://localhost:8180/crest2/v1/api and responds to all
endpoint queries.
"""

import argparse
import json
import math
import time

from flask import Flask, jsonify, request

app = Flask(__name__)
_scenario = "idle"


# ---------------------------------------------------------------------------
# Scenario payloads
# ---------------------------------------------------------------------------

def _base():
    """Base telemetry — car cruising at 120 kph on track."""
    return {
        "carState": {
            "mSpeed": 33.3,          # ~120 kph
            "mSteering": 0.0,
            "mThrottle": 0.6,
            "mBrake": 0.0,
            "mGear": 4,
            "mLocalAcceleration": [0.5, 0.0, 9.81],
            "mLocalVelocity": [0.0, 33.3, 0.0],
            "mAngularVelocity": [0.0, 0.18, 0.0],
            "mAntiLockActive": False,
            "mTractionControlActive": False,
            "mOrientation": [0.0, 0.0, 0.0],
            "mEngineSpeed": 7200.0,
            "mEngineTorque": 280.0,
            "mFuelCapacity": 100.0,     # litres — typical GT/formula tank
            "mFuelLevel": 0.72,         # fraction of capacity (72 L remaining)
        },
        "wheelsAndTyres": {
            "mTyreRPS": [42.0, 42.0, 42.0, 42.0],
            "mTyreGrip": [0.95, 0.95, 0.95, 0.95],
            "mTyreTreadTemp": [358.15, 358.15, 363.15, 363.15],   # ~85°C / 90°C
            "mTyreCarcassTemp": [348.15, 348.15, 353.15, 353.15],
            "mBrakeTempCelsius": [220.0, 220.0, 180.0, 180.0],
            "mSuspensionTravel": [0.025, 0.025, 0.030, 0.030],
            "mSuspensionVelocity": [0.0, 0.0, 0.0, 0.0],
            "mRideHeight": [0.040, 0.040, 0.042, 0.042],
            "mTerrain": [0, 0, 0, 0],
        },
        "unfilteredInputs": {
            "mUnfilteredSteering": 0.0,
            "mUnfilteredThrottle": 0.6,
            "mUnfilteredBrake": 0.0,
            "mUnfilteredClutch": 0.0,
        },
        "vehicleInformation": {
            "mCarName": "Formula Reiza",
            "mCarClassName": "Formula V10",
        },
        "eventInformation": {
            "mTrackLocation": "Interlagos",
            "mTrackVariation": "Grand Prix",
            "mTrackLength": 4309.0,
            "mSessionFastestLapTime": 68.4,
        },
    }


SCENARIOS = {
    "idle": lambda: {
        **_base(),
        "carState": {**_base()["carState"],
            "mSpeed": 0.0,
            "mThrottle": 0.0,
            "mSteering": 0.0,
            "mAngularVelocity": [0.0, 0.0, 0.0],
        },
        "wheelsAndTyres": {**_base()["wheelsAndTyres"],
            "mTyreRPS": [0.0, 0.0, 0.0, 0.0],
        },
    },

    "understeer": lambda: {
        **_base(),
        "carState": {**_base()["carState"],
            "mSpeed": 33.3,
            "mSteering": 0.52,              # heavy steering demand
            "mThrottle": 0.1,
            "mBrake": 0.0,
            "mLocalAcceleration": [1.8, -2.5, 9.81],  # low lateral G for the steering
            "mAngularVelocity": [0.0, 0.12, 0.0],     # yaw rate far below expected
        },
        "unfilteredInputs": {**_base()["unfilteredInputs"],
            "mUnfilteredSteering": 0.54,
            "mUnfilteredThrottle": 0.1,
        },
    },

    "oversteer": lambda: {
        **_base(),
        "carState": {**_base()["carState"],
            "mSpeed": 22.0,              # ~79 kph, slow corner
            "mSteering": -0.12,          # slight right input
            "mThrottle": 0.65,
            "mLocalAcceleration": [-3.5, 1.2, 9.81],
            "mAngularVelocity": [0.0, -0.82, 0.0],  # yaw rate >> expected (left rotation)
        },
        "unfilteredInputs": {**_base()["unfilteredInputs"],
            "mUnfilteredSteering": -0.10,
            "mUnfilteredThrottle": 0.65,
        },
    },

    "traction": lambda: {
        **_base(),
        "carState": {**_base()["carState"],
            "mSpeed": 16.7,
            "mSteering": 0.15,
            "mThrottle": 0.85,
            "mAngularVelocity": [0.0, 0.20, 0.0],
        },
        "wheelsAndTyres": {**_base()["wheelsAndTyres"],
            "mTyreRPS": [25.0, 25.0, 42.0, 44.0],   # rears spinning significantly faster
            "mTyreGrip": [0.95, 0.95, 0.62, 0.58],
        },
        "unfilteredInputs": {**_base()["unfilteredInputs"],
            "mUnfilteredThrottle": 0.85,
            "mUnfilteredSteering": 0.15,
        },
    },

    "braking": lambda: {
        **_base(),
        "carState": {**_base()["carState"],
            "mSpeed": 44.4,              # 160 kph hard braking
            "mSteering": 0.18,
            "mThrottle": 0.0,
            "mBrake": 0.88,
            "mAntiLockActive": True,
            "mAngularVelocity": [0.0, 0.10, 0.0],
        },
        "wheelsAndTyres": {**_base()["wheelsAndTyres"],
            "mBrakeTempCelsius": [480.0, 310.0, 220.0, 220.0],  # FL much hotter
        },
        "unfilteredInputs": {**_base()["unfilteredInputs"],
            "mUnfilteredBrake": 0.88,
            "mUnfilteredSteering": 0.18,
        },
    },

    "tyre_hot": lambda: {
        **_base(),
        "wheelsAndTyres": {**_base()["wheelsAndTyres"],
            "mTyreTreadTemp": [355.15, 355.15, 396.15, 399.15],  # rears overheating
            "mTyreCarcassTemp": [345.15, 345.15, 385.15, 388.15],
        },
    },

    "tyre_cold": lambda: {
        **_base(),
        "wheelsAndTyres": {**_base()["wheelsAndTyres"],
            "mTyreTreadTemp": [314.15, 312.15, 363.15, 361.15],  # fronts under 60°C
            "mTyreCarcassTemp": [308.15, 307.15, 348.15, 346.15],
        },
    },

    "bottoming": lambda: {
        **_base(),
        "carState": {**_base()["carState"],
            "mSpeed": 55.5,             # fast compression
        },
        "wheelsAndTyres": {**_base()["wheelsAndTyres"],
            "mRideHeight": [0.012, 0.011, 0.014, 0.013],  # all very close to zero
            "mSuspensionTravel": [0.068, 0.070, 0.072, 0.071],
            "mSuspensionVelocity": [-0.8, -0.9, -0.7, -0.8],
        },
    },
}


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/crest2/v1/api")
def api():
    scenario_fn = SCENARIOS.get(_scenario, SCENARIOS["idle"])
    data = scenario_fn()

    # Add slight jitter to make it feel more like real telemetry
    t = time.time()
    cs = data["carState"]
    cs["mAngularVelocity"][1] += math.sin(t * 3.7) * 0.01
    cs["mLocalAcceleration"][0] += math.sin(t * 5.1) * 0.05

    # Route query to correct top-level key
    param_map = {
        "carState":          "carState",
        "wheelsAndTyres":    "wheelsAndTyres",
        "unfilteredInputs":  "unfilteredInputs",
        "vehicleInformation":"vehicleInformation",
        "eventInformation":  "eventInformation",
    }

    for param, key in param_map.items():
        if param in request.args:
            return jsonify({key: data[key]})

    # No specific param — return everything
    return jsonify(data)


@app.route("/scenario/<name>", methods=["POST"])
def set_scenario(name: str):
    global _scenario
    if name in SCENARIOS:
        _scenario = name
        return jsonify({"status": "ok", "scenario": _scenario})
    return jsonify({"status": "error", "message": f"Unknown scenario: {name}"}), 400


@app.route("/scenarios")
def list_scenarios():
    return jsonify(list(SCENARIOS.keys()))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock CREST2-AMS2 server")
    parser.add_argument(
        "--scenario", "-s",
        default="idle",
        choices=list(SCENARIOS.keys()),
        help="Initial telemetry scenario to serve",
    )
    parser.add_argument("--port", "-p", type=int, default=8180)
    args = parser.parse_args()

    _scenario = args.scenario
    print(f"[MockCREST] Starting on http://localhost:{args.port}")
    print(f"[MockCREST] Scenario: {_scenario}")
    print(f"[MockCREST] Change scenario: POST http://localhost:{args.port}/scenario/<name>")
    print(f"[MockCREST] Available:  {', '.join(SCENARIOS.keys())}")

    app.run(host="0.0.0.0", port=args.port, debug=False)
