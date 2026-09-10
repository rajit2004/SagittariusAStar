from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from core import rate_limits
from core.auth import get_password_hash
from core.auth_router import normalize_email
from core.password_policy import validate_password
from core.rate_limits import (
    LOGIN_ACCOUNT,
    LOGIN_IP,
    PROVIDER_REGISTER_IP,
    REGISTER_IP,
)
from services.rate_limit_service import RateLimitService

client = TestClient(app)

REGISTER_URL = "/api/v1/provider/register"
LOGIN_URL = "/api/v1/provider/login"
PATIENT_REGISTER_URL = "/api/v1/auth/register"
PATIENT_LOGIN_URL = "/api/v1/auth/login"

STRONG_PASSWORD = "Wintergreen!Harbour42"
PROVIDER_EMAIL = "dr.mehta@clinic.in"
PATIENT_EMAIL = "asha@example.com"

WEAK_PASSWORDS = [
    "a",
    "",
    "        ",
    "1234567",
    "password",
    "aaaaaaaaaaaa",
    "abcdefghijkl",
    "qwertyuiop",
]

@pytest.fixture(autouse=True)
def _clean_state():

    def _reset():
        client.cookies.clear()
        RateLimitService.clear_all()

    _reset()
    yield
    _reset()

class _FakeUserStore:

    def __init__(self):
        self.users = {}
        self.next_id = 1

    def seed(self, email, password, role="provider", **extra):
        user_id = f"seeded-{role}-{self.next_id}"
        self.next_id += 1
        key = normalize_email(email)
        self.users[key] = {
            "id": user_id,
            "email": key,
            "password": get_password_hash(password),
            "email_verified": True,
            "role": role,
            **extra,
        }
        return user_id

    def get_user_by_email(self, email):
        found = self.users.get(normalize_email(email))
        return dict(found) if found else None

    def get_user_by_id(self, user_id):
        for user in self.users.values():
            if user["id"] == user_id:
                return dict(user)
        return None

    def create_user(self, data):
        user_id = f"created-{self.next_id}"
        self.next_id += 1
        key = normalize_email(data.get("email"))
        self.users[key] = {**data, "email": key, "id": user_id}
        return user_id

    def update_user(self, user_id, updates):
        return None

@pytest.fixture
def store():
    fake = _FakeUserStore()
    with patch("api.provider.UserService", fake), patch(
        "core.auth_router.UserService", fake
    ):
        yield fake

@pytest.fixture
def generous_limits(monkeypatch):
    for policy in (REGISTER_IP, PROVIDER_REGISTER_IP, LOGIN_IP, LOGIN_ACCOUNT):
        monkeypatch.setenv(f"{policy.env_prefix}_MAX", "10000")
    yield

@pytest.mark.parametrize("password", WEAK_PASSWORDS)
def test_provider_register_refuses_weak_passwords(store, generous_limits, password):
    response = client.post(
        REGISTER_URL,
        json={"email": f"weak-{len(password)}@clinic.in", "password": password},
    )

    assert response.status_code == 422, (
        f"password {password!r} was accepted; policy failures: "
        f"{validate_password(password)}"
    )
    assert response.json()["error"]["code"] == "weak_password"
    assert store.users == {}, "a rejected registration must not create an account"

@pytest.mark.parametrize("password", WEAK_PASSWORDS)
def test_provider_and_patient_registration_agree_on_weak_passwords(
    store, generous_limits, password
):
    provider = client.post(
        REGISTER_URL, json={"email": "sym-a@clinic.in", "password": password}
    )
    patient = client.post(
        PATIENT_REGISTER_URL, json={"email": "sym-b@example.com", "password": password}
    )

    assert provider.status_code == patient.status_code == 422
    assert (
        provider.json()["error"]["code"] == patient.json()["error"]["code"]
    ), "the two registration routes disagree about what a weak password is"

