import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
from core.auth import (
    generate_reset_token,
    generate_verification_token,
    get_password_hash,
    reset_token_store,
    verification_token_store,
    verify_email_token,
    verify_reset_token,
)
from core.auth_router import normalize_email as router_normalize_email
from core.email_identity import normalize_email, same_email
from services import token_store
from services.firestore_service import MockFirestoreClient, UserService
from services.rate_limit_service import RateLimitService

import services.firestore_service as _fs_mod
import services.rate_limit_service as _rl_mod

client = TestClient(app)

_mock_db = None

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
FORGOT_URL = "/api/v1/auth/forgot-password"
RESET_URL = "/api/v1/auth/reset-password"
VERIFY_URL = "/api/v1/auth/verify-email"
RESEND_URL = "/api/v1/auth/resend-verification"
PROVIDER_REGISTER_URL = "/api/v1/provider/register"
PROVIDER_LOGIN_URL = "/api/v1/provider/login"

PASSWORD = "Wintergreen!Harbour42"

CANONICAL = "sana@example.com"
VARIANTS = [
    "Sana@Example.com",
    "SANA@EXAMPLE.COM",
    "  sana@example.com  ",
    "sAnA@eXaMpLe.CoM",
]

@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    global _mock_db
    _mock_db = MockFirestoreClient()
    monkeypatch.setattr(_fs_mod, "db", _mock_db)
    monkeypatch.setattr(_rl_mod, "db", _mock_db)
    yield
    _mock_db = None

@pytest.fixture(autouse=True)
def _clean_state():

    def _reset():
        client.cookies.clear()
        reset_token_store.clear()
        verification_token_store.clear()
        RateLimitService.clear_all()

    _reset()
    yield
    _reset()

def _seed_user(email, *, password=PASSWORD, role="patient", verified=False):
    return UserService.create_user(
        {
            "email": email,
            "password": get_password_hash(password),
            "email_verified": verified,
            "role": role,
        }
    )

def _seed_legacy_user(email, *, password=PASSWORD):
    _, doc = _mock_db.collection("users").add(
        {
            "email": email,
            "password": get_password_hash(password),
            "email_verified": False,
            "role": "patient",
        }
    )
    return doc.id

def _stored_emails():
    return [
        data.get("email") for data in _mock_db._collections.get("users", {}).values()
    ]

@pytest.mark.parametrize("variant", VARIANTS)
def test_normalize_email_collapses_every_variant(variant):
    assert normalize_email(variant) == CANONICAL

@pytest.mark.parametrize("blank", [None, "", "   ", "\t\n"])
def test_normalize_email_returns_empty_string_for_nothing(blank):
    assert normalize_email(blank) == ""

def test_normalize_email_leaves_the_local_part_otherwise_intact():
    assert normalize_email("S.ana+news@Example.com") == "s.ana+news@example.com"

@pytest.mark.parametrize("variant", VARIANTS)
def test_same_email_matches_across_capitalisation(variant):
    assert same_email(CANONICAL, variant) is True

def test_same_email_rejects_different_addresses():
    assert same_email(CANONICAL, "asha@example.com") is False

@pytest.mark.parametrize("blank", [None, "", "   "])
def test_same_email_is_false_when_either_side_is_blank(blank):
    assert same_email(blank, CANONICAL) is False
    assert same_email(CANONICAL, blank) is False
    assert same_email(blank, blank) is False

def test_auth_router_still_exports_normalize_email():
    assert router_normalize_email is normalize_email

