"""
CREST2-AMS2 polling client.

Fetches all data in a single request to the base URL every POLL_INTERVAL_MS
milliseconds. CREST2 returns all sections in one JSON response when called
with no query parameters, which is simpler and more reliable than querying
individual sections separately.
"""

import time
from typing import Optional

import requests
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal, pyqtSlot

from config import CREST_BASE_URL, CREST_ENDPOINT, HTTP_TIMEOUT_S, POLL_INTERVAL_MS
from data_layer.data_models import (
    TelemetrySnapshot,
    parse_car_state,
    parse_event_information,
    parse_motion,
    parse_timings,
    parse_unfiltered_inputs,
    parse_vehicle_information,
    parse_wheels_and_tyres,
)


class _FetchWorker(QRunnable):
    """Runs in a thread-pool thread; delivers results back via a callback."""

    def __init__(self, url: str, timeout: float, callback):
        super().__init__()
        self._url = url
        self._timeout = timeout
        self._callback = callback

    @pyqtSlot()
    def run(self):
        try:
            resp = requests.get(self._url, timeout=self._timeout)
            resp.raise_for_status()
            self._callback(resp.json(), None)
        except Exception as exc:
            self._callback(None, exc)


class CRESTClient(QObject):
    """
    Emits data_ready(TelemetrySnapshot) every poll cycle.
    Emits connection_changed(bool) when game connectivity changes.
    """

    data_ready = pyqtSignal(object)         # TelemetrySnapshot
    connection_changed = pyqtSignal(bool)   # True = connected, False = disconnected

    def __init__(self, parent=None):
        super().__init__(parent)
        self._url = CREST_BASE_URL + CREST_ENDPOINT
        self._pool = QThreadPool.globalInstance()
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._dispatch_fetch)
        self._connected: Optional[bool] = None  # None = unknown (first run)

        # Cache slow-changing data to avoid re-parsing on every tick
        self._vehicle_info = None
        self._event_info = None
        self._vehicle_poll_counter = 0
        self._VEHICLE_POLL_EVERY = 10       # refresh vehicle/event info every 5 s

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _dispatch_fetch(self):
        worker = _FetchWorker(
            url=self._url,
            timeout=HTTP_TIMEOUT_S,
            callback=self._on_fetch_complete,
        )
        self._pool.start(worker)

    def _on_fetch_complete(self, data: Optional[dict], error: Optional[Exception]):
        """Called from thread-pool thread — must only do thread-safe work."""
        if error is not None:
            self._set_connected(False)
            snapshot = TelemetrySnapshot(timestamp=time.monotonic(), game_running=False)
            self.data_ready.emit(snapshot)
            return

        self._set_connected(True)
        self._vehicle_poll_counter += 1
        if self._vehicle_poll_counter >= self._VEHICLE_POLL_EVERY or self._vehicle_info is None:
            self._vehicle_info = parse_vehicle_information(data)
            self._event_info = parse_event_information(data)
            self._vehicle_poll_counter = 0

        car_state = parse_car_state(data)
        motion = parse_motion(data)
        car_state.mOrientation       = motion["mOrientation"]
        car_state.mLocalVelocity     = motion["mLocalVelocity"]
        car_state.mAngularVelocity   = motion["mAngularVelocity"]
        car_state.mLocalAcceleration = motion["mLocalAcceleration"]

        timings = parse_timings(data)
        snapshot = TelemetrySnapshot(
            timestamp=time.monotonic(),
            car_state=car_state,
            wheels=parse_wheels_and_tyres(data),
            inputs=parse_unfiltered_inputs(data),
            vehicle_info=self._vehicle_info,
            event_info=self._event_info,
            game_running=True,
            current_lap_time=timings["current_lap_time"],
            last_lap_time=timings["last_lap_time"],
        )
        self.data_ready.emit(snapshot)

    def _set_connected(self, state: bool):
        if state != self._connected:
            self._connected = state
            self.connection_changed.emit(state)
