
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from services import access_log_service
from services.firestore_service import UserService
from services.scoring_service import get_user_scores

CONSENTS_COLLECTION = "consents"

MAX_PATIENTS_PAGE = 100
DEFAULT_PATIENTS_PAGE = 20

MAX_CONSENTS_PAGE = 100
DEFAULT_CONSENTS_PAGE = 20

_PROVIDER_VISIBLE_PROFILE_FIELDS = (
    "full_name",
    "age",
    "city",
    "state",
    "cycle_length",
    "period_duration",
    "cycle_regular",
    "last_period",
)

def _db():
    from services.firestore_service import db

    return db

def _consent_doc_id(patient_id: str, provider_id: str) -> str:
    return f"{patient_id}::{provider_id}"

def _sort_key(consent: Dict[str, Any]):
    created = consent.get("created_at")
    if isinstance(created, datetime):
        created = created.isoformat()
    return (str(created or ""), str(consent.get("id") or ""))

def _sorted_consents(consents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(consents, key=_sort_key, reverse=True)

def _provider_display_name(provider_id: str) -> Optional[str]:
    provider = UserService.get_user_by_id(provider_id) or {}
    return (
        provider.get("full_name")
        or provider.get("username")
        or provider.get("email")
    )

class ConsentService:

    @staticmethod
    def grant(patient_id: str, provider_email: str) -> Dict[str, Any]:
        provider = UserService.get_user_by_email(provider_email)
        if not provider or provider.get("role") != "provider":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No healthcare provider found with that email",
            )
        if provider["id"] == patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot share data with yourself",
            )

        doc_id = _consent_doc_id(patient_id, provider["id"])
        doc_ref = _db().collection(CONSENTS_COLLECTION).document(doc_id)
        existing = doc_ref.get()
        now = datetime.now(timezone.utc)

        consent = {
            "patient_id": patient_id,
            "provider_id": provider["id"],
            "provider_email": provider.get("email"),
            "provider_name": (
                provider.get("full_name")
                or provider.get("username")
                or provider.get("email")
            ),
            "status": "active",
            "created_at": (
                existing.to_dict().get("created_at") if existing.exists else now
            ),
            "updated_at": now,
            "revoked_at": None,
        }
        doc_ref.set(consent)
        consent["id"] = doc_id
        return consent

    @staticmethod
    def list_for_patient(patient_id: str) -> List[Dict[str, Any]]:
        consents: List[Dict[str, Any]] = []
        for doc in (
            _db().collection(CONSENTS_COLLECTION)
            .where("patient_id", "==", patient_id)
            .stream()
        ):
            data = doc.to_dict()
            data["id"] = doc.id
            consents.append(data)
        return _sorted_consents(consents)

    @staticmethod
    def list_page_for_patient(
        patient_id: str,
        *,
        limit: int = DEFAULT_CONSENTS_PAGE,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        consents = ConsentService.list_for_patient(patient_id)
        window = consents[offset : offset + limit + 1]
        return window[:limit], len(window) > limit

    @staticmethod
    def revoke(patient_id: str, consent_id: str) -> Dict[str, Any]:
        doc_ref = _db().collection(CONSENTS_COLLECTION).document(consent_id)
        doc = doc_ref.get()
        if not doc.exists or doc.to_dict().get("patient_id") != patient_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consent not found",
            )
        now = datetime.now(timezone.utc)
        doc_ref.update({"status": "revoked", "revoked_at": now, "updated_at": now})
        data = doc_ref.get().to_dict()
        data["id"] = consent_id
        return data

    @staticmethod
    def active_consent(
        patient_id: str, provider_id: str
    ) -> Optional[Dict[str, Any]]:
        doc = (
            _db().collection(CONSENTS_COLLECTION)
            .document(_consent_doc_id(patient_id, provider_id))
            .get()
        )
        if not doc.exists or doc.to_dict().get("status") != "active":
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    @staticmethod
    def list_active_for_provider(provider_id: str) -> List[Dict[str, Any]]:
        consents: List[Dict[str, Any]] = []
        for doc in (
            _db().collection(CONSENTS_COLLECTION)
            .where("provider_id", "==", provider_id)
            .stream()
        ):
            data = doc.to_dict()
            if data.get("status") != "active":
                continue
            data["id"] = doc.id
            consents.append(data)
        return _sorted_consents(consents)