def test_provider_register_accepts_a_strong_password(store, generous_limits):
    response = client.post(
        REGISTER_URL,
        json={
            "email": PROVIDER_EMAIL,
            "password": STRONG_PASSWORD,
            "full_name": "Dr. Priya Mehta",
            "specialty": "Gynaecology",
            "license_number": "MH-2019-44821",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "provider"
    assert body["email"] == PROVIDER_EMAIL

    stored = store.users[PROVIDER_EMAIL]
    assert stored["role"] == "provider"
    assert stored["specialty"] == "Gynaecology"
    assert stored["license_number"] == "MH-2019-44821"

def test_password_containing_the_provider_email_is_refused(store, generous_limits):
    response = client.post(
        REGISTER_URL,
        json={"email": "drmehta@clinic.in", "password": "drmehta@clinic.in!99X"},
    )

    assert response.status_code == 422
    codes = {d["code"] for d in response.json()["error"]["details"]}
    assert "contains_identifier" in codes

def test_password_containing_the_provider_username_is_refused(store, generous_limits):
    response = client.post(
        REGISTER_URL,
        json={
            "email": "someone@clinic.in",
            "password": "PriyaMehta!Winter42",
            "username": "PriyaMehta",
        },
    )

    assert response.status_code == 422
    codes = {d["code"] for d in response.json()["error"]["details"]}
    assert "contains_identifier" in codes

def test_the_password_is_never_echoed_in_a_rejection(store, generous_limits):
    secret = "hunter2hunter2"
    response = client.post(
        REGISTER_URL, json={"email": "echo@clinic.in", "password": secret}
    )

    assert secret not in response.text

@pytest.mark.parametrize(
    "field,length",
    [
        ("full_name", 500),
        ("username", 500),
        ("specialty", 500),
        ("license_number", 500),
    ],
)
def test_over_long_profile_fields_are_refused(store, generous_limits, field, length):
    response = client.post(
        REGISTER_URL,
        json={
            "email": f"long-{field}@clinic.in",
            "password": STRONG_PASSWORD,
            field: "x" * length,
        },
    )

    assert response.status_code == 422
    assert store.users == {}

def test_whitespace_only_profile_fields_are_stored_as_absent(store, generous_limits):
    response = client.post(
        REGISTER_URL,
        json={
            "email": "blank@clinic.in",
            "password": STRONG_PASSWORD,
            "full_name": "   ",
            "specialty": "\t\n ",
        },
    )

    assert response.status_code == 201
    stored = store.users["blank@clinic.in"]
    assert stored["full_name"] is None
    assert stored["specialty"] is None

def test_profile_fields_are_trimmed(store, generous_limits):
    client.post(
        REGISTER_URL,
        json={
            "email": "trim@clinic.in",
            "password": STRONG_PASSWORD,
            "full_name": "  Dr. Priya Mehta  ",
        },
    )

    assert store.users["trim@clinic.in"]["full_name"] == "Dr. Priya Mehta"

def test_normalize_email_casefolds_and_strips():
    assert normalize_email("  Dr.Mehta@Clinic.IN ") == "dr.mehta@clinic.in"
    assert normalize_email("") == ""
    assert normalize_email(None) == ""

def test_registration_stores_the_normalised_address(store, generous_limits):
    response = client.post(
        REGISTER_URL, json={"email": "Dr.Mehta@Clinic.IN", "password": STRONG_PASSWORD}
    )

    assert response.status_code == 201
    assert response.json()["email"] == "dr.mehta@clinic.in"
    assert "dr.mehta@clinic.in" in store.users

def test_case_variant_registration_is_a_conflict_not_a_second_account(
    store, generous_limits
):
    first = client.post(
        REGISTER_URL, json={"email": "doc@clinic.in", "password": STRONG_PASSWORD}
    )
    second = client.post(
        REGISTER_URL, json={"email": "DOC@CLINIC.IN", "password": STRONG_PASSWORD}
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert len(store.users) == 1

def test_login_accepts_a_differently_cased_address(store, generous_limits):
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)

    response = client.post(
        LOGIN_URL, json={"email": "Dr.Mehta@Clinic.IN", "password": STRONG_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "provider"

def test_provider_login_is_limited_per_account(store, generous_limits, monkeypatch):
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_MAX", "3")

    codes = [
        client.post(
            LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "WrongPassword!1"}
        ).status_code
        for _ in range(4)
    ]

    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429

def test_provider_login_is_limited_per_ip_across_different_accounts(
    store, generous_limits, monkeypatch
):
    monkeypatch.setenv(f"{LOGIN_IP.env_prefix}_MAX", "3")

    codes = [
        client.post(
            LOGIN_URL, json={"email": f"victim{i}@clinic.in", "password": "Guess!1234"}
        ).status_code
        for i in range(4)
    ]

    assert codes[3] == 429, "a different address each time should still trip per-IP"

def test_rate_limited_login_carries_a_usable_retry_after(
    store, generous_limits, monkeypatch
):
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_MAX", "1")
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_WINDOW", "600")

    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"})
    blocked = client.post(
        LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"}
    )

    assert blocked.status_code == 429
    retry_after = int(blocked.headers["Retry-After"])
    assert 0 < retry_after <= 600

def test_provider_and_patient_login_share_one_account_bucket(
    store, generous_limits, monkeypatch
):
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_MAX", "2")

    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"})
    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"})

    spillover = client.post(
        PATIENT_LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"}
    )

    assert spillover.status_code == 429

def test_provider_and_patient_login_share_one_ip_bucket(
    store, generous_limits, monkeypatch
):
    monkeypatch.setenv(f"{LOGIN_IP.env_prefix}_MAX", "2")

    client.post(LOGIN_URL, json={"email": "a@clinic.in", "password": "Wrong!12345"})
    client.post(LOGIN_URL, json={"email": "b@clinic.in", "password": "Wrong!12345"})

    spillover = client.post(
        PATIENT_LOGIN_URL, json={"email": "c@example.com", "password": "Wrong!12345"}
    )

    assert spillover.status_code == 429

def test_a_successful_login_clears_the_account_bucket(
    store, generous_limits, monkeypatch
):
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_MAX", "5")

    for _ in range(3):
        client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Nope!12345"})

    success = client.post(
        LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": STRONG_PASSWORD}
    )
    assert success.status_code == 200

    after = [
        client.post(
            LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Nope!12345"}
        ).status_code
        for _ in range(5)
    ]
    assert after == [401] * 5

def test_a_successful_login_does_not_clear_the_ip_bucket(
    store, generous_limits, monkeypatch
):
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    monkeypatch.setenv(f"{LOGIN_IP.env_prefix}_MAX", "3")

    client.post(LOGIN_URL, json={"email": "x@clinic.in", "password": "Nope!12345"})
    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": STRONG_PASSWORD})
    client.post(LOGIN_URL, json={"email": "y@clinic.in", "password": "Nope!12345"})

    assert (
        client.post(
            LOGIN_URL, json={"email": "z@clinic.in", "password": "Nope!12345"}
        ).status_code
        == 429
    )

def test_a_patient_hitting_the_provider_form_keeps_her_budget_intact(
    store, generous_limits, monkeypatch
):
    store.seed(PATIENT_EMAIL, STRONG_PASSWORD, role="patient")
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_MAX", "3")

    codes = [
        client.post(
            LOGIN_URL, json={"email": PATIENT_EMAIL, "password": STRONG_PASSWORD}
        ).status_code
        for _ in range(4)
    ]

    assert codes[:3] == [403, 403, 403]
    assert codes[3] == 429

def test_provider_registration_is_rate_limited(store, monkeypatch):
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "3")
    monkeypatch.setenv(f"{REGISTER_IP.env_prefix}_MAX", "10000")

    codes = [
        client.post(
            REGISTER_URL,
            json={"email": f"bulk{i}@clinic.in", "password": STRONG_PASSWORD},
        ).status_code
        for i in range(4)
    ]

    assert codes[:3] == [201, 201, 201]
    assert codes[3] == 429

def test_provider_registration_also_counts_against_the_shared_ceiling(
    store, monkeypatch
):
    monkeypatch.setenv(f"{REGISTER_IP.env_prefix}_MAX", "2")
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "10000")

    client.post(
        PATIENT_REGISTER_URL,
        json={"email": "p1@example.com", "password": STRONG_PASSWORD},
    )
    client.post(
        REGISTER_URL, json={"email": "d1@clinic.in", "password": STRONG_PASSWORD}
    )

    third = client.post(
        REGISTER_URL, json={"email": "d2@clinic.in", "password": STRONG_PASSWORD}
    )
    assert third.status_code == 429

def test_registration_is_metered_before_the_existence_check(store, monkeypatch):
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "2")
    monkeypatch.setenv(f"{REGISTER_IP.env_prefix}_MAX", "10000")
    store.seed("taken@clinic.in", STRONG_PASSWORD)

    first = client.post(
        REGISTER_URL, json={"email": "taken@clinic.in", "password": STRONG_PASSWORD}
    )
    second = client.post(
        REGISTER_URL, json={"email": "taken@clinic.in", "password": STRONG_PASSWORD}
    )
    third = client.post(
        REGISTER_URL, json={"email": "taken@clinic.in", "password": STRONG_PASSWORD}
    )

    assert first.status_code == second.status_code == 409
    assert third.status_code == 429

