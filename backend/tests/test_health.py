import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Rhythma API"
    assert data["status"] in ("ok", "degraded", "down")
    assert "ready" in data