class ProviderService:

    @staticmethod
    def patient_summaries(provider_id: str) -> List[Dict[str, Any]]:
        summaries, _ = ProviderService.patient_summaries_page(
            provider_id, limit=None
        )
        return summaries

    @staticmethod
    def patient_summaries_page(
        provider_id: str,
        *,
        limit: Optional[int] = DEFAULT_PATIENTS_PAGE,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        summaries: List[Dict[str, Any]] = []
        provider_name = _provider_display_name(provider_id)

        consents = ConsentService.list_active_for_provider(provider_id)
        if limit is None:
            window, has_more = consents, False
        else:
            window = consents[offset : offset + limit + 1]
            has_more = len(window) > limit
            window = window[:limit]

        for consent in window:
            patient = UserService.get_user_by_id(consent["patient_id"])
            if not patient:
                continue
            scores = get_user_scores(consent["patient_id"])
            access_log_service.record(
                provider_id=provider_id,
                patient_id=consent["patient_id"],
                view=access_log_service.VIEW_PATIENT_LIST,
                consent_id=consent.get("id"),
                provider_name=provider_name,
            )
            summaries.append(
                {
                    "patient_id": consent["patient_id"],
                    "name": (
                        patient.get("full_name")
                        or patient.get("username")
                        or consent["patient_id"]
                    ),
                    "age": patient.get("age"),
                    "city": patient.get("city"),
                    "state": patient.get("state"),
                    "sharedSince": consent["created_at"],
                    "loggedCycleCount": scores["logged_cycle_count"],
                    "mhs": scores["mhs"],
                    "cvi": scores["cvi_risk"],
                    "hasEnoughDataForInsights": scores["has_enough_data_for_insights"],
                }
            )
        return summaries, has_more

    @staticmethod
    def patient_detail(provider_id: str, patient_id: str) -> Dict[str, Any]:
        consent = ConsentService.active_consent(patient_id, provider_id)
        if not consent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have this patient's consent to view their data",
            )

        patient = UserService.get_user_by_id(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        access_log_service.record(
            provider_id=provider_id,
            patient_id=patient_id,
            view=access_log_service.VIEW_PATIENT_DETAIL,
            consent_id=consent.get("id"),
            provider_name=_provider_display_name(provider_id),
        )

        scores = get_user_scores(patient_id)

        history: List[Dict[str, Any]] = []
        for log in scores["logs"]:
            entry = dict(log)
            start = entry.get("start_date")
            entry["start_date"] = (
                start.isoformat() if hasattr(start, "isoformat") else start
            )
            history.append(entry)

        sleep_hours = [
            log.get("sleep_hours")
            for log in scores["logs"]
            if log.get("sleep_hours") is not None
        ]
        avg_sleep = round(sum(sleep_hours) / len(sleep_hours), 1) if sleep_hours else None

        profile = {
            "id": patient_id,
            "name": (
                patient.get("full_name")
                or patient.get("username")
                or patient_id
            ),
            **{field: patient.get(field) for field in _PROVIDER_VISIBLE_PROFILE_FIELDS},
        }

        return {
            "patient": profile,
            "summary": {
                "mhs": scores["mhs"],
                "cvi": scores["cvi_risk"],
                "cvi_raw": scores["cvi"],
                "loggedCycleCount": scores["logged_cycle_count"],
                "hasEnoughDataForInsights": scores["has_enough_data_for_insights"],
                "avgSleepHours": avg_sleep,
            },
            "cycleLogs": history,
            "consent": {
                "grantedAt": consent["created_at"],
                "status": consent["status"],
            },
        }
