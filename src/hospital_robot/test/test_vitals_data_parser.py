"""Tests unitaires pour le parseur de signes vitaux HIAR (ESP32 ➔ HMI)."""

import pytest
from hospital_robot.vitals_data_parser import (
    build_vitals_instruction,
    format_speech_fr,
    parse_vitals_frame,
)


def test_parse_complete_vitals_frame():
    line = "RESULT,temperature_c=36.8,heart_rate_bpm=72,spo2_percent=98"
    parsed = parse_vitals_frame(line)

    assert parsed["ok"] is True
    assert parsed["temperature"] == 36.8
    assert parsed["heart_rate"] == 72
    assert parsed["spo2"] == 98


def test_parse_shorthand_keys():
    line = "RESULT,temp=37.1,bpm=80,spo2=97"
    parsed = parse_vitals_frame(line)

    assert parsed["ok"] is True
    assert parsed["temperature"] == 37.1
    assert parsed["heart_rate"] == 80
    assert parsed["spo2"] == 97


def test_parse_with_missing_spo2():
    line = "RESULT,temperature_c=36.5,heart_rate_bpm=65,spo2_percent=NA"
    parsed = parse_vitals_frame(line)

    assert parsed["ok"] is True
    assert parsed["temperature"] == 36.5
    assert parsed["heart_rate"] == 65
    assert parsed["spo2"] is None


def test_out_of_range_sensor_values_are_ignored():
    # Temp 15.0 trop basse, BPM 290 trop haut, SpO2 40 trop bas
    line = "RESULT,temperature_c=15.0,heart_rate_bpm=290,spo2_percent=40"
    parsed = parse_vitals_frame(line)

    assert parsed["ok"] is False
    assert parsed["error"] == "NO_VALID_MEASURE"


def test_parse_error_frames():
    timeout = parse_vitals_frame("ERROR,TIMEOUT")
    assert timeout["ok"] is False
    assert timeout["error"] == "TIMEOUT"

    busy = parse_vitals_frame("ERROR,BUSY")
    assert busy["ok"] is False
    assert busy["error"] == "BUSY"

    comm = parse_vitals_frame("ERROR,SERIAL_COMMUNICATION")
    assert comm["ok"] is False
    assert comm["error"] == "SERIAL_COMMUNICATION"


def test_format_speech_fr():
    text = format_speech_fr(36.8, 72, 98)
    assert "Température : 36 virgule 8 degrés." in text
    assert "Pouls : 72 battements par minute." in text
    assert "Oxygénation : 98 pour cent." in text

    partial = format_speech_fr(37.0, 75, None)
    assert "Température : 37 virgule 0 degrés." in partial
    assert "Pouls : 75 battements par minute." in partial
    assert "Oxygénation" not in partial


def test_build_vitals_instruction_success():
    parsed = {
        "ok": True,
        "temperature": 36.8,
        "heart_rate": 72,
        "spo2": 98,
    }
    instruction = build_vitals_instruction(parsed)

    assert instruction["instruction_ui"]["screen"] == "consultation"
    assert instruction["instruction_ui"]["step"] == 4
    assert instruction["instruction_ui"]["require_confirmation"] is False
    assert instruction["value_to_show"]["field_id"] == "vitals_state"
    assert instruction["value_to_show"]["value"] == "done"
    assert instruction["fields"]["temperature"] == 36.8
    assert instruction["fields"]["heart_rate"] == 72
    assert instruction["fields"]["spo2"] == 98
    assert instruction["fields"]["temperature_formatted"] == "36.8 °C"
    assert "Mesure des constantes terminée" in instruction["text_to_speak"]


def test_build_vitals_instruction_error():
    parsed = {"ok": False, "error": "TIMEOUT"}
    instruction = build_vitals_instruction(parsed)

    assert instruction["instruction_ui"]["screen"] == "consultation"
    assert instruction["instruction_ui"]["step"] == 4
    assert instruction["value_to_show"]["value"] == "error"
    assert "Délai dépassé" in instruction["text_to_speak"]
