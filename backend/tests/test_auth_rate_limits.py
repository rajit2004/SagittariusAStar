import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ["TRUSTED_PROXY_IPS"] = "*"

from main import app
from core import rate_limits
from core.client_address import (
    TRUSTED_PROXY_HOPS_ENV,
    TRUSTED_PROXY_IPS_ENV,
)
from core.rate_limits import (
    LOGIN_ACCOUNT,
    LOGIN_IP,
    RateLimitPolicy,
    client_ip,
)
from core.auth import get_password_hash
from services.firestore_service import MockFirestoreClient
from services.rate_limit_service import RateLimitService

import services.firestore_service as _fs_mod
import services.rate_limit_service as _rl_mod

_mock_db = MockFirestoreClient()
_fs_mod.db = _mock_db
_rl_mod.db = _mock_db

client = TestClient(app)

PASSWORD = "SecurePass123"
KNOWN_EMAIL = "known@example.com"

@pytest.fixture(autouse=True)
def _clean_state():
    def _reset():
        client.cookies.clear()
        _mock_db._collections.clear()

    _reset()
    yield
    _reset()

@pytest.fixture(autouse=True)
def _mock_user_service():
    stored = {
        "id": "rate-limit-user",
        "email": KNOWN_EMAIL,
        "password": get_password_hash(PASSWORD),
        "email_verified": True,
        "created_at": "2026-01-01T00:00:00Z",
    }

    def get_by_email(email):
        return stored.copy() if email == KNOWN_EMAIL else None

    with patch("core.auth_router.UserService") as mock_service:
        mock_service.get_user_by_email.side_effect = get_by_email
        mock_service.get_user_by_id.return_value = stored.copy()
        mock_service.create_user.return_value = "new-user-id"
        mock_service.update_user.return_value = None
        yield mock_service

def _login(email, password=PASSWORD, ip="203.0.113.10"):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Forwarded-For": ip},
    )

def test_policy_uses_its_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_LOGIN_IP_MAX", raising=False)
    monkeypatch.delenv("RATE_LIMIT_LOGIN_IP_WINDOW", raising=False)

    assert LOGIN_IP.limit == LOGIN_IP.default_limit
    assert LOGIN_IP.window_seconds == LOGIN_IP.default_window

