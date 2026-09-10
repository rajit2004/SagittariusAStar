
from __future__ import annotations

import csv
import hashlib
import io
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from services import access_log_service
from services import chat_link_service
from services import firestore_service as _firestore
from services import token_store
from services.firestore_service import UserService
from utils.logger import logger

EXPORT_SCHEMA_VERSION = "1.2"

USERS_COLLECTION = "users"
CYCLE_LOGS_COLLECTION = "cycle_logs"
CONVERSATIONS_COLLECTION = "conversations"
RATE_LIMITS_COLLECTION = "rate_limits"
CONSENTS_COLLECTION = "consents"

ACCESS_LOG_COLLECTION = "access_log"

CHAT_LINKS_COLLECTION = chat_link_service.CHAT_LINKS_COLLECTION

USER_DATA_COLLECTIONS: Tuple[str, ...] = (
    USERS_COLLECTION,
    CYCLE_LOGS_COLLECTION,
    CONVERSATIONS_COLLECTION,
    RATE_LIMITS_COLLECTION,
    CONSENTS_COLLECTION,
    ACCESS_LOG_COLLECTION,
    CHAT_LINKS_COLLECTION,
)

DELETION_AUDIT_COLLECTION = "deletion_audit"

RATE_LIMIT_KEY_PREFIXES: Tuple[str, ...] = ("sms", "assistant", "login", "register")

EXPORT_EXCLUDED_USER_FIELDS = frozenset({"password", "password_hash"})

DELETION_TOKEN_TTL_SECONDS = 300

_deletion_tokens = token_store.TokenNamespace(token_store.KIND_ACCOUNT_DELETION)

CSV_COLUMNS: Tuple[str, ...] = (
    "start_date",
    "end_date",
    "flow_intensity",
    "mood",
    "symptoms",
    "sleep_hours",
    "stress_level",
    "notes",
    "created_at",
    "updated_at",
)

def _db():
    return _firestore.db

def _hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value

def _doc_to_dict(doc: Any) -> Dict[str, Any]:
    data = doc.to_dict() or {}
    data = dict(data)
    data["id"] = doc.id
    return data

def _stream_collection(name: str) -> Iterable[Any]:
    collection = _db().collection(name)
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

def _query_by_user(name: str, user_id: str) -> List[Any]:
    try:
        return list(_db().collection(name).where("user_id", "==", user_id).stream())
    except Exception:
        return [
            doc
            for doc in _stream_collection(name)
            if (doc.to_dict() or {}).get("user_id") == user_id
        ]

def _rate_limit_doc_ids(user_id: str) -> List[str]:
    suffix = f":{user_id}"
    return [
        doc.id
        for doc in _stream_collection(RATE_LIMITS_COLLECTION)
        if doc.id.endswith(suffix)
        or doc.id in {f"{prefix}:{user_id}" for prefix in RATE_LIMIT_KEY_PREFIXES}
    ]

def _consent_doc_ids(user_id: str) -> List[str]:
    return [
        doc.id
        for doc in _stream_collection(CONSENTS_COLLECTION)
        if (doc.to_dict() or {}).get("patient_id") == user_id
        or (doc.to_dict() or {}).get("provider_id") == user_id
    ]

def _delete_doc(collection: str, doc_id: str) -> bool:
    try:
        _db().collection(collection).document(doc_id).delete()
        return True
    except Exception:
        logger.bind(collection=collection).warning(
            "Failed to delete one document during account purge"
        )
        return False

