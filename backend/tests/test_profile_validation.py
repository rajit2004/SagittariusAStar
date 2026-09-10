from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from fastapi.testclient import TestClient

from core.profile_validation import (
    FUTURE_GRACE_DAYS,
    MAX_LAST_PERIOD_AGE_DAYS,
    normalize_last_period,
)
from main import app
from models.user import UserProfileUpdate
from services import prediction_service

client = TestClient(app)

def _today() -> date:
    return datetime.now(timezone.utc).date()

def test_a_bare_date_is_accepted_unchanged():
    assert normalize_last_period("2026-06-01") == "2026-06-01"

def test_surrounding_whitespace_does_not_change_the_answer():
    assert normalize_last_period("  2026-06-01 ") == "2026-06-01"

@pytest.mark.parametrize(
    "sent",
    [
        "2026-06-01T00:00:00",
        "2026-06-01T09:30:00Z",
        "2026-06-01T09:30:00z",
        "2026-06-01T09:30:00+05:30",
        "2026-06-01T09:30:00.123456Z",
    ],
)
def test_a_timestamp_is_reduced_to_its_date(sent):
    assert normalize_last_period(sent) == "2026-06-01"

def test_the_basic_iso_form_is_accepted():
    assert normalize_last_period("20260601") == "2026-06-01"

def test_a_date_object_is_accepted():
    assert normalize_last_period(date(2026, 6, 1)) == "2026-06-01"

def test_a_datetime_object_is_reduced_to_its_date():
    assert normalize_last_period(datetime(2026, 6, 1, 9, 30)) == "2026-06-01"

def test_today_is_accepted():
    today = _today()
    assert normalize_last_period(today.isoformat()) == today.isoformat()

def test_none_passes_through():
    assert normalize_last_period(None) is None

def test_an_empty_string_is_read_as_clearing_the_field():
    assert normalize_last_period("") is None
    assert normalize_last_period("   ") is None

@pytest.mark.parametrize(
    "sent",
    [
        "yesterday",
        "01/06/2026",
        "2026-13-01",
        "2026-02-30",
        "2026-6-1",
        "2026-06-01-garbage",
        "null",
        "0",
    ],
)
def test_something_that_is_not_a_date_is_refused(sent):
    with pytest.raises(ValueError) as exc:
        normalize_last_period(sent)
    assert "last_period" in str(exc.value)

def test_a_trailing_suffix_is_not_quietly_truncated():
    with pytest.raises(ValueError):
        normalize_last_period("2026-06-01-garbage")

def test_a_value_that_is_not_text_is_refused():
    for sent in (42, 3.5, True, ["2026-06-01"], {"date": "2026-06-01"}):
        with pytest.raises(ValueError):
            normalize_last_period(sent)

def test_an_absurdly_long_value_is_refused_before_parsing():
    with pytest.raises(ValueError):
        normalize_last_period("2026-06-01" + "x" * 5000)

def test_a_date_in_the_future_is_refused():
    ahead = (_today() + timedelta(days=30)).isoformat()

    with pytest.raises(ValueError) as exc:
        normalize_last_period(ahead)

    assert "future" in str(exc.value)

def test_tomorrow_is_within_the_timezone_grace():
    tomorrow = (_today() + timedelta(days=FUTURE_GRACE_DAYS)).isoformat()

    assert normalize_last_period(tomorrow) == tomorrow

def test_the_grace_does_not_extend_to_a_genuinely_wrong_answer():
    beyond = (_today() + timedelta(days=FUTURE_GRACE_DAYS + 1)).isoformat()

    with pytest.raises(ValueError):
        normalize_last_period(beyond)

def test_a_date_from_years_ago_is_accepted():
    old = (_today() - timedelta(days=MAX_LAST_PERIOD_AGE_DAYS - 10)).isoformat()

    assert normalize_last_period(old) == old

def test_a_date_beyond_the_age_bound_is_refused():
    ancient = (_today() - timedelta(days=MAX_LAST_PERIOD_AGE_DAYS + 10)).isoformat()

    with pytest.raises(ValueError) as exc:
        normalize_last_period(ancient)

    assert "past" in str(exc.value)

def test_a_mis_parsed_year_is_refused_by_the_age_bound():
    with pytest.raises(ValueError):
        normalize_last_period("0202-06-01")

