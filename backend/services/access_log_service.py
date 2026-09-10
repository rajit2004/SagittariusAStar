
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import logger

ACCESS_LOG_COLLECTION = "access_log"

VIEW_PATIENT_LIST = "patient_list"
VIEW_PATIENT_DETAIL = "patient_detail"

VIEW_TYPES = (VIEW_PATIENT_LIST, VIEW_PATIENT_DETAIL)

MAX_ACCESS_LOG_PAGE = 100
DEFAULT_ACCESS_LOG_PAGE = 20

def _db():
    from services.firestore_service import db

    return db

def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value

def _stream_all() -> List[Any]:
    collection = _db().collection(ACCESS_LOG_COLLECTION)

    stream = getattr(collection, "stream", None)
    if callable(stream):
        try:
            return list(stream())
        except (AttributeError, NotImplementedError, TypeError):
            pass

    store = getattr(collection, "store", None)
    if store is None:
        return []
    return [collection.document(doc_id) for doc_id in list(store.keys())]

def record(
    *,
    provider_id: str,
    patient_id: str,
    view: str,
    consent_id: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> None:
    if view not in VIEW_TYPES:

        logger.warning(f"Ignoring access record with unknown view type {view!r}")
        return

    try:
        _db().collection(ACCESS_LOG_COLLECTION).add(
            {
                "provider_id": provider_id,
                "patient_id": patient_id,
                "provider_name": provider_name,
                "view": view,
                "consent_id": consent_id,
                "accessed_at": datetime.now(timezone.utc),
            }
        )
    except Exception as exc:

        logger.warning(f"Could not record provider access: {exc}")

def _entries_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for doc in _stream_all():
        data = doc.to_dict() or {}
        if data.get("patient_id") != patient_id:
            continue
        data["id"] = doc.id
        entries.append(data)

    entries.sort(key=lambda entry: str(entry.get("accessed_at") or ""), reverse=True)
    return entries

def list_for_patient(
    patient_id: str,
    *,
    limit: int = DEFAULT_ACCESS_LOG_PAGE,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], bool]:
    entries = _entries_for_patient(patient_id)
    window = entries[offset : offset + limit + 1]
    has_more = len(window) > limit

    page = [
        {
            "id": entry.get("id"),
            "providerId": entry.get("provider_id"),
            "providerName": entry.get("provider_name"),
            "view": entry.get("view"),
            "consentId": entry.get("consent_id"),
            "accessedAt": _serialize(entry.get("accessed_at")),
        }
        for entry in window[:limit]
    ]
    return page, has_more

def summary_for_patient(patient_id: str) -> Dict[str, Dict[str, Any]]:
    summary: Dict[str, Dict[str, Any]] = {}
    for entry in _entries_for_patient(patient_id):
        provider_id = entry.get("provider_id")
        if not provider_id:
            continue
        accessed_at = _serialize(entry.get("accessed_at"))
        existing = summary.get(provider_id)
        if existing is None:
            summary[provider_id] = {"viewCount": 1, "lastAccessedAt": accessed_at}
            continue
        existing["viewCount"] += 1

        if accessed_at and str(accessed_at) > str(existing["lastAccessedAt"] or ""):
            existing["lastAccessedAt"] = accessed_at
    return summary

def count_for_patient(patient_id: str) -> int:
    return len(_entries_for_patient(patient_id))

def doc_ids_for_user(user_id: str) -> List[str]:
    ids: List[str] = []
    for doc in _stream_all():
        data = doc.to_dict() or {}
        if data.get("patient_id") == user_id or data.get("provider_id") == user_id:
            ids.append(doc.id)
    return ids
