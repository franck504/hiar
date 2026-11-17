import re

from app import app

EMOJI = re.compile("[\u2600-\u27bf\U0001F300-\U0001FAFF]")


def test_home_page_has_new_flow_and_no_emoji():
    response = app.test_client().get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "login-panel" in html
    assert "queue-panel" in html
    assert "doctor.js" in html
    assert not EMOJI.search(html)


def test_static_files_are_served():
    client = app.test_client()
    assert client.get("/static/consultation.js").status_code == 200
    assert client.get("/static/consultation.css").status_code == 200