def test_the_model_normalises_a_timestamp():
    update = UserProfileUpdate(last_period="2026-06-01T09:30:00Z")

    assert update.last_period == "2026-06-01"

def test_the_model_refuses_a_future_date():
    ahead = (_today() + timedelta(days=30)).isoformat()

    with pytest.raises(ValidationError) as exc:
        UserProfileUpdate(last_period=ahead)

    assert "last_period" in str(exc.value)

def test_the_model_refuses_a_malformed_date():
    with pytest.raises(ValidationError):
        UserProfileUpdate(last_period="not-a-date")

def test_an_update_that_omits_the_field_is_unaffected():
    update = UserProfileUpdate(full_name="Alice Doe")

    dump = update.model_dump()
    assert dump["last_period"] is None
    assert {k: v for k, v in dump.items() if v is not None} == {
        "full_name": "Alice Doe"
    }

@pytest.fixture
def _authenticated(monkeypatch):
    import core.auth_router as auth_router_module
    from core.auth import get_current_user

    written = {}

    def _fake_update(user_id, updates):
        written.update(updates)
        return True

    def _fake_get(user_id):
        return {
            "id": user_id,
            "email": "asha@example.com",
            "username": "ashadev",
            **written,
        }

    monkeypatch.setattr(
        auth_router_module.UserService, "update_user", staticmethod(_fake_update)
    )
    monkeypatch.setattr(
        auth_router_module.UserService, "get_user_by_id", staticmethod(_fake_get)
    )

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1",
        "email": "asha@example.com",
    }
    yield written
    app.dependency_overrides.pop(get_current_user, None)

def test_the_route_stores_a_normalised_date(_authenticated):
    response = client.patch(
        "/api/v1/auth/profile", json={"last_period": "2026-06-01T09:30:00Z"}
    )

    assert response.status_code == 200
    assert _authenticated["last_period"] == "2026-06-01"

def test_the_route_refuses_a_future_date_with_a_422(_authenticated):
    ahead = (_today() + timedelta(days=45)).isoformat()

    response = client.patch("/api/v1/auth/profile", json={"last_period": ahead})

    assert response.status_code == 422
    assert _authenticated == {}, "nothing should have reached the store"

def test_the_route_refuses_a_malformed_date_with_a_422(_authenticated):
    response = client.patch(
        "/api/v1/auth/profile", json={"last_period": "01/06/2026"}
    )

    assert response.status_code == 422
    assert _authenticated == {}

def test_the_422_names_the_field(_authenticated):
    response = client.patch(
        "/api/v1/auth/profile", json={"last_period": "yesterday"}
    )

    assert response.status_code == 422
    assert "last_period" in response.text

def test_other_profile_fields_still_save(_authenticated):
    response = client.patch(
        "/api/v1/auth/profile",
        json={"full_name": "Asha", "cycle_length": 30, "period_duration": 5},
    )

    assert response.status_code == 200
    assert _authenticated["cycle_length"] == 30
    assert "last_period" not in _authenticated

def test_a_malformed_anchor_would_have_emptied_the_prediction():
    result = prediction_service.predict([], profile={"last_period": "yesterday"})

    assert result.last_period_start is None
    assert result.phase == prediction_service.PHASE_UNKNOWN
    assert result.next_period_date is None
    assert result.ovulation_date is None

def test_a_future_anchor_would_have_produced_a_fertile_window(monkeypatch):
    today = date(2026, 6, 1)
    ahead = (today + timedelta(days=30)).isoformat()

    result = prediction_service.predict(
        [], profile={"last_period": ahead, "cycle_length": 28}, today=today
    )

    assert result.last_period_start == date(2026, 7, 1)
    assert result.current_cycle_day is None
    assert result.ovulation_date is not None
    assert result.fertile_window_start is not None
    assert result.fertile_window_end is not None

def test_an_accepted_anchor_behaves():
    today = date(2026, 6, 15)

    result = prediction_service.predict(
        [], profile={"last_period": "2026-06-01", "cycle_length": 28}, today=today
    )

    assert result.last_period_start == date(2026, 6, 1)
    assert result.current_cycle_day == 15
    assert result.next_period_date == date(2026, 6, 29)
