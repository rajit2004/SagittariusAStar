
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, MutableMapping, Optional

from services import firestore_service as _firestore
from utils.logger import logger

TOKENS_COLLECTION = "auth_tokens"

KIND_REFRESH = "refresh"
KIND_PASSWORD_RESET = "password_reset"
KIND_EMAIL_VERIFICATION = "email_verification"
KIND_ACCOUNT_DELETION = "account_deletion"

ALL_KINDS = (
    KIND_REFRESH,
    KIND_PASSWORD_RESET,
    KIND_EMAIL_VERIFICATION,
    KIND_ACCOUNT_DELETION,
)

def _collection():
    return _firestore.db.collection(TOKENS_COLLECTION)

def hash_value(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()

def document_id(kind: str, key: str) -> str:
    return f"{kind}:{hash_value(key)}"

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _as_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None

def _stream() -> Iterator[Any]:
    collection = _collection()
    stream = getattr(collection, "stream", None)
    if callable(stream):
        try:
            yield from stream()
            return
        except (AttributeError, NotImplementedError, TypeError):
            pass

    store = getattr(collection, "store", None)
    if store is None:
        return
    for doc_id in list(store.keys()):
        yield collection.document(doc_id)

def put(
    kind: str,
    key: str,
    payload: Dict[str, Any],
    ttl: timedelta,
) -> None:
    document = dict(payload)
    document["kind"] = kind
    document["expires_at"] = (_now() + ttl).isoformat()
    document["created_at"] = _now().isoformat()
    _collection().document(document_id(kind, key)).set(document)

def get(kind: str, key: str) -> Optional[Dict[str, Any]]:
    try:
        doc = _collection().document(document_id(kind, key)).get()
    except Exception:
        logger.bind(kind=kind).warning("Could not read an auth token record")
        return None

    if not getattr(doc, "exists", False):
        return None

    data = doc.to_dict() or {}
    expires_at = _as_datetime(data.get("expires_at"))
    if expires_at is None or expires_at <= _now():
        delete(kind, key)
        return None
    return data

def delete(kind: str, key: str) -> bool:
    doc_id = document_id(kind, key)
    try:
        existing = _collection().document(doc_id).get()
        if not getattr(existing, "exists", False):
            return False
        _collection().document(doc_id).delete()
        return True
    except Exception:
        logger.bind(kind=kind).warning("Could not delete an auth token record")
        return False

def delete_for_user(kind: str, user_id: str) -> int:
    removed = 0
    for doc in list(_stream()):
        data = doc.to_dict() or {}
        if data.get("kind") != kind or data.get("user_id") != user_id:
            continue
        try:
            _collection().document(doc.id).delete()
            removed += 1
        except Exception:
            logger.bind(kind=kind).warning("Could not revoke an auth token record")
    return removed

def keys_of_kind(kind: str) -> List[str]:
    return [
        doc.id for doc in _stream() if (doc.to_dict() or {}).get("kind") == kind
    ]

def entries_of_kind(kind: str) -> Dict[str, Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}
    for doc in _stream():
        data = doc.to_dict() or {}
        if data.get("kind") == kind:
            found[doc.id] = data
    return found

def purge_expired(kind: Optional[str] = None) -> int:
    now = _now()
    removed = 0
    for doc in list(_stream()):
        data = doc.to_dict() or {}
        if kind is not None and data.get("kind") != kind:
            continue
        expires_at = _as_datetime(data.get("expires_at"))
        if expires_at is not None and expires_at > now:
            continue
        try:
            _collection().document(doc.id).delete()
            removed += 1
        except Exception:
            pass
    if removed:
        logger.bind(removed=removed).info("Swept expired auth tokens")
    return removed

def clear(kind: Optional[str] = None) -> None:
    if kind is None:
        try:
            if hasattr(_firestore.db, "_collections"):
                _firestore.db._collections.pop(TOKENS_COLLECTION, None)
                return
        except Exception:
            pass

    for doc in list(_stream()):
        if kind is not None and (doc.to_dict() or {}).get("kind") != kind:
            continue
        try:
            _collection().document(doc.id).delete()
        except Exception:
            pass

class TokenNamespace(MutableMapping):

    def __init__(self, kind: str):
        self.kind = kind

    def __getitem__(self, key: str) -> Dict[str, Any]:
        entries = entries_of_kind(self.kind)
        if key in entries:
            return entries[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: Dict[str, Any]) -> None:
        document = dict(value)
        document["kind"] = self.kind
        expires_at = document.get("expires_at")
        if isinstance(expires_at, datetime):
            document["expires_at"] = expires_at.isoformat()
        _collection().document(key).set(document)

    def __delitem__(self, key: str) -> None:
        try:
            _collection().document(key).delete()
        except Exception:
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(entries_of_kind(self.kind))

    def __len__(self) -> int:
        return len(entries_of_kind(self.kind))

    def clear(self) -> None:
        clear(self.kind)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, dict):
            return entries_of_kind(self.kind) == other
        return NotImplemented

    def __hash__(self):
        raise TypeError("TokenNamespace is unhashable")

    def __repr__(self) -> str:
        return f"TokenNamespace({self.kind!r}, {len(self)} entries)"

__all__ = [
    "ALL_KINDS",
    "KIND_ACCOUNT_DELETION",
    "KIND_EMAIL_VERIFICATION",
    "KIND_PASSWORD_RESET",
    "KIND_REFRESH",
    "TOKENS_COLLECTION",
    "TokenNamespace",
    "clear",
    "delete",
    "delete_for_user",
    "document_id",
    "entries_of_kind",
    "get",
    "hash_value",
    "keys_of_kind",
    "purge_expired",
    "put",
]