def build_data_summary(user_id: str) -> Dict[str, Any]:
    user = UserService.get_user_by_id(user_id) or {}
    cycle_docs = _query_by_user(CYCLE_LOGS_COLLECTION, user_id)
    cycle_logs = [_doc_to_dict(doc) for doc in cycle_docs]

    start_dates = sorted(
        d for d in (_as_date(log.get("start_date")) for log in cycle_logs) if d
    )

    conversation = _get_conversation(user_id)
    message_count = len(conversation.get("messages", []) if conversation else [])

    rate_limit_ids = _rate_limit_doc_ids(user_id)
    consent_ids = _consent_doc_ids(user_id)
    access_count = access_log_service.count_for_patient(user_id)
    chat_links = chat_link_service.links_for_user(user_id)

    identity_fields = sorted(
        field
        for field in user.keys()
        if field not in EXPORT_EXCLUDED_USER_FIELDS and user.get(field) not in (None, "")
    )

    return {
        "userId": user_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "categories": [
            {
                "key": "identity_and_profile",
                "label": "Account and health profile",
                "recordCount": 1 if user else 0,
                "storedFields": identity_fields,
                "collection": USERS_COLLECTION,
                "retentionNote": "Kept until you delete your account.",
            },
            {
                "key": "cycle_logs",
                "label": "Cycle logs, symptoms and notes",
                "recordCount": len(cycle_logs),
                "storedFields": sorted(
                    {key for log in cycle_logs for key in log.keys() if key != "id"}
                ),
                "collection": CYCLE_LOGS_COLLECTION,
                "earliestEntry": start_dates[0].isoformat() if start_dates else None,
                "latestEntry": start_dates[-1].isoformat() if start_dates else None,
                "retentionNote": "Kept until you delete your account or the individual log.",
            },
            {
                "key": "assistant_conversation",
                "label": "AI assistant conversation",
                "recordCount": message_count,
                "storedFields": ["role", "content"] if message_count else [],
                "collection": CONVERSATIONS_COLLECTION,
                "retentionNote": (
                    "A rolling window of your most recent messages; older "
                    "messages are dropped automatically."
                ),
            },
            {
                "key": "rate_limits",
                "label": "Abuse-prevention counters",
                "recordCount": len(rate_limit_ids),
                "storedFields": ["timestamps"] if rate_limit_ids else [],
                "collection": RATE_LIMITS_COLLECTION,
                "retentionNote": "Short-lived request timestamps, no health data.",
            },
            {
                "key": "consents",
                "label": "Provider data-sharing consents",
                "recordCount": len(consent_ids),
                "storedFields": (
                    ["provider_id", "provider_email", "status"] if consent_ids else []
                ),
                "collection": CONSENTS_COLLECTION,
                "retentionNote": "Kept until you revoke them or delete your account.",
            },
            {
                "key": "provider_access_log",
                "label": "Record of providers viewing your data",
                "recordCount": access_count,
                "storedFields": (
                    ["provider_id", "provider_name", "view", "accessed_at"]
                    if access_count
                    else []
                ),
                "collection": ACCESS_LOG_COLLECTION,
                "retentionNote": (
                    "Records that a provider viewed your data — never a copy "
                    "of the data itself. Kept until you delete your account."
                ),
            },
            {
                "key": "chat_links",
                "label": "Connected chat accounts",
                "recordCount": len(chat_links),
                "storedFields": (
                    ["channel", "chat_id", "linked_at"] if chat_links else []
                ),
                "collection": CHAT_LINKS_COLLECTION,
                "retentionNote": (
                    "Which Telegram chats or WhatsApp numbers can ask the "
                    "bot about your cycle. Kept until you disconnect them "
                    "or delete your account."
                ),
            },
        ],
        "totalRecords": (1 if user else 0)
        + len(cycle_logs)
        + (1 if message_count else 0)
        + len(rate_limit_ids)
        + len(consent_ids)
        + access_count
        + len(chat_links),
    }

def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None

def _get_conversation(user_id: str) -> Optional[Dict[str, Any]]:
    try:
        doc = _db().collection(CONVERSATIONS_COLLECTION).document(user_id).get()
    except Exception:
        return None
    if not getattr(doc, "exists", False):
        return None
    return doc.to_dict() or {}

