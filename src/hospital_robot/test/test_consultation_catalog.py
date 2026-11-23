"""Tests du catalogue de consultation et des analyseurs du dialogue vocal."""

import pytest

from hospital_robot import consultation_catalog as cat


# ---------------------------------------------------------------- médecins

def test_four_doctors_with_recognisable_names_and_fixed_periods():
    assert {c: d["name"] for c, d in cat.DOCTORS.items()} == {
        "A": "Raissa", "B": "Bell", "C": "Pierrot", "D": "Alice",
    }
    assert {c: d["period"] for c, d in cat.DOCTORS.items()} == {
        "A": "MAT", "B": "AM", "C": "MAT", "D": "AM",
    }
    assert cat.doctors_for_period("MAT") == ["A", "C"]
    assert cat.doctors_for_period("AM") == ["B", "D"]


def test_no_alias_shared_between_two_doctors():
    seen = {}
    for code, info in cat.DOCTORS.items():
        for alias in (info["name"].lower(), *info["aliases"]):
            assert seen.setdefault(alias, code) == code, f"{alias} ambigu"


@pytest.mark.parametrize("value,expected", [
    ("RAISSA", "A"), ("Raïssa", "A"), ("raisa", "A"), ("A", "A"), ("a", "A"),
    ("Bell", "B"), ("belle", "B"), ("Dr Bell", "B"), ("docteur Bell", "B"), ("MEDECIN B", "B"),
    ("Pierrot", "C"), ("le docteur Pierrot", "C"), ("pierro", "C"),
    ("Alice", "D"), ("alis", "D"), ("D", "D"),
    ("inconnu", None), ("", None), (None, None), ("E", None), ("Marie", None),
])
def test_resolve_doctor(value, expected):
    assert cat.resolve_doctor(value) == expected


@pytest.mark.parametrize("phrase,expected", [
    ("je veux le docteur Bell", ["B"]),
    ("Pierrot", ["C"]),
    ("avec Raïssa s'il vous plaît", ["A"]),
    ("médecin A", ["A"]),
    ("docteur d", ["D"]),
    ("médecin B le matin", ["B"]),
    ("Alice ou Pierrot", ["D", "C"]),            # ambigu : deux médecins cités
    ("le médecin a besoin de repos", []),         # « a » = verbe, pas le médecin A
    ("je voudrais une consultation", []),
])
def test_find_doctors_in_text(phrase, expected):
    # ordre d'apparition dans la phrase, sans doublon
    assert cat.find_doctors_in_text(phrase) == expected


def test_name_only_requires_title_outside_consultation():
    assert cat.find_doctors_in_text("Alice", name_only_ok=False) == []
    assert cat.find_doctors_in_text("docteur Alice", name_only_ok=False) == ["D"]


# ---------------------------------------------------------------- périodes / motifs

@pytest.mark.parametrize("value,expected", [
    ("MORNING", "MAT"), ("matin", "MAT"), ("MAT", "MAT"), ("AFTERNOON", "AM"),
    ("APRES_MIDI", "AM"), ("après-midi", "AM"), ("AM", "AM"), ("nuit", None), (None, None),
])
def test_resolve_period(value, expected):
    assert cat.resolve_period(value) == expected


@pytest.mark.parametrize("phrase,expected", [
    ("plutôt le matin", "MAT"), ("l'après-midi", "AM"), ("cet après midi", "AM"), ("demain", None),
])
def test_find_period_in_text(phrase, expected):
    assert cat.find_period_in_text(phrase) == expected


@pytest.mark.parametrize("value,expected", [
    ("CONSULTATION_GENERALE", "consultation_generale"), ("generale", "consultation_generale"),
    ("SUIVI_MEDICAL", "suivi_medical"), ("suivi", "suivi_medical"), ("suivi_medical", "suivi_medical"),
    ("AUTRE_MOTIF", "autre_motif"), ("autre", "autre_motif"),
    ("n'importe quoi", None), (None, None),
])
def test_resolve_reason(value, expected):
    assert cat.resolve_reason(value) == expected


# ---------------------------------------------------------------- formulaire

def test_form_from_both_key_families_and_first_missing_step():
    assert cat.first_missing_step(cat.form_from_data({})) == 1
    form = cat.form_from_data({"selected_reason": "suivi_medical"})
    assert cat.first_missing_step(form) == 2
    form = cat.form_from_data({"reason_code": "suivi_medical", "doctor_code": "b", "period": "AM"})
    assert form["doctor"] == "B" and cat.first_missing_step(form) == 3
    form = cat.form_from_data({"reason_code": "suivi_medical", "selected_doctor": "B", "selected_period": "AM",
                               "patient_name": "Jean", "contact": "0341234567"})
    assert cat.first_missing_step(form) is None
    assert cat.form_from_data({"doctor_code": "Z"})["doctor"] is None


def test_form_fields_only_contains_filled_values():
    form = cat.form_from_data({"selected_reason": "autre_motif", "doctor_code": "C", "period": "MAT"})
    assert cat.form_fields(form) == {
        "selected_reason": "autre_motif", "selected_doctor": "C", "selected_period": "MAT",
    }


