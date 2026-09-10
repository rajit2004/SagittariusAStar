from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
from core.auth import create_access_token
from services.firestore_service import (
    CycleService,
    MockFirestoreClient,
    UserService,
)

import services.firestore_service as _fs_mod

client = TestClient(app)

LOG_URL = "/api/v1/cycle/log"
TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)

@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    monkeypatch.setattr(_fs_mod, "db", MockFirestoreClient())

@pytest.fixture
def account():
    user_id = UserService.create_user(
        {"email": "sana@example.com", "username": "sanakumar"}
    )
    token = create_access_token(data={"sub": user_id})
    return user_id, {"Authorization": f"Bearer {token}"}

def _post(headers, **payload):
    body = {"start_date": TODAY.isoformat(), **payload}
    response = client.post(LOG_URL, json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response

def _stored(user_id, headers, when=TODAY):
    response = client.get(
        f"/api/v1/cycle/{user_id}/history",
        params={"start_date": when.isoformat(), "end_date": when.isoformat()},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    entries = response.json()["entries"]
    assert len(entries) == 1, f"expected one entry, got {len(entries)}"
    return entries[0]

def test_a_null_removes_a_logged_value(account):
    user_id, headers = account
    _post(headers, flow_intensity="heavy")
    assert _stored(user_id, headers)["flow_intensity"] == "heavy"

    _post(headers, flow_intensity=None)

    assert _stored(user_id, headers).get("flow_intensity") is None

def test_clearing_one_field_leaves_the_rest_of_the_day_alone(account):
    user_id, headers = account
    _post(headers, flow_intensity="heavy", mood="sad", sleep_hours=8.0)

    _post(headers, flow_intensity=None)

    entry = _stored(user_id, headers)
    assert entry.get("flow_intensity") is None
    assert entry["mood"] == "sad"
    assert entry["sleep_hours"] == 8.0

def test_an_omitted_field_is_still_left_alone(account):
    user_id, headers = account
    _post(headers, flow_intensity="heavy", mood="sad")

    _post(headers, sleep_hours=7.0)

    entry = _stored(user_id, headers)
    assert entry["flow_intensity"] == "heavy"
    assert entry["mood"] == "sad"
    assert entry["sleep_hours"] == 7.0

def test_every_loggable_field_can_be_cleared(account):
    user_id, headers = account
    _post(
        headers,
        flow_intensity="heavy",
        mood="sad",
        sleep_hours=12.0,
        stress_level=5,
        symptoms=["cramps"],
        notes="mentioned it to Dr Rao",
    )

    _post(
        headers,
        flow_intensity=None,
        mood=None,
        sleep_hours=None,
        stress_level=None,
        symptoms=None,
        notes=None,
    )

    entry = _stored(user_id, headers)
    for field in (
        "flow_intensity",
        "mood",
        "sleep_hours",
        "stress_level",
        "symptoms",
        "notes",
    ):
        assert entry.get(field) is None, f"{field} survived a clearing"

def test_an_empty_symptom_list_clears_the_list(account):
    user_id, headers = account
    _post(headers, symptoms=["cramps", "headache"])

    _post(headers, symptoms=[])

    assert _stored(user_id, headers)["symptoms"] == []

def test_a_whitespace_only_note_clears_it(account):
    user_id, headers = account
    _post(headers, notes="took ibuprofen")

    _post(headers, notes="   ")

    assert _stored(user_id, headers).get("notes") is None

def test_clearing_a_field_that_was_never_logged_is_harmless(account):
    user_id, headers = account

    _post(headers, mood="happy", flow_intensity=None)

    entry = _stored(user_id, headers)
    assert entry["mood"] == "happy"
    assert entry.get("flow_intensity") is None

def test_a_cleared_value_does_not_come_back_as_a_sentinel(account):
    user_id, headers = account
    _post(headers, mood="sad")
    _post(headers, mood=None)

    raw = CycleService.get_log(user_id, f"{user_id}_{TODAY.isoformat()}")
    assert "mood" not in raw

def test_a_null_only_update_is_accepted_not_a_400(account):
    user_id, headers = account
    _post(headers, notes="mentioned it to Dr Rao")
    log_id = f"{user_id}_{TODAY.isoformat()}"

    response = client.put(
        f"/api/v1/cycle/{log_id}", json={"notes": None}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert _stored(user_id, headers).get("notes") is None

def test_an_empty_update_body_is_still_a_400(account):
    user_id, headers = account
    _post(headers, mood="sad")
    log_id = f"{user_id}_{TODAY.isoformat()}"

    response = client.put(f"/api/v1/cycle/{log_id}", json={}, headers=headers)

    assert response.status_code == 400
    assert "No fields provided" in response.json()["detail"]

def test_an_update_clears_one_field_and_leaves_the_others(account):
    user_id, headers = account
    _post(headers, mood="sad", stress_level=4, notes="rough day")
    log_id = f"{user_id}_{TODAY.isoformat()}"

    response = client.put(
        f"/api/v1/cycle/{log_id}", json={"stress_level": None}, headers=headers
    )

    assert response.status_code == 200, response.text
    entry = _stored(user_id, headers)
    assert entry.get("stress_level") is None
    assert entry["mood"] == "sad"
    assert entry["notes"] == "rough day"

def test_a_null_end_date_clears_it_without_a_range_check(account):
    user_id, headers = account
    _post(headers, end_date=TODAY.isoformat())
    log_id = f"{user_id}_{TODAY.isoformat()}"

    response = client.put(
        f"/api/v1/cycle/{log_id}", json={"end_date": None}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert _stored(user_id, headers).get("end_date") is None

def test_an_inverted_end_date_is_still_refused(account):
    user_id, headers = account
    _post(headers, mood="sad")
    log_id = f"{user_id}_{TODAY.isoformat()}"

    response = client.put(
        f"/api/v1/cycle/{log_id}",
        json={"end_date": (TODAY - timedelta(days=3)).isoformat()},
        headers=headers,
    )

    assert response.status_code == 422

def test_an_update_still_refuses_someone_elses_log(account):
    _, headers = account
    other_id = UserService.create_user({"email": "other@example.com"})
    CycleService.upsert_log(other_id, TODAY, {"mood": "happy"})

    response = client.put(
        f"/api/v1/cycle/{other_id}_{TODAY.isoformat()}",
        json={"mood": None},
        headers=headers,
    )

    assert response.status_code == 403

def test_an_out_of_range_value_is_still_refused(account):
    _, headers = account

    response = client.post(
        LOG_URL,
        json={"start_date": TODAY.isoformat(), "stress_level": 99},
        headers=headers,
    )

    assert response.status_code == 422

def test_an_unknown_flow_intensity_is_still_refused(account):
    _, headers = account

    response = client.post(
        LOG_URL,
        json={"start_date": TODAY.isoformat(), "flow_intensity": "torrential"},
        headers=headers,
    )

    assert response.status_code == 422

def test_the_mock_refuses_the_delete_sentinel_in_set():
    from google.cloud.firestore_v1 import DELETE_FIELD

    db = MockFirestoreClient()
    doc = db.collection("cycle_logs").document("new-doc")

    with pytest.raises(ValueError, match="DELETE_FIELD"):
        doc.set({"mood": DELETE_FIELD})

def test_the_mock_removes_a_key_rather_than_storing_the_sentinel():
    from google.cloud.firestore_v1 import DELETE_FIELD

    db = MockFirestoreClient()
    collection = db.collection("cycle_logs")
    collection.document("d").set({"mood": "sad", "notes": "keep me"})

    collection.document("d").update({"mood": DELETE_FIELD})

    stored = collection.document("d").get().to_dict()
    assert stored == {"notes": "keep me"}
