import pytest

import app as app_module
import vital_signs


class FakeSerial:
    def __init__(self, lines):
        self.lines = list(lines)
        self.written = []

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.written.append(data)

    def readline(self):
        if self.lines:
            return (self.lines.pop(0) + "\n").encode()
        return b""

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(vital_signs, "BOOT_WAIT_S", 0)
    monkeypatch.setattr(vital_signs, "TOTAL_TIMEOUT_S", 0.3)


def _use(monkeypatch, lines):
    fake = FakeSerial(lines)
    monkeypatch.setenv("HIAR_VITALS_PORT", "FAKE")
    monkeypatch.setattr(vital_signs, "_open_port", lambda port: fake)
    return fake


def test_no_port_configured_is_unavailable(monkeypatch):
    monkeypatch.delenv("HIAR_VITALS_PORT", raising=False)
    result = vital_signs.acquire()
    assert result["state"] == "indisponible"
    assert result["values"] == {
        "temperature_c": None,
        "heart_rate_bpm": None,
        "spo2_percent": None,
    }


def test_valid_measurement(monkeypatch):
    fake = _use(monkeypatch, [
        "STATE,RUNNING",
        "RESULT,temperature_c=36.6,heart_rate_bpm=72,spo2_percent=NA",
        "STATE,DONE",
    ])
    result = vital_signs.acquire()
    assert fake.written == [b"MEASURE\n"]
    assert result["state"] == "valide"
    assert result["values"]["temperature_c"] == 36.6
    assert result["values"]["heart_rate_bpm"] == 72
    assert result["values"]["spo2_percent"] is None
    assert result["measured_at"]


def test_spo2_is_never_reported_even_if_sent(monkeypatch):
    _use(monkeypatch, [
        "RESULT,temperature_c=36.6,heart_rate_bpm=72,spo2_percent=98",
    ])
    assert vital_signs.acquire()["values"]["spo2_percent"] is None


def test_all_na_is_unavailable(monkeypatch):
    _use(monkeypatch, [
        "RESULT,temperature_c=NA,heart_rate_bpm=NA,spo2_percent=NA",
    ])
    result = vital_signs.acquire()
    assert result["state"] == "indisponible"
    assert result["measured_at"] is None


def test_out_of_range_values_are_rejected(monkeypatch):
    _use(monkeypatch, [
        "RESULT,temperature_c=-127.0,heart_rate_bpm=300,spo2_percent=NA",
    ])
    assert vital_signs.acquire()["state"] == "indisponible"


def test_partial_measurement_keeps_missing_value_empty(monkeypatch):
    _use(monkeypatch, [
        "RESULT,temperature_c=36.4,heart_rate_bpm=NA,spo2_percent=NA",
    ])
    result = vital_signs.acquire()
    assert result["state"] == "valide"
    assert result["values"]["temperature_c"] == 36.4
    assert result["values"]["heart_rate_bpm"] is None


def test_firmware_error_is_unavailable(monkeypatch):
    _use(monkeypatch, ["ERROR,NO_SENSOR"])
    assert vital_signs.acquire()["state"] == "indisponible"


def test_no_answer_is_unavailable(monkeypatch):
    _use(monkeypatch, [])
    assert vital_signs.acquire()["state"] == "indisponible"


def test_port_open_failure_is_unavailable(monkeypatch):
    monkeypatch.setenv("HIAR_VITALS_PORT", "FAKE")

    def broken(port):
        raise OSError("absent")

    monkeypatch.setattr(vital_signs, "_open_port", broken)
    assert vital_signs.acquire()["state"] == "indisponible"


def test_route_returns_result_and_never_touches_robot(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Le robot ne doit pas être sollicité.")

    monkeypatch.setattr(app_module.bridge, "publish", forbidden)
    monkeypatch.setattr(
        app_module.bridge,
        "acquire_vitals",
        lambda timeout=35.0: {
            "ok": True,
            "request_id": "test-request",
            "line": "RESULT,temperature_c=36.6,heart_rate_bpm=72,spo2_percent=NA",
        },
    )

    response = app_module.app.test_client().post("/api/vitals/acquire")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["state"] == "valide"
    assert body["values"]["temperature_c"] == 36.6
    assert body["values"]["heart_rate_bpm"] == 72
    assert body["values"]["spo2_percent"] is None
