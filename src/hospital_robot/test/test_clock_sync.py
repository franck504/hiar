"""Horloge du Raspberry Pi recalée sur l'heure de la tablette."""

import json
import subprocess

import pytest

from hospital_robot.clock_sync import ClockGuard, client_epoch_seconds, describe_skew

ROBOT_NOW = 1_763_442_000.0          # 18/11/2026 (Pi déréglé)
TABLET_MS = int((ROBOT_NOW + 6 * 86400 + 3 * 3600) * 1000)   # tablette : 6 j 3 h plus tard


class Runner:
    def __init__(self, returncode=0, stderr=""):
        self.calls, self.returncode, self.stderr = [], returncode, stderr

    def __call__(self, cmd):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.returncode, "", self.stderr)


def guard(runner=None, enabled=True, now=ROBOT_NOW):
    return ClockGuard(enabled=enabled, now=lambda: now, runner=runner or Runner())


@pytest.mark.parametrize("ts,expected", [
    (1_763_442_000, 1_763_442_000.0),        # secondes
    (1_763_442_000_000, 1_763_442_000.0),    # millisecondes (Dart)
    (12345, None),                           # horodatage de test : ignoré
    (None, None), ("abc", None), (True, None),
    (5_000_000_000_000, None),               # an 2128 : invraisemblable
])
def test_client_epoch_seconds(ts, expected):
    assert client_epoch_seconds(ts) == expected


def test_describe_skew():
    assert describe_skew(6 * 86400 + 3 * 3600) == "en retard de 6 j 3 h"
    assert describe_skew(-240) == "en avance de 4 min"
    assert describe_skew(2 * 3600) == "en retard de 2 h"


def test_small_drift_is_ignored():
    r = Runner()
    g = guard(r)
    assert g.observe(int((ROBOT_NOW + 30) * 1000)) is None
    assert r.calls == [] and g.diagnostics()["status"] == "ok"


def test_large_skew_resyncs_the_pi_on_the_tablet_time():
    r = Runner()
    g = guard(r)
    note = g.observe(TABLET_MS)
    assert r.calls == [["sudo", "-n", "date", "-s", f"@{TABLET_MS // 1000}"]]
    assert "recalée" in note and "6 j 3 h" in note
    assert g.diagnostics()["status"] == "ok"


def test_no_resync_during_a_guidance_mission():
    r = Runner()
    note = guard(r).observe(TABLET_MS, mission_active=True)
    assert r.calls == [] and "reporté" in note


def test_resync_at_most_every_ten_minutes():
    r = Runner(returncode=1, stderr="sudo: a password is required")
    g = guard(r)
    g.observe(TABLET_MS)
    g.observe(TABLET_MS + 1000)
    assert len(r.calls) == 1


def test_refused_resync_is_reported_with_the_fix():
    g = guard(Runner(returncode=1, stderr="sudo: a password is required"))
    note = g.observe(TABLET_MS)
    assert "refusé" in note and "hiar_setup_clock.sh" in note
    diag = g.diagnostics()
    assert diag["status"] == "warn" and "6 j" in diag["detail"]


def test_disabled_guard_only_reports():
    r = Runner()
    note = guard(r, enabled=False).observe(TABLET_MS)
    assert r.calls == [] and "désactivé" in note


def test_bridge_measures_the_tablet_clock_from_websocket_frames():
    import asyncio
    from hospital_robot.hmi_websocket_bridge_node import HMIWebSocketBridgeNode

    node = HMIWebSocketBridgeNode(host="127.0.0.1", port=0)
    runner = Runner(returncode=1, stderr="refusé")
    node._clock = guard(runner)
    node._auth_required = False

    frame = {"v": 1, "type": "pub", "topic": "ui/state", "ts": TABLET_MS, "payload": {"screen": "home"}}
    asyncio.run(node._process_incoming_frame(None, json.dumps(frame)))

    assert len(runner.calls) == 1
    clock = node.build_system_diagnostics()["clock"]
    assert clock["status"] == "warn" and "robot_time" in clock
