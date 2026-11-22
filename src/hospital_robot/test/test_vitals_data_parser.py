"""Tests unitaires pour le parseur de signes vitaux HIAR (ESP32 ➔ HMI)."""

import pytest
from hospital_robot.vitals_data_parser import (
    build_vitals_instruction,
    format_speech_fr,
    parse_vitals_frame,
    validate_vitals,
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
    assert "Mesure des constantes terminée" in text
    assert "36" not in text
    assert "72" not in text
    assert "98" not in text
    assert "degrés" not in text
    assert "battements" not in text
    assert "pour cent" not in text

    partial = format_speech_fr(37.0, 75, None)
    assert "Mesure des constantes terminée" in partial
    assert "37" not in partial
    assert "75" not in partial


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


def test_build_vitals_instruction_no_valid_measure():
    parsed = {"ok": False, "error": "NO_VALID_MEASURE"}
    instruction = build_vitals_instruction(parsed)

    assert instruction["instruction_ui"]["screen"] == "consultation"
    assert instruction["instruction_ui"]["step"] == 4
    assert instruction["value_to_show"]["value"] == "error"
    assert "fields" not in instruction
    assert "n'a pas pu aboutir" in instruction["text_to_speak"]


def test_validate_vitals_standalone():
    """Vérifie le validateur de sécurité des constantes vitales."""
    # 1. Valeurs valides
    t, hr, spo2, err = validate_vitals(37.2, 75, 98)
    assert t == 37.2
    assert hr == 75
    assert spo2 == 98
    assert err is None

    # 2. Valeurs hors-plages rejetées
    t_bad, hr_bad, spo2_bad, err_bad = validate_vitals(55.0, 290, 40)
    assert t_bad is None
    assert hr_bad is None
    assert spo2_bad is None
    assert "température" in err_bad
    assert "pouls" in err_bad
    assert "SpO2" in err_bad

    # 3. Valeurs None acceptées (facultatives)
    t_none, hr_none, spo2_none, err_none = validate_vitals(None, None, None)
    assert t_none is None and hr_none is None and spo2_none is None and err_none is None

