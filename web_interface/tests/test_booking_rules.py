import threading

import pytest

import appointments_store as store

DAY = "2099-01-05"


@pytest.fixture
def booking_db(tmp_path, monkeypatch):
    monkeypatch.setenv("HIAR_APPOINTMENTS_DB", str(tmp_path / "t.sqlite3"))
    store.init_db()


def test_valid_booking_has_doctor_slot_and_queue_number(booking_db):
    store.create_appointment("A", "034 12 345 67", "toux", DAY, "09:00")
    appt = store.list_appointments()[0]
    assert appt["doctor"] == "Médecin B"
    assert appt["slot_id"] == 2
    assert appt["pass_number"] == 1
    assert appt["contact_normalized"] == "+261341234567"


@pytest.mark.parametrize(
    "raw",
    ["034 12 345 67", "+261 34 12 345 67", "261341234567"],
)
def test_phone_normalization(raw):
    assert store.normalize_phone(raw) == "+261341234567"


def test_invalid_phone_rejected(booking_db):
    with pytest.raises(store.BookingError) as exc:
        store.create_appointment("A", "abc", "toux", DAY, "08:00")
    assert exc.value.code == "invalid_phone"
    assert store.list_appointments() == []


def test_same_phone_same_day_rejected_any_format_any_slot(booking_db):
    store.create_appointment("A", "034 12 345 67", "toux", DAY, "08:00")
    with pytest.raises(store.BookingError) as exc:
        store.create_appointment(
            "B", "+261 34 12 345 67", "fièvre", DAY, "09:00"
        )
    assert exc.value.code == "duplicate_phone"


def test_same_phone_other_day_allowed(booking_db):
    store.create_appointment("A", "034 12 345 67", "toux", DAY, "08:00")
    store.create_appointment(
        "A", "034 12 345 67", "toux", "2099-01-06", "08:00"
    )
    assert len(store.list_appointments()) == 2


def test_slot_taken_and_invalid_slot(booking_db):
    store.create_appointment("A", "034 12 345 67", "toux", DAY, "08:00")
    with pytest.raises(store.BookingError) as exc:
        store.create_appointment("B", "033 11 111 11", "toux", DAY, "08:00")
    assert exc.value.code == "slot_taken"
    with pytest.raises(store.BookingError) as exc:
        store.create_appointment("C", "032 22 222 22", "toux", DAY, "12:00")
    assert exc.value.code == "invalid_slot"


def test_failed_booking_does_not_consume_queue_number(booking_db):
    store.create_appointment("A", "034 12 345 67", "toux", DAY, "08:00")
    with pytest.raises(store.BookingError):
        store.create_appointment("B", "034 12 345 67", "toux", DAY, "09:00")
    store.create_appointment("C", "033 11 111 11", "toux", DAY, "09:00")
    numbers = [a["pass_number"] for a in store.list_appointments()]
    assert numbers == [1, 2]


def test_list_slots_availability(booking_db):
    store.create_appointment("A", "034 12 345 67", "toux", DAY, "10:00")
    slots = {s["id"]: s for s in store.list_slots(DAY)}
    assert len(slots) == 4
    assert slots[3]["available"] is False
    assert slots[1]["available"] is True
    assert slots[3]["doctor"] == "Médecin A"


def _run_threads(args_list, func):
    results = []

    def worker(arg):
        try:
            func(arg)
            results.append("ok")
        except store.BookingError as exc:
            results.append(exc.code)

    threads = [threading.Thread(target=worker, args=(a,)) for a in args_list]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_concurrent_same_phone_only_one_succeeds(booking_db):
    results = _run_threads(
        ["08:00", "09:00", "10:00", "11:00"],
        lambda t: store.create_appointment(
            "P", "034 12 345 67", "toux", DAY, t
        ),
    )
    assert results.count("ok") == 1
    assert results.count("duplicate_phone") == 3


def test_concurrent_same_slot_only_one_succeeds(booking_db):
    phones = [
        "034 11 111 11",
        "033 22 222 22",
        "032 33 333 33",
        "034 44 444 44",
    ]
    results = _run_threads(
        phones,
        lambda p: store.create_appointment("P", p, "toux", DAY, "08:00"),
    )
    assert results.count("ok") == 1
    assert results.count("slot_taken") == 3
