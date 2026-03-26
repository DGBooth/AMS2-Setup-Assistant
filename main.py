"""
AMS2 Setup Advisor Overlay — entry point.

Wires together:
  CRESTClient → SignalSmoother → SymptomDetector → OverlayWindow

Run with --debug to print live signal values to the console each poll cycle.
Useful for verifying CREST2 field mappings (e.g. yaw rate index, tyre RPS scale).
"""

import sys
import os
import argparse

from PyQt5.QtCore import pyqtSlot, QObject, Qt
from PyQt5.QtWidgets import QApplication

from config import MAX_SUGGESTIONS_SHOWN, FL, FR, RL, RR
from data_layer.crest_client import CRESTClient
from data_layer.data_models import TelemetrySnapshot
from analysis.signal_smoother import SignalSmoother, SmoothedSignals
from analysis.symptom_detector import SymptomDetector, Symptom, Severity, SymptomType
from analysis.suggestion_table import get_suggestions
from ui.overlay_window import OverlayWindow

_SEVERITY_RANK = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}


def _print_debug(sig: SmoothedSignals, snap: TelemetrySnapshot) -> None:
    """Print a compact summary of smoothed signals plus raw vector components each tick."""
    temps = [round(t - 273.15, 1) for t in sig.tyre_tread_temp_k]
    av = snap.car_state.mAngularVelocity   # raw [x, y, z] — identify which is yaw
    la = snap.car_state.mLocalAcceleration # raw [x, y, z] — identify which is lateral
    print(
        f"[DBG] "
        f"spd={sig.speed_kph:5.1f}kph  "
        f"steer={sig.steering:+.2f}  "
        f"thr={sig.throttle:.2f}  brk={sig.brake:.2f}  "
        f"yaw={sig.yaw_rate:+.3f}rad/s  exp_yaw={sig.expected_yaw_rate:+.3f}  "
        f"lat_g={sig.lateral_g:+.2f}  "
        f"rps=[{sig.tyre_rps[FL]:.1f} {sig.tyre_rps[FR]:.1f} "
        f"{sig.tyre_rps[RL]:.1f} {sig.tyre_rps[RR]:.1f}]  "
        f"tread°C={temps}  "
        f"abs={int(sig.abs_active)} tc={int(sig.tc_active)}"
    )
    # Raw vector components — if all zeros the field name is wrong in the parser
    print(
        f"[RAW] "
        f"angVel[0]={av[0]:+.4f}  angVel[1]={av[1]:+.4f}  angVel[2]={av[2]:+.4f}  |  "
        f"localAccel[0]={la[0]:+.3f}  localAccel[1]={la[1]:+.3f}  localAccel[2]={la[2]:+.3f}"
    )


class App(QObject):
    """
    Controller that connects data pipeline to UI.
    Runs entirely on the Qt main thread via signals.
    """

    # Number of consecutive sub-5 kph samples before we consider the car back in garage
    _GARAGE_STATIONARY_SAMPLES = 6  # 3 s at 500 ms poll

    def __init__(self, debug: bool = False):
        super().__init__()
        self._debug = debug
        self._smoother = SignalSmoother()
        self._detector = SymptomDetector()
        self._last_snapshot: TelemetrySnapshot | None = None

        # Run / lap state
        self._run_started: bool = False          # True once car crosses start line
        self._stationary_samples: int = self._GARAGE_STATIONARY_SAMPLES  # start as "in garage"
        self._persisted_symptoms: dict[SymptomType, Symptom] = {}

        self._client = CRESTClient()
        self._window = OverlayWindow()

        # Wire signals
        self._client.data_ready.connect(self._on_data_ready)
        self._client.connection_changed.connect(self._on_connection_changed)

    def run(self):
        self._window.show()
        self._client.start()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot(object)
    def _on_data_ready(self, snapshot: TelemetrySnapshot):
        self._last_snapshot = snapshot
        self._window.update_snapshot(snapshot)

        if not snapshot.game_running:
            self._window.update_symptoms([])
            return

        self._update_run_state(snapshot)

        signals = self._smoother.update(snapshot)

        if self._debug:
            _print_debug(signals, snapshot)

        if self._run_started:
            symptoms = self._detector.detect(signals)

            if self._debug and symptoms:
                print(f"[DBG] >>> SYMPTOMS: {[s.symptom_type.name for s in symptoms]}")

            self._accumulate_symptoms(symptoms)

        self._window.update_symptoms(list(self._persisted_symptoms.values()))

    def _update_run_state(self, snapshot: TelemetrySnapshot) -> None:
        """Track garage exits and first-lap start to gate symptom collection."""
        if snapshot.speed_kph < 5.0:
            self._stationary_samples += 1
        else:
            if self._stationary_samples >= self._GARAGE_STATIONARY_SAMPLES:
                # Transitioned from garage → track: clear previous run's symptoms
                self._persisted_symptoms.clear()
                self._run_started = False
                if self._debug:
                    print("[DBG] Garage exit detected — symptom log cleared")
            self._stationary_samples = 0

        # Run begins once the car crosses the start/finish line (lap timer goes positive)
        if not self._run_started and snapshot.current_lap_time > 0:
            self._run_started = True
            if self._debug:
                print("[DBG] First lap started — symptom collection active")

    def _accumulate_symptoms(self, symptoms: list[Symptom]) -> None:
        """Merge new symptoms into the persisted log, keeping the worst severity seen."""
        for symptom in symptoms:
            existing = self._persisted_symptoms.get(symptom.symptom_type)
            if (existing is None or
                    _SEVERITY_RANK[symptom.severity] > _SEVERITY_RANK[existing.severity]):
                self._persisted_symptoms[symptom.symptom_type] = symptom

    @pyqtSlot(bool)
    def _on_connection_changed(self, connected: bool):
        state = "Connected to CREST2" if connected else "Waiting for CREST2..."
        print(f"[CREST2] {state}")

    def get_last_snapshot(self) -> TelemetrySnapshot | None:
        """Exposed for the AI dialog to include current telemetry in prompt."""
        return self._last_snapshot


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="AMS2 Setup Advisor Overlay")
    parser.add_argument(
        "--debug", action="store_true",
        help="Print live telemetry signal values to the console each poll cycle"
    )
    args = parser.parse_args()

    if args.debug:
        print("[DBG] Debug mode enabled — signal values will print every 500 ms")
        print("[DBG] Columns: speed | steer | throttle | brake | yaw | expected_yaw | "
              "lat_g | tyre_rps[FL FR RL RR] | tread_temps°C | abs | tc")

    # High-DPI support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("AMS2 Setup Advisor")
    app.setOrganizationName("AMS2SetupAdvisor")

    # Apply global stylesheet
    qss_path = os.path.join(os.path.dirname(__file__), "assets", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    controller = App(debug=args.debug)
    controller.run()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
