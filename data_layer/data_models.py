"""
Typed dataclasses mirroring the CREST2-AMS2 JSON field names.

Wheel array index order (constant throughout the codebase):
    FL = 0   FR = 1   RL = 2   RR = 3

Temperature note:
    mTyreTreadTemp / mTyreCarcassTemp are reported in Kelvin by CREST2.
    They are stored here as-is in Kelvin. Convert at display time if needed.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CarState:
    mSpeed: float = 0.0                         # m/s
    mSteering: float = 0.0                      # −1 (full left) … +1 (full right), filtered
    mThrottle: float = 0.0                      # 0 … 1
    mBrake: float = 0.0                         # 0 … 1
    mGear: int = 0                              # 0=reverse, 1=neutral, 2+=drive gear
    mLocalAcceleration: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    # [0]=lateral, [1]=longitudinal, [2]=vertical  (m/s²)
    mLocalVelocity: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    # vehicle-frame velocity (m/s)
    mAngularVelocity: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    # [1] = yaw rate (rad/s)
    mAntiLockActive: bool = False
    mAntiLockSetting: int = -1              # -1 = unavailable; 0 = off; 1+ = active (higher = more aggressive)
    mTractionControlActive: bool = False
    mOrientation: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    # Euler angles: [0]=roll, [1]=pitch, [2]=yaw (radians)
    mEngineSpeed: float = 0.0                   # rpm
    mEngineTorque: float = 0.0                  # Nm
    mFuelCapacity: float = 0.0                  # litres — tank size
    mFuelLevel: float = 0.0                     # fraction of capacity (0.0 … 1.0)


@dataclass
class WheelsAndTyres:
    mTyreRPS: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    # Wheel spin rate [FL, FR, RL, RR] in rev/s (positive = forward)
    mTyreSlipSpeed: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    # Slip speed per wheel [FL, FR, RL, RR] in m/s (difference between tyre surface and ground speed)
    mTyreGrip: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0, 1.0])
    # Normalised grip level 0.0 (no grip) … 1.0 (full grip) per wheel
    mTyreTreadTemp: list[float] = field(default_factory=lambda: [293.15]*4)
    # Tread surface temperature per wheel [FL, FR, RL, RR] in KELVIN
    mTyreCarcassTemp: list[float] = field(default_factory=lambda: [293.15]*4)
    # Carcass temperature per wheel in KELVIN
    mBrakeTempCelsius: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    # Brake disc temperature [FL, FR, RL, RR] in Celsius
    mSuspensionTravel: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    # Suspension travel [FL, FR, RL, RR] in metres
    mSuspensionVelocity: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    # Rate of change of suspension travel (m/s)
    mRideHeight: list[float] = field(default_factory=lambda: [0.05, 0.05, 0.05, 0.05])
    # Ride height per corner in metres
    mTerrain: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    # Surface type enum per wheel; 0 = tarmac / paved


@dataclass
class UnfilteredInputs:
    mUnfilteredSteering: float = 0.0    # raw driver steering (−1 … +1)
    mUnfilteredThrottle: float = 0.0    # raw driver throttle (0 … 1)
    mUnfilteredBrake: float = 0.0       # raw driver brake (0 … 1)
    mUnfilteredClutch: float = 0.0      # raw driver clutch (0 … 1)


@dataclass
class VehicleInformation:
    mCarName: str = ""
    mCarClassName: str = ""


@dataclass
class EventInformation:
    mTrackLocation: str = ""
    mTrackVariation: str = ""
    mTrackLength: float = 0.0           # metres
    mSessionFastestLapTime: float = 0.0 # seconds


@dataclass
class TelemetrySnapshot:
    """One complete merged sample from all CREST2 endpoints."""
    timestamp: float = 0.0              # time.monotonic() at fetch time
    car_state: CarState = field(default_factory=CarState)
    wheels: WheelsAndTyres = field(default_factory=WheelsAndTyres)
    inputs: UnfilteredInputs = field(default_factory=UnfilteredInputs)
    vehicle_info: VehicleInformation = field(default_factory=VehicleInformation)
    event_info: EventInformation = field(default_factory=EventInformation)
    game_running: bool = False          # False when CREST2 is unreachable
    current_lap_time: float = -1.0     # seconds; -1 = not on a timed lap (pre-start-line)
    last_lap_time: float = -1.0        # seconds; -1 = no lap completed yet this session

    @property
    def fuel_litres(self) -> float:
        """Current fuel load in litres (level fraction × tank capacity)."""
        return self.car_state.mFuelLevel * self.car_state.mFuelCapacity

    @property
    def speed_kph(self) -> float:
        return self.car_state.mSpeed * 3.6

    @property
    def yaw_rate(self) -> float:
        """Yaw rate in rad/s (positive = turning right)."""
        return self.car_state.mAngularVelocity[1]

    @property
    def lateral_g(self) -> float:
        """Lateral acceleration in g (positive = right)."""
        return self.car_state.mLocalAcceleration[0] / 9.81

    @property
    def longitudinal_g(self) -> float:
        """Longitudinal acceleration in g (positive = forward)."""
        return self.car_state.mLocalAcceleration[1] / 9.81


def parse_car_state(data: dict) -> CarState:
    cs = data.get("carState", data)
    return CarState(
        mSpeed=float(cs.get("mSpeed", 0)),
        mSteering=float(cs.get("mSteering", 0)),
        mThrottle=float(cs.get("mThrottle", 0)),
        mBrake=float(cs.get("mBrake", 0)),
        mGear=int(cs.get("mGear", 0)),
        mLocalAcceleration=_float_list(cs.get("mLocalAcceleration", [0, 0, 0]), 3),
        mLocalVelocity=_float_list(cs.get("mLocalVelocity", [0, 0, 0]), 3),
        mAngularVelocity=_float_list(cs.get("mAngularVelocity", [0, 0, 0]), 3),
        mAntiLockActive=bool(cs.get("mAntiLockActive", False)),
        mAntiLockSetting=int(cs.get("mAntiLockSetting", -1)),
        mTractionControlActive=bool(cs.get("mTractionControlActive", False)),
        mOrientation=_float_list(cs.get("mOrientation", [0, 0, 0]), 3),
        mEngineSpeed=float(cs.get("mEngineSpeed", 0)),
        mEngineTorque=float(cs.get("mEngineTorque", 0)),
        mFuelCapacity=float(cs.get("mFuelCapacity", 0)),
        mFuelLevel=float(cs.get("mFuelLevel", 0)),
    )


def parse_wheels_and_tyres(data: dict) -> WheelsAndTyres:
    wt = data.get("wheelsAndTyres", data)
    return WheelsAndTyres(
        mTyreRPS=_float_list(wt.get("mTyreRPS", [0]*4), 4),
        mTyreSlipSpeed=_float_list(wt.get("mTyreSlipSpeed", [0]*4), 4),
        mTyreGrip=_float_list(wt.get("mTyreGrip", [1]*4), 4),
        mTyreTreadTemp=_float_list(wt.get("mTyreTreadTemp", [293.15]*4), 4),
        mTyreCarcassTemp=_float_list(wt.get("mTyreCarcassTemp", [293.15]*4), 4),
        mBrakeTempCelsius=_float_list(wt.get("mBrakeTempCelsius", [0]*4), 4),
        mSuspensionTravel=_float_list(wt.get("mSuspensionTravel", [0]*4), 4),
        mSuspensionVelocity=_float_list(wt.get("mSuspensionVelocity", [0]*4), 4),
        mRideHeight=_float_list(wt.get("mRideHeight", [0.05]*4), 4),
        mTerrain=_int_list(wt.get("mTerrain", [0]*4), 4),
    )


def parse_unfiltered_inputs(data: dict) -> UnfilteredInputs:
    # CREST2 wraps this as "unfilteredInput" (singular) in the response
    ui = data.get("unfilteredInputs", data.get("unfilteredInput", data))
    return UnfilteredInputs(
        mUnfilteredSteering=float(ui.get("mUnfilteredSteering", 0)),
        mUnfilteredThrottle=float(ui.get("mUnfilteredThrottle", 0)),
        mUnfilteredBrake=float(ui.get("mUnfilteredBrake", 0)),
        mUnfilteredClutch=float(ui.get("mUnfilteredClutch", 0)),
    )


def parse_vehicle_information(data: dict) -> VehicleInformation:
    vi = data.get("vehicleInformation", data)
    return VehicleInformation(
        mCarName=str(vi.get("mCarName", "")),
        mCarClassName=str(vi.get("mCarClassName", "")),
    )


def parse_timings(data: dict) -> dict:
    """Returns current and last lap time from the timings section."""
    t = data.get("timings", data)
    return {
        "current_lap_time": float(t.get("mCurrentTime", -1)),
        "last_lap_time":    float(t.get("mLastLapTime", -1)),
    }


def parse_motion(data: dict) -> dict:
    """
    Extracts motion vectors from the motionAndDeviceRelated endpoint.
    Returns a plain dict so the caller can merge fields into CarState.
    """
    md = data.get("motionAndDeviceRelated", data)
    return {
        "mOrientation":      _float_list(md.get("mOrientation",      [0, 0, 0]), 3),
        "mLocalVelocity":    _float_list(md.get("mLocalVelocity",    [0, 0, 0]), 3),
        "mAngularVelocity":  _float_list(md.get("mAngularVelocity",  [0, 0, 0]), 3),
        "mLocalAcceleration":_float_list(md.get("mLocalAcceleration",[0, 0, 0]), 3),
    }


def parse_event_information(data: dict) -> EventInformation:
    ei = data.get("eventInformation", data)
    return EventInformation(
        mTrackLocation=str(ei.get("mTrackLocation", "")),
        mTrackVariation=str(ei.get("mTrackVariation", "")),
        mTrackLength=float(ei.get("mTrackLength", 0)),
        mSessionFastestLapTime=float(ei.get("mSessionFastestLapTime", 0)),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _float_list(value, length: int) -> list[float]:
    if isinstance(value, (list, tuple)):
        result = [float(v) for v in value]
        while len(result) < length:
            result.append(0.0)
        return result[:length]
    return [float(value)] + [0.0] * (length - 1)


def _int_list(value, length: int) -> list[int]:
    if isinstance(value, (list, tuple)):
        result = [int(v) for v in value]
        while len(result) < length:
            result.append(0)
        return result[:length]
    return [int(value)] + [0] * (length - 1)
