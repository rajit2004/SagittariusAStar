from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from api.sms import (
    SMS_MAX_CHARS,
    generate_cycle_sms_summary,
    registered_phone,
)
from core.auth import create_access_token
from services.firestore_service import MockFirestoreClient, UserService
from services.rate_limit_service import RateLimitService

import services.firestore_service as _fs_mod
import services.rate_limit_service as _rl_mod

client = TestClient(app)

SEND_URL = "/api/v1/sms/send-summary"
SETTINGS_URL = "/api/v1/sms/settings"

OWN_NUMBER = "+919876543210"
SOMEONE_ELSES_NUMBER = "+447700900123"
TWILIO_FROM = "+10000000000"

_mock_db = None

@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    global _mock_db
    _mock_db = MockFirestoreClient()
    monkeypatch.setattr(_fs_mod, "db", _mock_db)
    monkeypatch.setattr(_rl_mod, "db", _mock_db)
    RateLimitService.clear_all()
    yield
    RateLimitService.clear_all()
    _mock_db = None

@pytest.fixture(autouse=True)
def _twilio_configured(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "test-sid")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", TWILIO_FROM)

@pytest.fixture
def twilio():
    with patch("twilio.rest.Client") as MockClient:
        instance = MagicMock()
        MockClient.return_value = instance
        instance.messages.create.return_value = MagicMock(sid="SM-test")
        yield instance

def _sent(twilio):
    assert twilio.messages.create.call_count == 1
    return twilio.messages.create.call_args.kwargs

def _account(phone=OWN_NUMBER, **extra):
    payload = {"email": "sana@example.com", "sms_enabled": True, **extra}
    if phone is not None:
        payload["phone"] = phone
    user_id = UserService.create_user(payload)
    token = create_access_token(data={"sub": user_id})
    return user_id, {"Authorization": f"Bearer {token}"}

def test_the_summary_goes_to_the_number_on_the_account(twilio):
    _, headers = _account()

    response = client.post(SEND_URL, json={}, headers=headers)

    assert response.status_code == 200, response.text
    assert _sent(twilio)["to"] == OWN_NUMBER
    assert _sent(twilio)["from_"] == TWILIO_FROM

