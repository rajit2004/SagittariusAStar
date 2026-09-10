
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services import firestore_service as _firestore
from utils.logger import logger

CHAT_LINKS_COLLECTION = "chat_links"

CHAT_LINK_CODES_COLLECTION = "chat_link_codes"

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8

DEFAULT_CODE_TTL_SECONDS = 600

SUPPORTED_CHANNELS = ("telegram", "whatsapp")

def code_ttl_seconds() -> int:
    raw = os.getenv("CHAT_LINK_CODE_TTL_SECONDS")
    if raw is None:
        return DEFAULT_CODE_TTL_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_CODE_TTL_SECONDS

    return value if value > 0 else DEFAULT_CODE_TTL_SECONDS

def normalize_code(raw: str) -> str:
    return "".join(ch for ch in (raw or "").upper() if ch in CODE_ALPHABET)

def _hash_code(code: str) -> str:
    return hashlib.sha256(normalize_code(code).encode("utf-8")).hexdigest()

def link_document_id(channel: str, chat_id: str) -> str:
    return f"{channel}:{chat_id}"

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

def _collection(name: str):
    return _firestore.db.collection(name)

def _stream(name: str):
    collection = _collection(name)
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

def issue_link_code(user_id: str, channel: str) -> Dict[str, Any]:
    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(f"Unsupported channel {channel!r}.")

    revoke_codes_for(user_id, channel=channel)

    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    ttl = code_ttl_seconds()
    expires_at = _now() + timedelta(seconds=ttl)

    _collection(CHAT_LINK_CODES_COLLECTION).document(_hash_code(code)).set(
        {
            "user_id": user_id,
            "channel": channel,
            "expires_at": expires_at.isoformat(),
            "created_at": _now().isoformat(),
        }
    )

    logger.bind(channel=channel).info("Issued a chat link code")
    return {"code": code, "channel": channel, "expiresInSeconds": ttl}

def revoke_codes_for(user_id: str, channel: Optional[str] = None) -> int:
    removed = 0
    for doc in list(_stream(CHAT_LINK_CODES_COLLECTION)):
        data = doc.to_dict() or {}
        if data.get("user_id") != user_id:
            continue
        if channel is not None and data.get("channel") != channel:
            continue
        _collection(CHAT_LINK_CODES_COLLECTION).document(doc.id).delete()
        removed += 1
    return removed

def purge_expired_codes() -> int:
    now = _now()
    removed = 0
    for doc in list(_stream(CHAT_LINK_CODES_COLLECTION)):
        expires_at = _as_datetime((doc.to_dict() or {}).get("expires_at"))
        if expires_at is None or expires_at <= now:
            _collection(CHAT_LINK_CODES_COLLECTION).document(doc.id).delete()
            removed += 1
    return removed

def redeem_link_code(channel: str, chat_id: str, code: str) -> Optional[str]:
    normalized = normalize_code(code)
    if len(normalized) != CODE_LENGTH:
        return None

    doc = _collection(CHAT_LINK_CODES_COLLECTION).document(_hash_code(normalized)).get()
    if not getattr(doc, "exists", False):
        return None

    data = doc.to_dict() or {}
    if data.get("channel") != channel:
        return None

    expires_at = _as_datetime(data.get("expires_at"))
    if expires_at is None or expires_at <= _now():
        _collection(CHAT_LINK_CODES_COLLECTION).document(doc.id).delete()
        return None

    user_id = data.get("user_id")
    if not user_id:
        return None

    _collection(CHAT_LINK_CODES_COLLECTION).document(doc.id).delete()

    _collection(CHAT_LINKS_COLLECTION).document(link_document_id(channel, chat_id)).set(
        {
            "user_id": user_id,
            "channel": channel,
            "chat_id": str(chat_id),
            "linked_at": _now().isoformat(),
        }
    )
    purge_expired_codes()

    logger.bind(channel=channel).info("Linked a chat to an account")
    return user_id

def resolve_user_id(channel: str, chat_id: str) -> Optional[str]:
    if not chat_id:
        return None
    try:
        doc = (
            _collection(CHAT_LINKS_COLLECTION)
            .document(link_document_id(channel, str(chat_id)))
            .get()
        )
    except Exception:
        logger.bind(channel=channel).warning("Could not read chat link")
        return None

    if not getattr(doc, "exists", False):
        return None
    return (doc.to_dict() or {}).get("user_id") or None

def unlink(channel: str, chat_id: str) -> bool:
    doc_id = link_document_id(channel, str(chat_id))
    doc = _collection(CHAT_LINKS_COLLECTION).document(doc_id).get()
    if not getattr(doc, "exists", False):
        return False
    _collection(CHAT_LINKS_COLLECTION).document(doc_id).delete()
    logger.bind(channel=channel).info("Unlinked a chat from an account")
    return True

def links_for_user(user_id: str) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    for doc in _stream(CHAT_LINKS_COLLECTION):
        data = doc.to_dict() or {}
        if data.get("user_id") != user_id:
            continue
        entry = dict(data)
        entry["id"] = doc.id
        found.append(entry)
    return found

def clear_all() -> None:
    for name in (CHAT_LINKS_COLLECTION, CHAT_LINK_CODES_COLLECTION):
        try:
            if hasattr(_firestore.db, "_collections"):
                _firestore.db._collections.pop(name, None)
        except Exception:
            pass

__all__ = [
    "CHAT_LINKS_COLLECTION",
    "CHAT_LINK_CODES_COLLECTION",
    "CODE_ALPHABET",
    "CODE_LENGTH",
    "SUPPORTED_CHANNELS",
    "clear_all",
    "code_ttl_seconds",
    "issue_link_code",
    "link_document_id",
    "links_for_user",
    "normalize_code",
    "purge_expired_codes",
    "redeem_link_code",
    "resolve_user_id",
    "revoke_codes_for",
    "unlink",
]
