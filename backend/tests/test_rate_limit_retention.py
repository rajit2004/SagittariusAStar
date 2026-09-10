from datetime import datetime, timedelta, timezone

import pytest

import services.rate_limit_service as rate_limit_service
from services.firestore_service import MockFirestoreClient
from services.rate_limit_service import (
    LEGACY_MAX_WINDOW_SECONDS,
    RateLimitService,
)

@pytest.fixture(autouse=True)
def _isolated_store(monkeypatch):
    monkeypatch.setattr(rate_limit_service, "db", MockFirestoreClient())

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _documents() -> dict:
    return rate_limit_service.db._collections.get(RateLimitService.COLLECTION, {})

def _write_raw(key: str, payload: dict) -> None:
    RateLimitService._document(key).set(payload)

def _read_raw(key: str) -> dict:
    return RateLimitService._document(key).get().to_dict() or {}

def test_a_recorded_attempt_carries_an_expiry():
    RateLimitService.is_rate_limited("login_ip:abc", limit=5, window_seconds=300)

    stored = _read_raw("login_ip:abc")

    assert "expires_at" in stored
    assert stored["window_seconds"] == 300

def test_the_expiry_is_the_newest_attempt_plus_the_window():
    before = _now()
    RateLimitService.is_rate_limited("login_ip:abc", limit=5, window_seconds=300)
    after = _now()

    expires_at = RateLimitService._as_datetime(_read_raw("login_ip:abc")["expires_at"])

    assert before + timedelta(seconds=300) <= expires_at
    assert expires_at <= after + timedelta(seconds=300)

def test_the_expiry_moves_forward_with_each_attempt():
    RateLimitService.is_rate_limited("login_ip:abc", limit=5, window_seconds=300)
    first = _read_raw("login_ip:abc")["expires_at"]

    _write_raw(
        "login_ip:abc",
        {
            "timestamps": [(_now() - timedelta(seconds=60)).isoformat()],
            "expires_at": first,
            "window_seconds": 300,
        },
    )
    RateLimitService.is_rate_limited("login_ip:abc", limit=5, window_seconds=300)
    second = _read_raw("login_ip:abc")["expires_at"]

    assert second > first

def test_the_over_limit_write_carries_an_expiry_too():
    for _ in range(3):
        RateLimitService.is_rate_limited("login_ip:abc", limit=3, window_seconds=300)

    blocked = RateLimitService.is_rate_limited("login_ip:abc", limit=3, window_seconds=300)

    assert blocked is not None
    assert "expires_at" in _read_raw("login_ip:abc")

def test_timestamps_are_written_as_strings():
    RateLimitService.is_rate_limited("login_ip:abc", limit=5, window_seconds=300)

    stored = _read_raw("login_ip:abc")

    assert all(isinstance(entry, str) for entry in stored["timestamps"])

def test_purge_deletes_a_bucket_whose_window_has_closed():
    _write_raw(
        "login_ip:dead",
        {
            "timestamps": [(_now() - timedelta(hours=2)).isoformat()],
            "expires_at": (_now() - timedelta(hours=1)).isoformat(),
            "window_seconds": 900,
        },
    )

    assert RateLimitService.purge_expired() == 1
    assert "login_ip:dead" not in _documents()

def test_purge_leaves_a_live_bucket_alone():
    RateLimitService.is_rate_limited("login_ip:live", limit=5, window_seconds=900)

    assert RateLimitService.purge_expired() == 0
    assert "login_ip:live" in _documents()

def test_purge_does_not_release_someone_who_is_currently_locked_out():
    for _ in range(3):
        RateLimitService.is_rate_limited("login_ip:blocked", limit=3, window_seconds=900)

    RateLimitService.purge_expired()

    assert (
        RateLimitService.is_rate_limited("login_ip:blocked", limit=3, window_seconds=900)
        is not None
    )

