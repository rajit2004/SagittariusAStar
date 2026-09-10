import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import date

from main import app
from core.auth import get_current_user
import services.firestore_service as fs
from services.firestore_service import MockFirestoreClient, CycleService

fs.db = MockFirestoreClient()
db = fs.db

client = TestClient(app)

TEST_USER_ID = "test-user-id"
OTHER_USER_ID = "other-user-id"

def override_get_current_user():
    return {"id": TEST_USER_ID, "username": "testuser"}

@pytest.fixture(autouse=True)
def override_dependencies():
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def setup_db():

    db._collections = {}
    yield
    db._collections = {}

@pytest.fixture
def test_log_id():
    return CycleService.upsert_log(
        TEST_USER_ID,
        date(2026, 7, 24),
        {"flow_intensity": "medium", "mood": "happy"}
    )

@pytest.fixture
def other_user_log_id():
    return CycleService.upsert_log(
        OTHER_USER_ID,
        date(2026, 7, 24),
        {"flow_intensity": "light", "mood": "sad"}
    )

@pytest.fixture
def mock_cycle_service():
    with patch("api.cycle.CycleService") as MockCycleService:
        yield MockCycleService

def test_log_cycle_success(mock_cycle_service):
    mock_cycle_service.upsert_log.return_value = "log-123"
    payload = {
        "start_date": "2026-05-01",
        "flow_intensity": "medium",
        "symptoms": ["cramps"]
    }
    response = client.post("/api/v1/cycle/log", json=payload)
    assert response.status_code == 200
    assert response.json()["id"] == "log-123"

    assert response.json()["data"]["flow_intensity"] == "medium"

def test_log_cycle_missing_required_fields(mock_cycle_service):
    payload = {
        "flow_intensity": "medium"
    }
    response = client.post("/api/v1/cycle/log", json=payload)
    assert response.status_code == 422
    assert "start_date" in str(response.json()["detail"])

def test_log_cycle_invalid_dates(mock_cycle_service):
    payload = {
        "start_date": "not-a-date"
    }
    response = client.post("/api/v1/cycle/log", json=payload)
    assert response.status_code == 422
    assert "start_date" in str(response.json()["detail"])

def test_log_cycle_invalid_payload(mock_cycle_service):
    payload = {
        "start_date": "2026-05-01",
        "sleep_hours": "not-a-number"
    }
    response = client.post("/api/v1/cycle/log", json=payload)
    assert response.status_code == 422
    assert "sleep_hours" in str(response.json()["detail"])

def test_get_cycle_history_success(mock_cycle_service):
    mock_cycle_service.get_logs_page.return_value = (
        [{"id": "log-1", "start_date": "2026-05-01", "flow_intensity": "medium"}],
        False,
        1,
    )
    response = client.get(f"/api/v1/cycle/{TEST_USER_ID}/history")
    assert response.status_code == 200
    assert len(response.json()["entries"]) == 1
    mock_cycle_service.get_logs_page.assert_called_once_with(
        TEST_USER_ID, limit=20, offset=0, start_date=None, end_date=None
    )

def test_get_cycle_history_unauthorized(mock_cycle_service):
    response = client.get(f"/api/v1/cycle/{OTHER_USER_ID}/history")
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to view this user's data"

def test_get_cycle_history_empty_history(mock_cycle_service):
    mock_cycle_service.get_logs_page.return_value = ([], False, 0)
    response = client.get(f"/api/v1/cycle/{TEST_USER_ID}/history")
    assert response.status_code == 200
    assert len(response.json()["entries"]) == 0

def test_update_cycle_log_success(test_log_id):
    update_data = {
        "flow_intensity": "heavy",
        "notes": "Updated note"
    }
    response = client.put(f"/api/v1/cycle/{test_log_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == f"Cycle log {test_log_id} updated"

    doc = db.collection("cycle_logs").document(test_log_id).get()
    doc_data = doc.to_dict()
    assert doc_data["flow_intensity"] == "heavy"
    assert doc_data["notes"] == "Updated note"

    assert doc_data["mood"] == "happy"

def test_update_cycle_log_missing_log():
    update_data = {"flow_intensity": "heavy"}
    response = client.put("/api/v1/cycle/non-existent-id", json=update_data)

    assert response.status_code == 404
    assert response.json()["detail"] == "Cycle log not found"

def test_update_cycle_log_unauthorized(other_user_log_id):
    update_data = {"flow_intensity": "heavy"}
    response = client.put(f"/api/v1/cycle/{other_user_log_id}", json=update_data)

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this log"

def test_update_cycle_log_empty_payload(test_log_id):

    response = client.put(f"/api/v1/cycle/{test_log_id}", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "No fields provided for update"

def test_delete_cycle_log_success(test_log_id):
    response = client.delete(f"/api/v1/cycle/{test_log_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == f"Cycle log {test_log_id} deleted"

    doc = db.collection("cycle_logs").document(test_log_id).get()
    assert not doc.exists

def test_delete_cycle_log_missing_log():
    response = client.delete("/api/v1/cycle/non-existent-id")

    assert response.status_code == 404
    assert response.json()["detail"] == "Cycle log not found"

def test_delete_cycle_log_unauthorized(other_user_log_id):
    response = client.delete(f"/api/v1/cycle/{other_user_log_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to delete this log"
