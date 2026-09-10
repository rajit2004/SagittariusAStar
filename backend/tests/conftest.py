"""Shared test fixtures for backend tests."""

import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Mock google.generativeai ──────────────────────────────────────────────
class MockGemini:
    last_prompt = None
    last_config = None

    def __getattr__(self, name):
        return self

    def configure(self, *args, **kwargs):
        pass

    def GenerativeModel(self, *args, **kwargs):
        class MockModel:
            def generate_content(self, prompt, *args, **kwargs):
                MockGemini.last_prompt = prompt
                MockGemini.last_config = kwargs.get("generation_config")
                class MockResponse:
                    text = "Mock Gemini response"

                return MockResponse()

        return MockModel()


sys.modules.setdefault("google.generativeai", MockGemini())

os.environ["JWT_SECRET"] = os.environ.get("JWT_SECRET", "test-secret")
os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "mock-key")
os.environ["COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "false")

# ─── Mock firebase_admin ──────────────────────────────────────────────────
_existing = sys.modules.get("firebase_admin")
if isinstance(_existing, MagicMock):
    mock_firebase_admin = _existing
else:
    mock_firebase_admin = MagicMock(_apps={})
    sys.modules["firebase_admin"] = mock_firebase_admin
    sys.modules["firebase_admin.auth"] = mock_firebase_admin.auth
    sys.modules["firebase_admin.credentials"] = MagicMock()
    sys.modules["firebase_admin.firestore"] = MagicMock()


@pytest.fixture
def client():
    """Shared FastAPI test client."""
    from main import app
    return TestClient(app)
