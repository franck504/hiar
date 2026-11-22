"""Tests unitaires pour le masquage des données sensibles RGPD."""

from hospital_robot.rgpd_masking import mask_patient_name, mask_phone_number


def test_mask_patient_name():
    assert mask_patient_name("Jean Dupont") == "J*** D***"
    assert mask_patient_name("Alice") == "A***"
    assert mask_patient_name("A B") == "A B"
    assert mask_patient_name("") == "—"
    assert mask_patient_name(None) == "—"


def test_mask_phone_number():
    assert mask_phone_number("0601020304") == "06****0304"
    assert mask_phone_number("+33612345678") == "+3****5678"
    assert mask_phone_number("1234") == "****"
    assert mask_phone_number("") == "—"
    assert mask_phone_number(None) == "—"