def test_a_weak_password_still_consumes_registration_budget(store, monkeypatch):
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "2")
    monkeypatch.setenv(f"{REGISTER_IP.env_prefix}_MAX", "10000")

    client.post(REGISTER_URL, json={"email": "w1@clinic.in", "password": "a"})
    client.post(REGISTER_URL, json={"email": "w2@clinic.in", "password": "a"})

    third = client.post(
        REGISTER_URL, json={"email": "w3@clinic.in", "password": STRONG_PASSWORD}
    )
    assert third.status_code == 429

def test_provider_register_policy_is_tunable_from_the_environment(monkeypatch):
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "7")
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_WINDOW", "120")

    assert PROVIDER_REGISTER_IP.limit == 7
    assert PROVIDER_REGISTER_IP.window_seconds == 120

def test_a_zero_limit_falls_back_rather_than_opening_the_gate(monkeypatch):
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "0")
    assert PROVIDER_REGISTER_IP.limit == PROVIDER_REGISTER_IP.default_limit

    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "-4")
    assert PROVIDER_REGISTER_IP.limit == PROVIDER_REGISTER_IP.default_limit

    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "not-a-number")
    assert PROVIDER_REGISTER_IP.limit == PROVIDER_REGISTER_IP.default_limit

def test_the_provider_register_bucket_is_distinct_from_the_shared_one():
    assert PROVIDER_REGISTER_IP.key_for("1.2.3.4") != REGISTER_IP.key_for("1.2.3.4")

