"""Configuration pytest des tests de l'interface web HIAR."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_appointments_db(tmp_path, monkeypatch):
    """Chaque test travaille sur une base SQLite temporaire, jamais sur la base réelle."""
    monkeypatch.setenv("HIAR_APPOINTMENTS_DB", str(tmp_path / "test_appointments.sqlite3"))
    yield
