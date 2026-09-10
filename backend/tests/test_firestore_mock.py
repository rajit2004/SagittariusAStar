from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from services.firestore_service import (
    MockFirestoreClient,
    MockNotFound,
    MockQuery,
    firestore,
)

@pytest.fixture
def db():
    return MockFirestoreClient()

def _ids(stream):
    return [doc.id for doc in stream]

def test_set_does_not_alias_the_callers_dict(db):
    payload = {"status": "active"}
    db.collection("consents").document("c1").set(payload)

    payload["status"] = "revoked"

    assert db.collection("consents").document("c1").to_dict() == {"status": "active"}

def test_two_documents_set_from_one_dict_are_independent(db):
    payload = {"count": 1}
    db.collection("counters").document("a").set(payload)
    db.collection("counters").document("b").set(payload)

    db.collection("counters").document("a").update({"count": 99})

    assert db.collection("counters").document("b").to_dict() == {"count": 1}

def test_set_replaces_rather_than_merges(db):
    doc = db.collection("users").document("u1")
    doc.set({"email": "a@example.com", "role": "patient"})
    doc.set({"email": "a@example.com"})

    assert db.collection("users").document("u1").to_dict() == {
        "email": "a@example.com"
    }

def test_set_marks_the_document_as_existing(db):
    doc = db.collection("users").document("u1")
    assert doc.exists is False

    doc.set({"email": "a@example.com"})

    assert doc.exists is True
    assert db.collection("users").document("u1").exists is True

def test_add_does_not_alias_the_callers_dict(db):
    payload = {"user_id": "u1"}
    _, ref = db.collection("cycle_logs").add(payload)

    payload["user_id"] = "someone-else"

    assert ref.to_dict() == {"user_id": "u1"}
    assert db.collection("cycle_logs").document(ref.id).to_dict() == {"user_id": "u1"}

def test_to_dict_returns_a_copy(db):
    db.collection("users").document("u1").set({"email": "a@example.com"})

    read = db.collection("users").document("u1").to_dict()
    read["email"] = "tampered@example.com"

    assert db.collection("users").document("u1").to_dict()["email"] == "a@example.com"

def test_update_does_not_alias_the_callers_dict(db):
    db.collection("users").document("u1").set({"email": "a@example.com"})

    patch = {"role": "provider"}
    db.collection("users").document("u1").update(patch)
    patch["role"] = "admin"

    assert db.collection("users").document("u1").to_dict()["role"] == "provider"

def test_update_on_a_missing_document_raises(db):
    with pytest.raises(MockNotFound):
        db.collection("users").document("gone").update({"email": "a@example.com"})

def test_update_after_delete_raises(db):
    doc = db.collection("users").document("u1")
    doc.set({"email": "a@example.com"})
    doc.delete()

    with pytest.raises(MockNotFound):
        db.collection("users").document("u1").update({"email": "b@example.com"})

def test_update_merges_into_an_existing_document(db):
    db.collection("users").document("u1").set({"email": "a@example.com", "age": 27})

    db.collection("users").document("u1").update({"age": 28, "city": "Pune"})

    assert db.collection("users").document("u1").to_dict() == {
        "email": "a@example.com",
        "age": 28,
        "city": "Pune",
    }

def test_delete_is_idempotent(db):
    db.collection("rate_limits").document("nope").delete()
    db.collection("rate_limits").document("nope").delete()

@pytest.fixture
def logs(db):
    collection = db.collection("cycle_logs")
    collection.document("middle").set({"start_date": date(2026, 2, 1)})
    collection.document("oldest").set({"start_date": date(2026, 1, 1)})
    collection.document("newest").set({"start_date": date(2026, 3, 1)})
    return collection

def test_collection_order_by_actually_orders(logs):
    assert _ids(logs.order_by("start_date").stream()) == ["oldest", "middle", "newest"]

def test_collection_order_by_honours_descending(logs):
    ordered = logs.order_by("start_date", firestore.Query.DESCENDING)
    assert _ids(ordered.stream()) == ["newest", "middle", "oldest"]

def test_collection_limit_actually_limits(logs):
    newest_first = logs.order_by("start_date", firestore.Query.DESCENDING).limit(1)
    assert _ids(newest_first.stream()) == ["newest"]

def test_collection_offset_actually_skips(logs):
    ordered = logs.order_by("start_date").offset(1)
    assert _ids(ordered.stream()) == ["middle", "newest"]

def test_collection_stream_returns_every_document(logs):
    assert sorted(_ids(logs.stream())) == ["middle", "newest", "oldest"]

def test_collection_stream_is_empty_for_an_unknown_collection(db):
    assert list(db.collection("never-written").stream()) == []

def test_a_chain_behaves_the_same_with_or_without_a_leading_filter(logs):
    without_filter = logs.order_by("start_date").limit(2)
    with_filter = logs.where("start_date", ">=", date(2026, 1, 1)).order_by(
        "start_date"
    ).limit(2)

    assert _ids(without_filter.stream()) == _ids(with_filter.stream())