@pytest.mark.parametrize("variant", VARIANTS)
def test_register_stores_the_canonical_address(variant):
    response = client.post(
        REGISTER_URL, json={"email": variant, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    assert response.json()["email"] == CANONICAL
    assert _stored_emails() == [CANONICAL]

@pytest.mark.parametrize("variant", VARIANTS)
def test_register_refuses_an_address_already_taken_in_another_case(variant):
    first = client.post(REGISTER_URL, json={"email": CANONICAL, "password": PASSWORD})
    assert first.status_code == 200, first.text

    second = client.post(REGISTER_URL, json={"email": variant, "password": PASSWORD})
    assert second.status_code == 409
    assert len(_stored_emails()) == 1

def test_register_still_allows_a_genuinely_different_address():
    assert (
        client.post(REGISTER_URL, json={"email": CANONICAL, "password": PASSWORD}).status_code
        == 200
    )
    assert (
        client.post(
            REGISTER_URL, json={"email": "asha@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )
    assert sorted(_stored_emails()) == ["asha@example.com", CANONICAL]

def test_password_policy_sees_the_canonical_address():
    response = client.post(
        REGISTER_URL, json={"email": "Sana@Example.com", "password": "sana@example.com"}
    )
    assert response.status_code == 422

@pytest.mark.parametrize("variant", VARIANTS)
def test_login_succeeds_whatever_case_the_address_is_typed_in(variant):
    _seed_user(CANONICAL)
    response = client.post(LOGIN_URL, json={"email": variant, "password": PASSWORD})
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]

def test_login_still_refuses_the_wrong_password():
    _seed_user(CANONICAL)
    response = client.post(
        LOGIN_URL, json={"email": "SANA@EXAMPLE.COM", "password": "not-the-password"}
    )
    assert response.status_code == 401

def test_login_still_refuses_an_unknown_address():
    response = client.post(
        LOGIN_URL, json={"email": "Nobody@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 401

def test_emailstr_folds_the_domain_but_not_the_local_part():
    from pydantic import BaseModel, EmailStr

    class _Probe(BaseModel):
        email: EmailStr

    assert _Probe(email="SANA@EXAMPLE.COM").email == "SANA@example.com"
    assert _Probe(email="  sana@example.com  ").email == CANONICAL

def test_login_finds_a_legacy_mixed_case_account():
    _seed_legacy_user("Sana@example.com")

    response = client.post(
        LOGIN_URL, json={"email": "Sana@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text

def test_the_legacy_fallback_does_not_reach_a_row_typed_differently():
    _seed_legacy_user("Sana@example.com")

    response = client.post(LOGIN_URL, json={"email": CANONICAL, "password": PASSWORD})
    assert response.status_code == 401

def test_provider_registered_address_works_on_the_patient_login_route():
    registered = client.post(
        PROVIDER_REGISTER_URL,
        json={"email": "Doc@Clinic.in", "password": PASSWORD, "full_name": "Dr Mehta"},
    )
    assert registered.status_code == 201, registered.text

    response = client.post(
        LOGIN_URL, json={"email": "Doc@Clinic.in", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text

def test_patient_registered_address_works_on_the_provider_login_route():
    assert (
        client.post(
            REGISTER_URL, json={"email": "Asha@Example.com", "password": PASSWORD}
        ).status_code
        == 200
    )

    response = client.post(
        PROVIDER_LOGIN_URL, json={"email": "Asha@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 403, response.text

def test_both_register_routes_agree_an_address_is_taken():
    assert (
        client.post(
            REGISTER_URL, json={"email": "shared@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )
    response = client.post(
        PROVIDER_REGISTER_URL,
        json={"email": "SHARED@EXAMPLE.COM", "password": PASSWORD},
    )
    assert response.status_code == 409, response.text

@pytest.mark.parametrize("variant", VARIANTS)
def test_reset_token_survives_a_case_change_between_request_and_use(variant):
    token = generate_reset_token(variant)
    assert verify_reset_token(CANONICAL, token) is True

def test_reset_token_is_single_use_across_capitalisations():
    token = generate_reset_token("Sana@Example.com")
    assert verify_reset_token(CANONICAL, token) is True
    assert verify_reset_token("SANA@EXAMPLE.COM", token) is False

def test_reset_token_still_rejects_a_wrong_token():
    generate_reset_token(CANONICAL)
    assert verify_reset_token(CANONICAL, "not-the-token") is False

def test_reset_token_still_rejects_another_accounts_token():
    token = generate_reset_token(CANONICAL)
    assert verify_reset_token("asha@example.com", token) is False

@pytest.mark.parametrize("variant", VARIANTS)
def test_verification_token_survives_a_case_change(variant):
    token = generate_verification_token(variant)
    assert verify_email_token(CANONICAL, token) is True

def test_verification_token_still_rejects_a_wrong_token():
    generate_verification_token(CANONICAL)
    assert verify_email_token(CANONICAL, "not-the-token") is False

def _reset_key(email):
    return token_store.document_id(token_store.KIND_PASSWORD_RESET, email)

def _verification_key(email):
    return token_store.document_id(token_store.KIND_EMAIL_VERIFICATION, email)

def test_reset_store_is_keyed_on_the_canonical_address():
    generate_reset_token("  SANA@Example.com  ")
    assert list(reset_token_store) == [_reset_key(CANONICAL)]

def test_reset_store_is_not_keyed_on_the_address_as_typed():
    generate_reset_token("  SANA@Example.com  ")
    assert list(reset_token_store) != [_reset_key("SANA@Example.com")]

def test_forgot_then_reset_with_different_capitalisation():
    _seed_user(CANONICAL)
    new_password = "Marigold!Sequoia88"

    forgot = client.post(FORGOT_URL, json={"email": "Sana@Example.com"})
    assert forgot.status_code == 200
    assert list(reset_token_store) == [_reset_key(CANONICAL)]

    token = generate_reset_token("SANA@EXAMPLE.COM")

    reset = client.post(
        RESET_URL,
        json={
            "email": "  Sana@Example.COM  ",
            "token": token,
            "new_password": new_password,
        },
    )
    assert reset.status_code == 200, reset.text

    login = client.post(
        LOGIN_URL, json={"email": "SANA@example.com", "password": new_password}
    )
    assert login.status_code == 200, login.text

def test_reset_password_still_refuses_a_wrong_token_through_the_route():
    _seed_user(CANONICAL)
    client.post(FORGOT_URL, json={"email": CANONICAL})

    reset = client.post(
        RESET_URL,
        json={
            "email": CANONICAL,
            "token": "not-the-token",
            "new_password": "Marigold!Sequoia88",
        },
    )
    assert reset.status_code == 400

def test_resend_verification_accepts_any_capitalisation():
    _seed_user(CANONICAL, verified=False)
    response = client.post(RESEND_URL, json={"email": "Sana@Example.com"})
    assert response.status_code == 200
    assert list(verification_token_store) == [_verification_key(CANONICAL)]

def test_verify_email_accepts_any_capitalisation():
    _seed_user(CANONICAL, verified=False)
    token = generate_verification_token("SANA@EXAMPLE.COM")

    response = client.post(
        VERIFY_URL, json={"email": "  sana@example.com ", "token": token}
    )
    assert response.status_code == 200, response.text

def test_forgot_password_response_is_unchanged_for_an_unknown_address():
    _seed_user(CANONICAL)
    known = client.post(FORGOT_URL, json={"email": "Sana@Example.com"})
    unknown = client.post(FORGOT_URL, json={"email": "Nobody@Example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()

@pytest.mark.parametrize("variant", VARIANTS)
def test_create_user_canonicalises_at_the_single_write_path(variant):
    user_id = _seed_user(variant)
    stored = UserService.get_user_by_id(user_id)
    assert stored["email"] == CANONICAL

def test_create_user_leaves_a_document_without_an_email_alone():
    user_id = UserService.create_user({"phone": "+919876543210"})
    stored = UserService.get_user_by_id(user_id)
    assert "email" not in stored or stored["email"] is None

@pytest.mark.parametrize("variant", VARIANTS)
def test_get_user_by_email_matches_across_capitalisation(variant):
    _seed_user(CANONICAL)
    assert UserService.get_user_by_email(variant) is not None

def test_get_user_by_email_returns_none_for_an_unknown_address():
    _seed_user(CANONICAL)
    assert UserService.get_user_by_email("nobody@example.com") is None

@pytest.mark.parametrize("blank", ["", "   "])
def test_get_user_by_email_returns_none_for_a_blank_address(blank):
    UserService.create_user({"phone": "+919876543210"})
    assert UserService.get_user_by_email(blank) is None

def test_get_user_by_email_finds_a_legacy_mixed_case_row():
    _seed_legacy_user("Sana@example.com")
    assert UserService.get_user_by_email("Sana@example.com") is not None

def test_get_user_by_email_costs_one_query_on_the_common_path():
    _seed_user(CANONICAL)

    queries = []
    real_where = _mock_db.collection("users").__class__.where

    def counting_where(self, field, op, value):
        queries.append((field, value))
        return real_where(self, field, op, value)

    _mock_db.collection("users").__class__.where = counting_where
    try:
        assert UserService.get_user_by_email(CANONICAL) is not None
    finally:
        _mock_db.collection("users").__class__.where = real_where

    assert queries == [("email", CANONICAL)]

def test_update_user_canonicalises_a_changed_address():
    user_id = _seed_user(CANONICAL)
    UserService.update_user(user_id, {"email": "Sana.New@Example.COM"})
    assert UserService.get_user_by_id(user_id)["email"] == "sana.new@example.com"

def test_update_user_without_an_email_is_untouched():
    user_id = _seed_user(CANONICAL)
    UserService.update_user(user_id, {"full_name": "Sana"})
    stored = UserService.get_user_by_id(user_id)
    assert stored["email"] == CANONICAL
    assert stored["full_name"] == "Sana"

from scripts import backfill_email_normalization as backfill

def test_backfill_plans_a_rewrite_for_a_legacy_row():
    _seed_legacy_user("Sana@example.com")
    rewrites, collisions = backfill.plan()

    assert collisions == []
    assert [(row["from"], row["to"]) for row in rewrites] == [
        ("Sana@example.com", CANONICAL)
    ]

def test_backfill_plans_nothing_for_rows_already_canonical():
    _seed_user(CANONICAL)
    rewrites, collisions = backfill.plan()

    assert rewrites == []
    assert collisions == []

def test_backfill_ignores_documents_with_no_address():
    UserService.create_user({"phone": "+919876543210"})
    rewrites, collisions = backfill.plan()

    assert rewrites == []
    assert collisions == []

def test_backfill_rewrites_when_applied():
    user_id = _seed_legacy_user("Sana@example.com")
    rewrites, _ = backfill.plan()

    assert backfill.apply(rewrites) == 1
    assert UserService.get_user_by_id(user_id)["email"] == CANONICAL

    assert UserService.get_user_by_email(CANONICAL) is not None

def test_backfill_refuses_to_touch_a_duplicated_address():
    _seed_legacy_user("Sana@example.com")
    _seed_user(CANONICAL)

    rewrites, collisions = backfill.plan()

    assert rewrites == []
    assert len(collisions) == 1
    assert collisions[0]["email"] == CANONICAL
    assert len(collisions[0]["documents"]) == 2

def test_backfill_still_migrates_unaffected_rows_alongside_a_collision():
    _seed_legacy_user("Sana@example.com")
    _seed_user(CANONICAL)
    _seed_legacy_user("Asha@example.com")

    rewrites, collisions = backfill.plan()

    assert [row["to"] for row in rewrites] == ["asha@example.com"]
    assert len(collisions) == 1

def test_backfill_is_a_dry_run_by_default(capsys):
    user_id = _seed_legacy_user("Sana@example.com")

    exit_code = backfill.main([])

    assert exit_code == 0
    assert "Dry run" in capsys.readouterr().out
    assert UserService.get_user_by_id(user_id)["email"] == "Sana@example.com"

def test_backfill_writes_with_apply(capsys):
    user_id = _seed_legacy_user("Sana@example.com")

    exit_code = backfill.main(["--apply"])

    assert exit_code == 0
    assert "Rewrote 1/1" in capsys.readouterr().out
    assert UserService.get_user_by_id(user_id)["email"] == CANONICAL

def test_backfill_exits_non_zero_on_a_collision(capsys):
    _seed_legacy_user("Sana@example.com")
    _seed_user(CANONICAL)

    assert backfill.main(["--apply"]) == 1
    assert "more than one account" in capsys.readouterr().out

def test_backfill_on_an_empty_collection_is_a_no_op(capsys):
    assert backfill.main(["--apply"]) == 0
    assert "Nothing to rewrite" in capsys.readouterr().out