def build_export_bundle(user_id: str) -> Dict[str, Any]:
    user = UserService.get_user_by_id(user_id) or {}
    profile = {
        key: _serialize(value)
        for key, value in user.items()
        if key not in EXPORT_EXCLUDED_USER_FIELDS
    }

    cycle_logs = [
        _serialize(_doc_to_dict(doc))
        for doc in _query_by_user(CYCLE_LOGS_COLLECTION, user_id)
    ]

    cycle_logs.sort(key=lambda log: str(log.get("start_date") or ""), reverse=True)

    conversation = _get_conversation(user_id) or {}
    messages = [_serialize(message) for message in conversation.get("messages", [])]

    access_log, _ = access_log_service.list_for_patient(
        user_id, limit=access_log_service.count_for_patient(user_id) or 1
    )

    chat_links = chat_link_service.links_for_user(user_id)

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "profile": profile,
        "cycle_logs": cycle_logs,
        "assistant_conversation": {
            "message_count": len(messages),
            "messages": messages,
        },
        "provider_access_log": {
            "entry_count": len(access_log),
            "entries": access_log,
        },
        "chat_links": {
            "link_count": len(chat_links),
            "links": [
                {
                    "channel": link.get("channel"),
                    "chat_id": link.get("chat_id"),
                    "linked_at": _serialize(link.get("linked_at")),
                }
                for link in chat_links
            ],
        },
        "sms_settings": {
            "enabled": bool(user.get("sms_enabled", False)),
            "phone_number": user.get("sms_phone_number") or user.get("phone") or "",
        },
        "notes": (
            "This file contains everything Rhythma stores about your account "
            "on the server. Your password is deliberately excluded. "
            "Abuse-prevention counters are excluded because they hold no "
            "health data and expire on their own."
        ),
    }

def build_cycle_logs_csv(user_id: str) -> str:
    bundle = build_export_bundle(user_id)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    for log in bundle["cycle_logs"]:
        row = {column: log.get(column, "") for column in CSV_COLUMNS}
        symptoms = log.get("symptoms")
        if isinstance(symptoms, list):

            row["symptoms"] = ";".join(str(s) for s in symptoms)
        row = {k: ("" if v is None else v) for k, v in row.items()}
        writer.writerow(row)

    return buffer.getvalue()