def test_policy_reads_overrides_from_the_environment(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_WINDOW", "60")

    assert LOGIN_IP.limit == 3
    assert LOGIN_IP.window_seconds == 60

@pytest.mark.parametrize("bad", ["0", "-5", "", "ten", "5.5"])
def test_a_bad_override_falls_back_instead_of_disabling_the_limit(monkeypatch, bad):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", bad)
    assert LOGIN_IP.limit == LOGIN_IP.default_limit

def test_identifiers_are_hashed_before_they_become_storage_keys():
    key = LOGIN_ACCOUNT.key_for("sana@example.com")

    assert "sana@example.com" not in key
    assert "sana" not in key
    assert key.startswith("login_account:")

def test_the_same_identifier_always_maps_to_the_same_key():
    assert LOGIN_ACCOUNT.key_for("a@b.com") == LOGIN_ACCOUNT.key_for("a@b.com")

def test_identifier_matching_ignores_case_and_surrounding_space():
    assert LOGIN_ACCOUNT.key_for(" Sana@Example.com ") == LOGIN_ACCOUNT.key_for(
        "sana@example.com"
    )

def test_different_identifiers_map_to_different_keys():
    assert LOGIN_ACCOUNT.key_for("a@b.com") != LOGIN_ACCOUNT.key_for("c@d.com")

def test_policies_do_not_share_a_bucket():
    assert LOGIN_ACCOUNT.key_for("a@b.com") != LOGIN_IP.key_for("a@b.com")

def test_enforce_allows_up_to_the_limit_then_raises_429():
    from fastapi import HTTPException

    policy = RateLimitPolicy(
        name="unit_test_bucket",
        default_limit=2,
        default_window=300,
        message="wait {seconds}",
    )

    rate_limits.enforce(policy, "someone")
    rate_limits.enforce(policy, "someone")

    with pytest.raises(HTTPException) as exc:
        rate_limits.enforce(policy, "someone")

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"].isdigit()
    assert int(exc.value.headers["Retry-After"]) >= 1

def test_clear_frees_the_bucket_again():
    policy = RateLimitPolicy(
        name="unit_test_clear",
        default_limit=1,
        default_window=300,
        message="wait {seconds}",
    )

    rate_limits.enforce(policy, "someone")
    rate_limits.clear(policy, "someone")

    rate_limits.enforce(policy, "someone")

def test_clearing_a_bucket_that_was_never_used_is_not_an_error():
    policy = RateLimitPolicy(
        name="unit_test_never_used",
        default_limit=1,
        default_window=300,
        message="wait {seconds}",
    )
    rate_limits.clear(policy, "nobody")

class _FakeRequest:
    def __init__(self, headers=None, host="198.51.100.7"):
        self.headers = headers or {}
        self.client = MagicMock(host=host) if host is not None else None

def test_client_ip_takes_the_last_forwarded_address_not_the_first():
    request = _FakeRequest({"X-Forwarded-For": "203.0.113.5, 70.41.3.18, 150.172.238.178"})
    assert client_ip(request) == "150.172.238.178"

def test_client_ip_falls_back_to_the_socket_address():
    assert client_ip(_FakeRequest(host="198.51.100.7")) == "198.51.100.7"

def test_client_ip_is_unknown_when_there_is_nothing_to_read():
    assert client_ip(_FakeRequest(host=None)) == "unknown"
    assert client_ip(None) == "unknown"

def test_an_empty_forwarded_header_falls_through_to_the_socket():
    request = _FakeRequest({"X-Forwarded-For": "  "}, host="198.51.100.7")
    assert client_ip(request) == "198.51.100.7"

def test_client_ip_ignores_the_header_when_no_proxy_is_declared(monkeypatch):
    monkeypatch.delenv(TRUSTED_PROXY_IPS_ENV, raising=False)

    request = _FakeRequest({"X-Forwarded-For": "203.0.113.5"}, host="198.51.100.7")
    assert client_ip(request) == "198.51.100.7"

def test_client_ip_honours_a_declared_hop_count(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "*")
    monkeypatch.setenv(TRUSTED_PROXY_HOPS_ENV, "1")

    request = _FakeRequest(
        {"X-Forwarded-For": "1.1.1.1, 203.0.113.5, 169.254.8.8"},
        host="169.254.1.1",
    )
    assert client_ip(request) == "203.0.113.5"

def test_a_direct_caller_cannot_reset_a_limit_by_changing_the_header(monkeypatch):
    monkeypatch.delenv(TRUSTED_PROXY_IPS_ENV, raising=False)
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_CONFIRM_IP_MAX", "2")

    payload = {
        "email": KNOWN_EMAIL,
        "token": "not-a-real-token",
        "new_password": "AnotherPass456",
    }

    statuses = [
        client.post(
            "/api/v1/auth/reset-password",
            json=payload,
            headers={"X-Forwarded-For": f"203.0.113.{n}"},
        ).status_code
        for n in range(1, 6)
    ]

    assert statuses[:2] == [400, 400]
    assert statuses[2:] == [429, 429, 429]

def test_registration_cannot_be_sprayed_from_one_address(monkeypatch):
    monkeypatch.delenv(TRUSTED_PROXY_IPS_ENV, raising=False)
    monkeypatch.setenv("RATE_LIMIT_REGISTER_IP_MAX", "2")

    statuses = [
        client.post(
            "/api/v1/auth/register",
            json={"email": f"spray{n}@example.com", "password": PASSWORD},
            headers={"X-Forwarded-For": f"198.51.100.{n}"},
        ).status_code
        for n in range(1, 5)
    ]

    assert statuses == [200, 200, 429, 429]

def test_a_caller_behind_a_declared_proxy_cannot_prepend_entries(monkeypatch):
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "*")
    monkeypatch.setenv("RATE_LIMIT_EMAIL_VERIFY_IP_MAX", "2")

    payload = {"email": KNOWN_EMAIL, "token": "not-a-real-token"}

    statuses = [
        client.post(
            "/api/v1/auth/verify-email",
            json=payload,
            headers={"X-Forwarded-For": f"10.9.9.{n}, 203.0.113.200"},
        ).status_code
        for n in range(1, 5)
    ]

    assert statuses == [400, 400, 429, 429]

