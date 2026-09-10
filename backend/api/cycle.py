from fastapi import APIRouter, Depends, HTTPException, Query, status
from core.auth import get_current_user
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from core.cycle_validation import (
    FLOW_INTENSITIES,
    MOODS,
    loggable_values,
    normalize_choice,
    normalize_notes,
    normalize_symptoms,
    validate_end_date,
    validate_sleep_hours,
    validate_start_date,
    validate_stress_level,
)
from services.firestore_service import CycleService, UserService
from services.prediction_service import DEFAULT_FORECAST_HORIZON, predict

class _LoggableFields(BaseModel):

    end_date: Optional[date] = None
    flow_intensity: Optional[str] = None
    mood: Optional[str] = None
    symptoms: Optional[List[str]] = None
    sleep_hours: Optional[float] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None
    water_intake: Optional[int] = None
    medications: Optional[List[dict]] = None

    @field_validator("flow_intensity")
    @classmethod
    def _check_flow(cls, value):
        return normalize_choice(value, FLOW_INTENSITIES, "flow_intensity")

    @field_validator("mood")
    @classmethod
    def _check_mood(cls, value):
        return normalize_choice(value, MOODS, "mood")

    @field_validator("symptoms")
    @classmethod
    def _check_symptoms(cls, value):
        return normalize_symptoms(value)

    @field_validator("sleep_hours")
    @classmethod
    def _check_sleep(cls, value):
        return validate_sleep_hours(value)

    @field_validator("stress_level")
    @classmethod
    def _check_stress(cls, value):
        return validate_stress_level(value)

    @field_validator("notes")
    @classmethod
    def _check_notes(cls, value):
        return normalize_notes(value)

class CycleLog(_LoggableFields):
    start_date: date

    @field_validator("start_date")
    @classmethod
    def _check_start(cls, value):
        return validate_start_date(value)

    @model_validator(mode="after")
    def _check_range(self):

        validate_end_date(self.start_date, self.end_date)
        return self

class CycleLogUpdate(_LoggableFields):

    @field_validator("end_date")
    @classmethod
    def _check_end_alone(cls, value):
        return validate_end_date(None, value)

class CycleLogResponse(BaseModel):
    message: str
    id: str
    data: CycleLog

class CycleHistoryEntry(BaseModel):

    model_config = {"extra": "allow"}

    id: str
    start_date: Optional[Any] = None
    end_date: Optional[Any] = None
    flow_intensity: Optional[str] = None
    mood: Optional[str] = None
    symptoms: Optional[List[str]] = None
    sleep_hours: Optional[float] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None
    cycle_length: Optional[int] = Field(None, description="Days from this log's start_date to the next log's start_date, or null if this is the newest log.")

class CycleHistoryPage(BaseModel):

    limit: int = Field(..., description="How many entries were requested.")
    offset: int = Field(..., description="How many entries were skipped.")
    count: int = Field(..., description="How many entries this page holds.")
    total_count: int = Field(..., description="Total number of entries in the history matching the filter.")
    hasMore: bool = Field(
        ...,
        description=(
            "True when at least one more entry exists past this page. "
            "Derived from fetching one extra document rather than from a "
            "count query, so paging costs no extra round trip."
        ),
    )
    nextOffset: Optional[int] = Field(
        None,
        description="Offset for the next page, or null when this is the last one.",
    )

class CycleHistoryResponse(BaseModel):
    message: str
    entries: List[CycleHistoryEntry]
    page: CycleHistoryPage

class CycleLogUpdateResponse(BaseModel):
    message: str
    id: str
    updated_fields: dict

class CycleLogDeleteResponse(BaseModel):
    message: str
    id: str

class BatchCycleLogItem(BaseModel):
    start_date: date
    end_date: Optional[date] = None
    flow_intensity: Optional[str] = None
    mood: Optional[str] = None
    symptoms: Optional[List[str]] = None
    sleep_hours: Optional[float] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None

class BatchCycleResultItem(BaseModel):
    date_key: str
    status: str
    error: Optional[str] = None

class BatchCycleRequest(BaseModel):
    items: List[BatchCycleLogItem]

class BatchCycleResponse(BaseModel):
    results: List[BatchCycleResultItem]

class BatchDeleteRequest(BaseModel):
    date_keys: List[str]

class BatchDeleteResultItem(BaseModel):
    date_key: str
    status: str
    error: Optional[str] = None

class BatchDeleteResponse(BaseModel):
    results: List[BatchDeleteResultItem]