def test_a_matching_phone_number_in_the_body_is_accepted(twilio):
    _, headers = _account()

    response = client.post(
        SEND_URL, json={"phone_number": OWN_NUMBER}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert _sent(twilio)["to"] == OWN_NUMBER

def test_someone_elses_number_is_refused_and_nothing_is_sent(twilio):
    _, headers = _account()

    response = client.post(
        SEND_URL, json={"phone_number": SOMEONE_ELSES_NUMBER}, headers=headers
    )

    assert response.status_code == 403
    assert twilio.messages.create.call_count == 0

def test_a_refused_destination_does_not_spend_the_rate_limit(twilio):
    _, headers = _account()

    refused = client.post(
        SEND_URL, json={"phone_number": SOMEONE_ELSES_NUMBER}, headers=headers
    )
    assert refused.status_code == 403

    allowed = client.post(SEND_URL, json={}, headers=headers)
    assert allowed.status_code == 200, allowed.text
    assert _sent(twilio)["to"] == OWN_NUMBER

def test_an_account_with_no_saved_number_gets_a_clear_error(twilio):
    _, headers = _account(phone=None)

    response = client.post(
        SEND_URL, json={"phone_number": SOMEONE_ELSES_NUMBER}, headers=headers
    )

    assert response.status_code == 409
    assert "SMS settings" in response.json()["detail"]
    assert twilio.messages.create.call_count == 0

def test_a_malformed_stored_number_is_refused_rather_than_handed_to_twilio(twilio):
    _, headers = _account(phone="9876543210")

    response = client.post(SEND_URL, json={}, headers=headers)

    assert response.status_code == 409
    assert twilio.messages.create.call_count == 0

def test_the_route_requires_authentication(twilio):
    response = client.post(SEND_URL, json={"phone_number": OWN_NUMBER})

    assert response.status_code == 401
    assert twilio.messages.create.call_count == 0

def test_two_accounts_cannot_be_pointed_at_one_victim(twilio):
    _, first = _account(phone="+919000000001")
    UserService.create_user({"email": "b@example.com", "phone": "+919000000002"})
    _, second = _account(phone="+919000000003")

    for headers in (first, second):
        response = client.post(
            SEND_URL, json={"phone_number": SOMEONE_ELSES_NUMBER}, headers=headers
        )
        assert response.status_code == 403

    assert twilio.messages.create.call_count == 0

def test_a_caller_supplied_message_is_never_sent(twilio):
    _, headers = _account()

    response = client.post(
        SEND_URL,
        json={"phone_number": OWN_NUMBER, "message": "Visit http://evil.example"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = _sent(twilio)["body"]
    assert "evil.example" not in body

    assert body.startswith("Rhythma")

def test_an_enormous_message_cannot_inflate_the_bill(twilio):
    _, headers = _account()

    response = client.post(
        SEND_URL, json={"message": "A" * 50_000}, headers=headers
    )

    assert response.status_code == 200, response.text
    assert len(_sent(twilio)["body"]) <= SMS_MAX_CHARS

def test_the_sent_body_is_the_generated_summary(twilio):
    _, headers = _account()

    response = client.post(SEND_URL, json={}, headers=headers)

    assert response.status_code == 200, response.text
    body = _sent(twilio)["body"]
    assert body.startswith("Rhythma")
    assert "Log your last period" in body
    assert "not medical/contraceptive advice" in body

def test_the_summary_fits_one_segment():
    summary = generate_cycle_sms_summary("nobody")
    assert len(summary) <= SMS_MAX_CHARS

def test_the_disclaimer_is_all_or_nothing():
    summary = generate_cycle_sms_summary("nobody")
    if "Estimate only" in summary:
        assert summary.rstrip().endswith("medical/contraceptive advice.")

def test_a_long_summary_is_cut_at_a_word_not_through_a_number():
    from api.sms import _fit_to_one_segment

    text = "Rhythma Summary: " + ("word " * 60) + "final"
    fitted = _fit_to_one_segment(text)

    assert len(fitted) <= SMS_MAX_CHARS
    assert fitted.endswith("...")
    assert not fitted.rstrip(".").endswith("wor")

def test_a_short_summary_is_returned_untouched():
    from api.sms import _fit_to_one_segment

    assert _fit_to_one_segment("Short.") == "Short."

def test_registered_phone_prefers_the_same_field_the_settings_screen_shows():
    assert registered_phone({"phone": OWN_NUMBER, "sms_phone_number": "+1"}) == (
        OWN_NUMBER
    )

def test_registered_phone_falls_back_to_the_sms_specific_field():
    assert registered_phone({"sms_phone_number": OWN_NUMBER}) == OWN_NUMBER

@pytest.mark.parametrize("user", [None, {}, {"phone": ""}, {"phone": "   "}])
def test_registered_phone_treats_blank_as_absent(user):
    assert registered_phone(user) is None

def test_settings_and_send_agree_on_the_destination(twilio):
    _, headers = _account(phone=None, sms_phone_number=OWN_NUMBER)

    shown = client.get(SETTINGS_URL, headers=headers)
    assert shown.status_code == 200
    assert shown.json()["phoneNumber"] == OWN_NUMBER

    sent = client.post(SEND_URL, json={}, headers=headers)
    assert sent.status_code == 200, sent.text
    assert _sent(twilio)["to"] == shown.json()["phoneNumber"]

def test_a_number_saved_through_settings_becomes_the_destination(twilio):
    _, headers = _account(phone=None)

    saved = client.post(
        SETTINGS_URL,
        json={"phoneNumber": OWN_NUMBER, "enabled": True},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text

    sent = client.post(SEND_URL, json={}, headers=headers)
    assert sent.status_code == 200, sent.text
    assert _sent(twilio)["to"] == OWN_NUMBER

def test_the_rate_limit_still_applies_to_a_valid_send(twilio):
    _, headers = _account()

    first = client.post(SEND_URL, json={}, headers=headers)
    assert first.status_code == 200, first.text

    second = client.post(SEND_URL, json={}, headers=headers)
    assert second.status_code == 429
    assert second.headers["Retry-After"]
    assert twilio.messages.create.call_count == 1

def test_a_twilio_failure_is_still_reported_as_a_500(twilio):
    _, headers = _account()
    twilio.messages.create.side_effect = Exception("Twilio down")

    response = client.post(SEND_URL, json={}, headers=headers)

    assert response.status_code == 500
    assert "Failed to send SMS" in response.json()["detail"]

def test_missing_twilio_credentials_are_still_reported(monkeypatch, twilio):
    _, headers = _account()
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)

    response = client.post(SEND_URL, json={}, headers=headers)

    assert response.status_code == 500
    assert "Twilio credentials are not configured" in response.json()["detail"]
    assert twilio.messages.create.call_count == 0

def test_a_malformed_phone_number_in_the_body_is_still_a_422(twilio):
    _, headers = _account()

    response = client.post(
        SEND_URL, json={"phone_number": "not-a-number"}, headers=headers
    )

    assert response.status_code == 422
    assert twilio.messages.create.call_count == 0