def test_login_is_limited_per_account(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "50")

    for _ in range(3):
        assert _login(KNOWN_EMAIL, "wrong-password").status_code == 401

    blocked = _login(KNOWN_EMAIL, "wrong-password")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers

def test_the_per_account_limit_follows_the_account_across_addresses(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "50")

    for i in range(3):
        assert _login(KNOWN_EMAIL, "wrong", ip=f"203.0.113.{i}").status_code == 401

    assert _login(KNOWN_EMAIL, "wrong", ip="203.0.113.99").status_code == 429

def test_login_is_limited_per_ip_across_different_accounts(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "50")

    for i in range(3):
        assert _login(f"victim{i}@example.com", "wrong").status_code == 401

    assert _login("victim99@example.com", "wrong").status_code == 429

def test_one_clients_limit_does_not_affect_another(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "50")

    for _ in range(2):
        _login("a@example.com", "wrong", ip="203.0.113.1")
    assert _login("a@example.com", "wrong", ip="203.0.113.1").status_code == 429

    assert _login("a@example.com", "wrong", ip="198.51.100.1").status_code == 401

def test_a_successful_login_clears_that_accounts_attempts(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "4")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "50")

    for _ in range(3):
        assert _login(KNOWN_EMAIL, "wrong").status_code == 401

    assert _login(KNOWN_EMAIL).status_code == 200

    assert _login(KNOWN_EMAIL, "wrong").status_code == 401

def test_a_successful_login_does_not_clear_the_ip_bucket(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "50")

    assert _login("other1@example.com", "wrong").status_code == 401
    assert _login("other2@example.com", "wrong").status_code == 401
    assert _login(KNOWN_EMAIL).status_code == 200

    assert _login("other3@example.com", "wrong").status_code == 429

def test_unknown_emails_are_counted_too(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "50")

    assert _login("ghost@example.com", "x").status_code == 401
    assert _login("ghost@example.com", "x").status_code == 401
    assert _login("ghost@example.com", "x").status_code == 429