def test_purge_reports_how_many_it_took():
    for n in range(4):
        _write_raw(
            f"login_ip:dead{n}",
            {
                "timestamps": [(_now() - timedelta(hours=2)).isoformat()],
                "expires_at": (_now() - timedelta(hours=1)).isoformat(),
                "window_seconds": 900,
            },
        )
    RateLimitService.is_rate_limited("login_ip:live", limit=5, window_seconds=900)

    assert RateLimitService.purge_expired() == 4
    assert list(_documents()) == ["login_ip:live"]

def test_purge_on_an_empty_collection_is_a_no_op():
    assert RateLimitService.purge_expired() == 0

def test_an_expiry_exactly_now_is_expired():
    _write_raw(
        "login_ip:edge",
        {"timestamps": [], "expires_at": _now().isoformat(), "window_seconds": 900},
    )

    assert RateLimitService.purge_expired() == 1

def test_a_legacy_bucket_older_than_every_window_is_swept():
    _write_raw(
        "login_ip:legacy-old",
        {"timestamps": [(_now() - timedelta(seconds=LEGACY_MAX_WINDOW_SECONDS + 60)).isoformat()]},
    )

    assert RateLimitService.purge_expired() == 1

def test_a_recent_legacy_bucket_is_kept():
    _write_raw(
        "login_ip:legacy-recent",
        {"timestamps": [(_now() - timedelta(seconds=60)).isoformat()]},
    )

    assert RateLimitService.purge_expired() == 0
    assert "login_ip:legacy-recent" in _documents()

def test_a_legacy_bucket_holding_naive_datetimes_is_still_read():
    naive_utc = (_now() - timedelta(seconds=LEGACY_MAX_WINDOW_SECONDS + 60)).replace(
        tzinfo=None
    )
    _write_raw("login_ip:legacy-naive", {"timestamps": [naive_utc]})

    assert RateLimitService.purge_expired() == 1

def test_a_bucket_with_nothing_readable_in_it_is_swept():
    _write_raw("login_ip:junk", {"timestamps": ["not-a-timestamp", None, 42]})

    assert RateLimitService.purge_expired() == 1

def test_a_bucket_with_no_fields_at_all_is_swept():
    _write_raw("login_ip:empty", {})

    assert RateLimitService.purge_expired() == 1

def test_an_unparseable_expiry_falls_back_to_the_timestamps():
    _write_raw(
        "login_ip:bad-expiry",
        {
            "timestamps": [(_now() - timedelta(seconds=30)).isoformat()],
            "expires_at": "sometime next week",
        },
    )

    assert RateLimitService.purge_expired() == 0

def test_a_legacy_document_is_still_enforced_correctly():
    recent = [(_now() - timedelta(seconds=n)).isoformat() for n in (30, 20, 10)]
    _write_raw("login_ip:mixed", {"timestamps": recent})

    assert (
        RateLimitService.is_rate_limited("login_ip:mixed", limit=3, window_seconds=900)
        is not None
    )

def test_a_timestamps_field_that_is_not_a_list_is_ignored():
    _write_raw("login_ip:wrong-type", {"timestamps": "yesterday"})

    assert (
        RateLimitService.is_rate_limited("login_ip:wrong-type", limit=1, window_seconds=900)
        is None
    )

def test_retry_after_is_measured_from_the_oldest_attempt_whatever_the_order():
    unordered = [
        (_now() - timedelta(seconds=10)).isoformat(),
        (_now() - timedelta(seconds=200)).isoformat(),
        (_now() - timedelta(seconds=100)).isoformat(),
    ]
    _write_raw("login_ip:unordered", {"timestamps": unordered})

    remaining = RateLimitService.is_rate_limited(
        "login_ip:unordered", limit=3, window_seconds=300
    )

    assert remaining is not None
    assert 90 <= remaining <= 105

def test_reset_removes_the_document_entirely():
    RateLimitService.is_rate_limited("login_account:abc", limit=5, window_seconds=900)

    RateLimitService.reset("login_account:abc")

    assert "login_account:abc" not in _documents()