def export_filename(user_id: str, extension: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"rhythma-data-export-{stamp}.{extension}"

def issue_deletion_token(user_id: str) -> Tuple[str, int]:
    token = secrets.token_urlsafe(32)
    token_store.put(
        token_store.KIND_ACCOUNT_DELETION,
        user_id,
        {"token_hash": _hash_token(token), "user_id": user_id},
        timedelta(seconds=DELETION_TOKEN_TTL_SECONDS),
    )
    return token, DELETION_TOKEN_TTL_SECONDS

def verify_deletion_token(user_id: str, token: str) -> bool:
    entry = token_store.get(token_store.KIND_ACCOUNT_DELETION, user_id)
    if not entry:
        return False
    if not secrets.compare_digest(entry.get("token_hash", ""), _hash_token(token)):
        return False
    token_store.delete(token_store.KIND_ACCOUNT_DELETION, user_id)
    return True

def clear_deletion_tokens() -> None:
    token_store.clear(token_store.KIND_ACCOUNT_DELETION)

def purge_user_data(user_id: str) -> Dict[str, int]:
    counts: Dict[str, int] = {name: 0 for name in USER_DATA_COLLECTIONS}

    for doc in _query_by_user(CYCLE_LOGS_COLLECTION, user_id):
        if _delete_doc(CYCLE_LOGS_COLLECTION, doc.id):
            counts[CYCLE_LOGS_COLLECTION] += 1

    if _get_conversation(user_id) is not None:
        if _delete_doc(CONVERSATIONS_COLLECTION, user_id):
            counts[CONVERSATIONS_COLLECTION] += 1

    for doc_id in _rate_limit_doc_ids(user_id):
        if _delete_doc(RATE_LIMITS_COLLECTION, doc_id):
            counts[RATE_LIMITS_COLLECTION] += 1

    for doc_id in _consent_doc_ids(user_id):
        if _delete_doc(CONSENTS_COLLECTION, doc_id):
            counts[CONSENTS_COLLECTION] += 1

    for doc_id in access_log_service.doc_ids_for_user(user_id):
        if _delete_doc(ACCESS_LOG_COLLECTION, doc_id):
            counts[ACCESS_LOG_COLLECTION] += 1

    for link in chat_link_service.links_for_user(user_id):
        if _delete_doc(CHAT_LINKS_COLLECTION, link["id"]):
            counts[CHAT_LINKS_COLLECTION] += 1
    chat_link_service.revoke_codes_for(user_id)

    user = UserService.get_user_by_id(user_id)
    if user:
        _delete_firebase_auth_user(user.get("phone"))
        if _delete_doc(USERS_COLLECTION, user_id):
            counts[USERS_COLLECTION] += 1

    logger.bind(deleted_counts=counts).info("Purged all stored data for an account")
    return counts

def _delete_firebase_auth_user(phone: Optional[str]) -> None:
    if not phone:
        return
    try:
        import firebase_admin.auth as firebase_auth

        fb_user = firebase_auth.get_user_by_phone_number(phone)
        firebase_auth.delete_user(fb_user.uid)
    except Exception:

        logger.debug("No Firebase Auth user to delete for this account")

def _write_audit_record(user_id: str, counts: Dict[str, int]) -> None:
    try:
        _db().collection(DELETION_AUDIT_COLLECTION).document(
            _hash_user_id(user_id)
        ).set(
            {
                "user_id_hash": _hash_user_id(user_id),
                "deleted_at": datetime.now(timezone.utc),
                "deleted_counts": counts,
                "schema_version": EXPORT_SCHEMA_VERSION,
            }
        )
    except Exception:
        logger.warning("Could not write the account-deletion audit record")

def delete_account(user_id: str) -> Dict[str, Any]:

    account = UserService.get_user_by_id(user_id) or {}
    account_email = account.get("email")

    counts = purge_user_data(user_id)

    from core.auth import revoke_all_user_refresh_tokens

    revoke_all_user_refresh_tokens(user_id)
    clear_deletion_tokens_for(user_id)

    if account_email:
        from core.email_identity import normalize_email

        email_key = normalize_email(account_email)
        token_store.delete(token_store.KIND_PASSWORD_RESET, email_key)
        token_store.delete(token_store.KIND_EMAIL_VERIFICATION, email_key)

    _write_audit_record(user_id, counts)

    return {
        "deletedCounts": counts,
        "totalDeleted": sum(counts.values()),
        "deletedAt": datetime.now(timezone.utc).isoformat(),
    }

def clear_deletion_tokens_for(user_id: str) -> None:
    token_store.delete(token_store.KIND_ACCOUNT_DELETION, user_id)

def deletion_record_for(user_id: str) -> Optional[Dict[str, Any]]:
    try:
        doc = _db().collection(DELETION_AUDIT_COLLECTION).document(
            _hash_user_id(user_id)
        ).get()
    except Exception:
        return None
    if not getattr(doc, "exists", False):
        return None
    return _serialize(doc.to_dict() or {})

def account_exists(user_id: str) -> bool:
    return UserService.get_user_by_id(user_id) is not None

__all__ = [
    "CSV_COLUMNS",
    "CONSENTS_COLLECTION",
    "DELETION_AUDIT_COLLECTION",
    "DELETION_TOKEN_TTL_SECONDS",
    "EXPORT_SCHEMA_VERSION",
    "USER_DATA_COLLECTIONS",
    "account_exists",
    "build_cycle_logs_csv",
    "build_data_summary",
    "build_export_bundle",
    "clear_deletion_tokens",
    "clear_deletion_tokens_for",
    "delete_account",
    "deletion_record_for",
    "export_filename",
    "issue_deletion_token",
    "purge_user_data",
    "verify_deletion_token",
]