def test_speeches_name_every_doctor_and_hold_no_personal_data():
    choice = cat.doctors_choice_speech()
    for name in ("Raissa", "Pierrot", "Bell", "Alice"):
        assert name in choice
    assert choice.index("Raissa") < choice.index("Bell")  # le matin avant l'après-midi
    recap = cat.recap_speech({"reason": "suivi_medical", "doctor": "B", "period": "AM",
                              "name": "Jean Dupont", "phone": "0341234567"})
    assert "docteur Bell" in recap and "suivi médical" in recap and "l'après-midi" in recap
    assert "Dupont" not in recap and "034" not in recap
    assert "Confirmer" in recap


# ---------------------------------------------------------------- téléphone dicté

@pytest.mark.parametrize("spoken,expected", [
    ("034 12 345 67", "0341234567"),
    ("0 3 4 1 2 3 4 5 6 7", "0341234567"),
    ("zéro trois quatre un deux trois quatre cinq six sept", "0341234567"),
    ("zéro trente-quatre douze trois cent quarante-cinq soixante-sept", "0341234567"),
    ("zéro trente quatre douze trois cent quarante cinq soixante sept", "0341234567"),
    ("mon numéro est le zéro trente-deux soixante-dix-sept quatre-vingt-dix-neuf cinquante-et-un vingt et un",
     "03277995121"),  # 0 | 32 | 77 | 99 | 51 | 21
    ("zéro trente-trois quatre-vingts quatre-vingt-un dix-sept dix-huit", "03380811718"),
    ("c'est le 034 12 puis 345 67", "0341234567"),
    ("bonjour merci", ""),
])
def test_spoken_to_digits(spoken, expected):
    assert cat.spoken_to_digits(spoken) == expected


def test_single_digits_are_not_added_together():
    # « trois quatre » = 3 puis 4, pas 7 ; « trente quatre » = 34
    assert cat.spoken_to_digits("trois quatre") == "34"
    assert cat.spoken_to_digits("trente quatre") == "34"
    assert cat.spoken_to_digits("deux cent cinq") == "205"
    assert cat.spoken_to_digits("cent") == "100"


@pytest.mark.parametrize("raw,expected", [
    ("0341234567", "0341234567"), ("034 12 345 67", "0341234567"),
    ("261341234567", "0341234567"), ("+261 34 12 345 67", "0341234567"),  # le « + » se perd à l'oral
    ("00261341234567", "0341234567"),
    ("034123456", None), ("03412345678", None), ("1341234567", None), ("", None),
])
def test_national_phone(raw, expected):
    assert cat.national_phone(raw) == expected


def test_phone_formats():
    assert cat.format_phone_display("0341234567") == "034 12 345 67"
    assert cat.format_phone_spoken("0341234567") == "0 3 4, 1 2, 3 4 5, 6 7"
    assert cat.format_phone_display("123") == "123"


# ---------------------------------------------------------------- nom dicté

@pytest.mark.parametrize("spoken,expected", [
    ("jean dupont", "Jean Dupont"),
    ("je m'appelle Jean-Pierre Dupont", "Jean-Pierre Dupont"),
    ("Je m’appelle marie de la croix, s'il vous plaît", "Marie de la Croix"),
    ("mon nom est Rakotondrasoa", "Rakotondrasoa"),
    ("c'est Alice Martin", "Alice Martin"),          # un patient peut s'appeler comme un médecin
    ("bonjour je suis Bell", "Bell"),
    ("O'Brien", "O'Brien"),
])
def test_clean_name_accepts_names(spoken, expected):
    assert cat.clean_name(spoken) == expected


@pytest.mark.parametrize("spoken", [
    "", "suivant", "précédent", "annuler", "oui", "non merci", "où est la pharmacie",
    "je veux voir un médecin", "suivi médical", "034 12 345 67", "jean 2", "mesurer mes constantes",
    "un deux trois quatre cinq six", "a b c d e f g",
])
def test_clean_name_rejects_commands_questions_and_numbers(spoken):
    assert cat.clean_name(spoken) is None


@pytest.mark.parametrize("spoken,expected", [
    ("suivant", "next"), ("Continuer", "next"), ("passer", "next"),
    ("précédent", "prev"), ("retour", "prev"), ("annuler", "cancel"), ("quitter", "cancel"),
    ("Jean Suivant", None), ("annuler mon rendez-vous", None), ("bonjour", None),
])
def test_closed_command(spoken, expected):
    assert cat.closed_command(spoken) == expected


@pytest.mark.parametrize("spoken,expected", [
    ("le nom", "name"), ("le prénom", "name"), ("le numéro", "phone"), ("le téléphone", "phone"),
    ("les deux", "both"), ("le nom et le numéro", "both"), ("rien", None),
])
def test_which_field_to_correct(spoken, expected):
    assert cat.which_field_to_correct(spoken) == expected