def test_a_shared_base_query_is_not_rewritten_by_a_second_chain(logs):
    base = logs.order_by("start_date")
    page = base.limit(2)
    head = base.limit(1)

    assert len(_ids(page.stream())) == 2
    assert len(_ids(head.stream())) == 1

def test_where_returns_a_new_query_and_leaves_the_original_alone(logs):
    base = MockQuery(logs._all_documents())
    narrowed = base.where("start_date", ">=", date(2026, 2, 1))

    assert len(list(base.stream())) == 3
    assert len(list(narrowed.stream())) == 2

def test_a_narrowing_filter_keeps_the_ordering_already_applied(logs):
    query = (
        logs.order_by("start_date", firestore.Query.DESCENDING)
        .where("start_date", ">=", date(2026, 2, 1))
    )
    assert _ids(query.stream()) == ["newest", "middle"]

def test_dates_and_datetimes_interleave_by_value(db):
    collection = db.collection("cycle_logs")
    collection.document("b").set({"at": datetime(2026, 2, 1, tzinfo=timezone.utc)})
    collection.document("a").set({"at": date(2026, 1, 1)})
    collection.document("c").set({"at": datetime(2026, 3, 1, tzinfo=timezone.utc)})

    assert _ids(collection.order_by("at").stream()) == ["a", "b", "c"]

def test_offset_is_applied_before_limit(db):
    collection = db.collection("items")
    for i in range(5):
        collection.document(f"d{i}").set({"n": i})

    page = collection.order_by("n").offset(2).limit(2)
    assert _ids(page.stream()) == ["d2", "d3"]

@pytest.fixture
def numbers(db):
    collection = db.collection("items")
    for i in range(1, 4):
        collection.document(f"d{i}").set({"n": i, "tag": "x" if i < 3 else "y"})
    return collection

@pytest.mark.parametrize(
    "op,value,expected",
    [
        ("==", 2, ["d2"]),
        ("!=", 2, ["d1", "d3"]),
        (">", 2, ["d3"]),
        (">=", 2, ["d2", "d3"]),
        ("<", 2, ["d1"]),
        ("<=", 2, ["d1", "d2"]),
    ],
)
def test_supported_operators(numbers, op, value, expected):
    assert sorted(_ids(numbers.where("n", op, value).stream())) == expected

def test_an_unsupported_operator_is_refused_loudly(numbers):
    with pytest.raises(NotImplementedError):
        numbers.where("n", "in", [1, 2])

    with pytest.raises(NotImplementedError):
        MockQuery(numbers._all_documents()).where("tag", "array_contains", "x")

def test_comparisons_skip_documents_missing_the_field(db):
    collection = db.collection("items")
    collection.document("has").set({"n": 5})
    collection.document("lacks").set({"other": 1})

    assert _ids(collection.where("n", ">", 0).stream()) == ["has"]

def test_auto_ids_are_per_collection(db):
    _, user = db.collection("users").add({"email": "a@example.com"})
    _, log = db.collection("cycle_logs").add({"user_id": "u1"})

    assert user.id == "mock-doc-id-1"
    assert log.id == "mock-doc-id-1"

def test_auto_ids_do_not_collide_within_a_collection(db):
    ids = {db.collection("users").add({"n": i})[1].id for i in range(5)}
    assert len(ids) == 5

def test_a_fresh_collection_handle_sees_the_same_data(db):
    db.collection("users").document("u1").set({"email": "a@example.com"})
    assert db.collection("users").document("u1").exists is True

def test_two_clients_do_not_share_state():
    first, second = MockFirestoreClient(), MockFirestoreClient()
    first.collection("users").document("u1").set({"email": "a@example.com"})

    assert second.collection("users").document("u1").exists is False

def test_the_rate_limiter_round_trips_through_the_stricter_mock():
    import services.firestore_service as fs
    import services.rate_limit_service as rl

    client = MockFirestoreClient()
    original_fs, original_rl = fs.db, rl.db
    fs.db, rl.db = client, client
    try:
        assert rl.RateLimitService.is_rate_limited("k", limit=2, window_seconds=60) is None
        assert rl.RateLimitService.is_rate_limited("k", limit=2, window_seconds=60) is None

        remaining = rl.RateLimitService.is_rate_limited("k", limit=2, window_seconds=60)
        assert remaining is not None and remaining >= 1

        rl.RateLimitService.reset("k")
        assert rl.RateLimitService.is_rate_limited("k", limit=2, window_seconds=60) is None
    finally:
        fs.db, rl.db = original_fs, original_rl

def test_an_expired_window_does_not_count_against_the_limit():
    import services.firestore_service as fs
    import services.rate_limit_service as rl

    client = MockFirestoreClient()
    original_fs, original_rl = fs.db, rl.db
    fs.db, rl.db = client, client
    try:
        stale = datetime.now(timezone.utc) - timedelta(seconds=120)
        client.collection("rate_limits").document("k").set({"timestamps": [stale]})

        assert rl.RateLimitService.is_rate_limited("k", limit=1, window_seconds=60) is None
    finally:
        fs.db, rl.db = original_fs, original_rl