class CycleLengthEstimateModel(BaseModel):
    days: int = Field(..., description="Estimated cycle length in days.")
    source: str = Field(
        ...,
        description=(
            "Where the estimate came from: logged_history, "
            "declared_cycle_length (from onboarding), or population_default."
        ),
    )
    confidence: str = Field(..., description="high, medium, or low.")
    sampleSize: int = Field(
        ..., description="Number of past cycles the estimate is based on."
    )
    spreadDays: float = Field(
        ..., description="Typical variation between this user's cycles, in days."
    )
    excludedCycleLengths: List[int] = Field(
        default_factory=list,
        description=(
            "Cycle lengths discarded as implausible or as statistical "
            "outliers, listed so the estimate is auditable."
        ),
    )

class PredictedRange(BaseModel):
    earliest: Optional[str] = None
    latest: Optional[str] = None

class OvulationEstimate(BaseModel):
    date: Optional[str] = None
    isEstimate: bool = True

class FertileWindowEstimate(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    isEstimate: bool = True
    notForContraception: bool = True

class PredictionResponse(BaseModel):
    today: str
    cycleLength: CycleLengthEstimateModel
    lastPeriodStart: Optional[str] = None
    currentCycleDay: Optional[int] = None
    phase: str
    nextPeriodDate: Optional[str] = None
    daysUntilNextPeriod: Optional[int] = Field(
        None,
        description=(
            "Negative when the period is late. Deliberately not clamped at "
            "zero — 'due today' and 'five days late' are different answers."
        ),
    )
    isOverdue: bool = False
    daysOverdue: int = 0
    predictedRange: PredictedRange
    ovulation: OvulationEstimate
    fertileWindow: FertileWindowEstimate
    upcomingPeriods: List[str] = Field(default_factory=list)
    confidence: str
    disclaimer: str

router = APIRouter(tags=["Cycle Tracking"])

def _submitted_fields(model: BaseModel, *, skip: Tuple[str, ...] = ()) -> Dict[str, Any]:
    dumped = model.model_dump()
    return {
        key: value
        for key, value in dumped.items()
        if key in model.model_fields_set and key not in skip
    }

def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None

@router.get(
    "/loggable-values",
    summary="The values this server accepts in a cycle log",
    description=(
        "The flow intensities, moods and symptom suggestions a client may "
        "offer, and the bounds on the numeric and free-text fields.\n\n"
        "Served so the options a user is shown come from the same place as "
        "the rules she is judged against, rather than being retyped in each "
        "client and going stale — the same reasoning behind "
        "`GET /auth/password-requirements`.\n\n"
        "`symptomsAreOpenEnded` is true: `knownSymptoms` is the suggested "
        "chip set, not a closed list, and a symptom outside it is accepted "
        "so long as it is within the length and count limits."
    ),
)
async def get_loggable_values(current_user: dict = Depends(get_current_user)):
    return loggable_values()

@router.post(
    "/batch",
    response_model=BatchCycleResponse,
    summary="Batch upsert cycle logs",
    description="Accepts a list of cycle log upserts and processes them. Returns per-item results indicating success or failure.",
)
async def batch_upsert_cycle_logs(
    batch: BatchCycleRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    results: List[BatchCycleResultItem] = []

    for item in batch.items:
        try:
            fields = {k: v for k, v in item.model_dump().items() if k != "start_date" and v is not None}
            CycleService.upsert_log(user_id, item.start_date, fields)
            results.append(BatchCycleResultItem(
                date_key=item.start_date.isoformat(),
                status="ok",
            ))
        except Exception as e:
            results.append(BatchCycleResultItem(
                date_key=item.start_date.isoformat(),
                status="error",
                error=str(e),
            ))

    return {"results": results}

@router.post(
    "/batch-delete",
    response_model=BatchDeleteResponse,
    summary="Batch delete cycle logs",
    description="Accepts a list of date keys and deletes the corresponding cycle logs. Returns per-item results.",
)
async def batch_delete_cycle_logs(
    batch: BatchDeleteRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    results: List[BatchDeleteResultItem] = []

    for date_key in batch.date_keys:
        try:
            from datetime import date as date_type
            log_date = date_type.fromisoformat(date_key)
            doc_id = CycleService._log_doc_id(user_id, log_date)
            CycleService.delete_log(user_id, doc_id)
            results.append(BatchDeleteResultItem(
                date_key=date_key,
                status="ok",
            ))
        except Exception as e:
            results.append(BatchDeleteResultItem(
                date_key=date_key,
                status="error",
                error=str(e),
            ))

    return {"results": results}

@router.post(
    "/log",
    response_model=CycleLogResponse,
    summary="Log a cycle entry",
    description=(
        "Creates or updates a cycle log entry for the specified start "
        "date. Partial payloads (e.g. only `flow_intensity` from a "
        "quick-log tile) are merged without overwriting previously saved "
        "fields for that day.\n\n"
        "A field sent as `null` is **removed** from the stored log; a "
        "field left out of the body is left alone. The two are different "
        "requests — omitting `mood` keeps yesterday's answer, sending "
        "`\"mood\": null` takes it back — which is what lets a user undo "
        "something she logged by mistake. `\"symptoms\": []` clears the "
        "list."
    ),
)
async def log_cycle(
    log: CycleLog,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    fields = _submitted_fields(log, skip=("start_date",))
    log_id = CycleService.upsert_log(user_id, log.start_date, fields)
    return {
        "message": f"Cycle logged for user {user_id}",
        "id": log_id,
        "data": log,
    }

MAX_HISTORY_PAGE = 100

DEFAULT_HISTORY_PAGE = 20

@router.get(
    "/{user_id}/history",
    response_model=CycleHistoryResponse,
    summary="Get cycle history",
    description=(
        "Returns a page of the user's cycle log entries, ordered by date "
        "descending.\n\n"
        "`limit` and `offset` page through the history; `start_date` and "
        "`end_date` (both inclusive, `YYYY-MM-DD`) restrict it to a window, "
        "so a client can ask for a specific month rather than only for the "
        "most recent N entries.\n\n"
        "The `page` object reports where this page sits and whether another "
        "one exists. `hasMore` comes from fetching one extra document, not "
        "from a count query, so paging costs no additional round trip.\n\n"
        "Calling with no query parameters returns the most recent entries, "
        "newest first, exactly as before."
    ),
)
async def get_cycle_history(
    user_id: str,
    limit: int = Query(
        DEFAULT_HISTORY_PAGE,
        ge=1,
        le=MAX_HISTORY_PAGE,
        description="How many entries to return (1-100).",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="How many entries to skip, for paging.",
    ),
    start_date: Optional[date] = Query(
        None,
        description="Only return entries on or after this date (inclusive).",
    ),
    end_date: Optional[date] = Query(
        None,
        description="Only return entries on or before this date (inclusive).",
    ),
    current_user: dict = Depends(get_current_user)
):
    if user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user's data"
        )

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must not be after end_date",
        )

    entries, has_more, total_count = CycleService.get_logs_page(
        user_id,
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "message": f"History for user {user_id}",
        "entries": entries,
        "page": {
            "limit": limit,
            "offset": offset,
            "count": len(entries),
            "total_count": total_count,
            "hasMore": has_more,
            "nextOffset": offset + len(entries) if has_more else None,
        },
    }

@router.get(
    "/predictions",
    response_model=PredictionResponse,
    summary="Predict the next period, fertile window and current phase",
    description=(
        "Returns the authenticated user's predicted next period date with an "
        "explicit earliest/latest range and a confidence tier, her current "
        "cycle day and phase, an estimated ovulation date and fertile window, "
        "and the next few predicted period start dates.\n\n"
        "The cycle-length estimate is an exponentially weighted mean of "
        "recent cycles with outlier rejection, falling back to the length "
        "declared during onboarding and then to a population default; the "
        "`cycleLength.source` field says which was used.\n\n"
        "`daysUntilNextPeriod` goes negative when a period is late — it is "
        "deliberately not clamped at zero. Ovulation and the fertile window "
        "are statistical estimates from logged dates and are not "
        "contraceptive guidance."
    ),
)
async def get_cycle_predictions(
    horizon: int = Query(
        DEFAULT_FORECAST_HORIZON,
        ge=1,
        le=12,
        description="How many future period start dates to project.",
    ),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    logs = CycleService.get_logs_for_user(user_id, limit=12)
    profile = UserService.get_user_by_id(user_id) or {}

    return predict(logs, profile=profile, horizon=horizon).to_dict()

@router.put(
    "/{log_id}",
    response_model=CycleLogUpdateResponse,
    summary="Update a cycle log",
    description=(
        "Updates one or more fields of an existing cycle log entry. Only "
        "the fields included in the request body are modified; all other "
        "existing fields are preserved.\n\n"
        "A field included as `null` is removed from the stored log. "
        "`{\"notes\": null}` is a valid update rather than a `400`."
    ),
)
async def update_cycle_log(
    log_id: str,
    log_update: CycleLogUpdate,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    fields = _submitted_fields(log_update)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update"
        )

    if fields.get("end_date") is not None:
        existing = CycleService.get_log(user_id, log_id)
        stored_start = _as_date(existing.get("start_date"))
        try:
            validate_end_date(stored_start, fields["end_date"])
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

    CycleService.update_log(user_id, log_id, fields)
    return {
        "message": f"Cycle log {log_id} updated",
        "id": log_id,
        "updated_fields": fields
    }

@router.delete(
    "/{log_id}",
    response_model=CycleLogDeleteResponse,
    summary="Delete a cycle log",
    description="Permanently removes a cycle log entry identified by its ID.",
)
async def delete_cycle_log(
    log_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    CycleService.delete_log(user_id, log_id)
    return {
        "message": f"Cycle log {log_id} deleted",
        "id": log_id
    }