def test_retry_after_is_a_usable_number_of_seconds(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_WINDOW", "120")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "50")

    _login(KNOWN_EMAIL, "wrong")
    blocked = _login(KNOWN_EMAIL, "wrong")

    assert blocked.status_code == 429
    retry_after = int(blocked.headers["Retry-After"])
    assert 1 <= retry_after <= 120
    assert str(retry_after) in blocked.json()["detail"]

def test_register_is_limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REGISTER_IP_MAX", "2")

    for i in range(2):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": f"new{i}@example.com", "password": PASSWORD},
            headers={"X-Forwarded-For": "203.0.113.50"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/api/v1/auth/register",
        json={"email": "new99@example.com", "password": PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.50"},
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers

def test_register_is_limited_before_the_email_lookup(monkeypatch, _mock_user_service):
    monkeypatch.setenv("RATE_LIMIT_REGISTER_IP_MAX", "1")

    client.post(
        "/api/v1/auth/register",
        json={"email": "first@example.com", "password": PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.51"},
    )
    _mock_user_service.get_user_by_email.reset_mock()

    blocked = client.post(
        "/api/v1/auth/register",
        json={"email": KNOWN_EMAIL, "password": PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.51"},
    )

    assert blocked.status_code == 429
    _mock_user_service.get_user_by_email.assert_not_called()

def test_forgot_password_is_limited_per_account(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_REQUEST_ACCOUNT_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_REQUEST_IP_MAX", "50")

    for i in range(2):
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": KNOWN_EMAIL},
            headers={"X-Forwarded-For": f"203.0.113.{i}"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": KNOWN_EMAIL},
        headers={"X-Forwarded-For": "198.51.100.9"},
    )
    assert blocked.status_code == 429

def test_forgot_password_is_also_limited_per_ip(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_REQUEST_IP_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_REQUEST_ACCOUNT_MAX", "50")

    for i in range(2):
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": f"target{i}@example.com"},
            headers={"X-Forwarded-For": "203.0.113.60"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "target99@example.com"},
        headers={"X-Forwarded-For": "203.0.113.60"},
    )
    assert blocked.status_code == 429

def test_reset_password_token_submissions_are_limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_CONFIRM_IP_MAX", "2")

    payload = {
        "email": KNOWN_EMAIL,
        "token": "not-a-real-token",
        "new_password": "AnotherPass456",
    }
    headers = {"X-Forwarded-For": "203.0.113.70"}

    for _ in range(2):
        assert client.post("/api/v1/auth/reset-password", json=payload, headers=headers).status_code == 400

    blocked = client.post("/api/v1/auth/reset-password", json=payload, headers=headers)
    assert blocked.status_code == 429

def test_verify_email_token_submissions_are_limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_EMAIL_VERIFY_IP_MAX", "2")

    payload = {"email": KNOWN_EMAIL, "token": "not-a-real-token"}
    headers = {"X-Forwarded-For": "203.0.113.80"}

    for _ in range(2):
        assert client.post("/api/v1/auth/verify-email", json=payload, headers=headers).status_code == 400

    assert client.post("/api/v1/auth/verify-email", json=payload, headers=headers).status_code == 429

def test_resend_verification_is_limited_per_account(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_VERIFICATION_RESEND_ACCOUNT_MAX", "1")
    monkeypatch.setenv("RATE_LIMIT_EMAIL_VERIFY_IP_MAX", "50")

    first = client.post(
        "/api/v1/auth/resend-verification",
        json={"email": KNOWN_EMAIL},
        headers={"X-Forwarded-For": "203.0.113.90"},
    )
    assert first.status_code == 200

    blocked = client.post(
        "/api/v1/auth/resend-verification",
        json={"email": KNOWN_EMAIL},
        headers={"X-Forwarded-For": "198.51.100.90"},
    )
    assert blocked.status_code == 429

def test_refresh_is_limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TOKEN_REFRESH_IP_MAX", "2")

    payload = {"refresh_token": "not-a-real-refresh-token"}
    headers = {"X-Forwarded-For": "203.0.113.100"}

    for _ in range(2):
        assert client.post("/api/v1/auth/refresh", json=payload, headers=headers).status_code == 401

    assert client.post("/api/v1/auth/refresh", json=payload, headers=headers).status_code == 429

def test_firebase_login_keeps_its_existing_ceiling():
    from core.rate_limits import FIREBASE_LOGIN_IP

    assert FIREBASE_LOGIN_IP.default_limit == 10
    assert FIREBASE_LOGIN_IP.default_window == 300

def test_every_post_route_under_auth_is_covered():
    import inspect

    import core.auth_router as auth_router

    authenticated_or_stateless = {"/logout", "/logout-all"}
    unprotected = []

    for route in auth_router.router.routes:
        if "POST" not in getattr(route, "methods", set()):
            continue
        if route.path in authenticated_or_stateless:
            continue
        source = inspect.getsource(route.endpoint)
        if "enforce_rate_limit" not in source:
            unprotected.append(route.path)

    assert not unprotected, f"POST routes with no rate limit: {unprotected}"