def test_provider_bucket_keys_do_not_contain_the_identifier():
    key = PROVIDER_REGISTER_IP.key_for("dr.mehta@clinic.in")
    assert "dr.mehta@clinic.in" not in key
    assert key.startswith("provider_register_ip:")

def test_login_buckets_are_case_insensitive_for_one_account():
    assert LOGIN_ACCOUNT.key_for("Dr.Mehta@Clinic.IN") == LOGIN_ACCOUNT.key_for(
        "dr.mehta@clinic.in"
    )

def _bucket_ids():
    from services import rate_limit_service as rls

    collections = getattr(rls.db, "_collections", None)
    if not collections:
        return set()
    return set((collections.get(RateLimitService.COLLECTION) or {}).keys())

def test_the_old_inline_login_key_is_no_longer_written(store, generous_limits):
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"})

    written = _bucket_ids()
    assert written, "the login attempt recorded no bucket at all"
    assert not any(
        key.startswith("login:") for key in written
    ), f"the inline login:{{ip}} key is still being written: {written}"

def test_provider_login_writes_both_policy_buckets(store, generous_limits):
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"})

    written = _bucket_ids()
    assert LOGIN_IP.key_for("testclient") in written or any(
        key.startswith("login_ip:") for key in written
    )
    assert LOGIN_ACCOUNT.key_for(PROVIDER_EMAIL) in written
