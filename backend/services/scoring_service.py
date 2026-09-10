
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from services.firestore_service import CycleService, UserService
from models.cvi_model import predict_cvi, risk_level
from models.mhs_model import predict_mhs

DEFAULT_CYCLE_LENGTH = 28

_FLOW_INTENSITY_TO_SCORE = {"none": 0, "spotting": 1, "light": 1, "medium": 2, "heavy": 3, "very_heavy": 4}

_FLOW_INTENSITY_WHEN_ABSENT = 2

_LOGS_LIMIT = 10

def as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None

def compute_cycle_stats(logs: List[Dict[str, Any]]) -> Dict[str, Any]:

    cycle_lengths: List[int] = []
    bleeding_days: List[int] = []

    for i in range(len(logs) - 1):
        newer = as_date(logs[i].get("start_date"))
        older = as_date(logs[i + 1].get("start_date"))
        if newer and older and (newer - older).days > 0:
            cycle_lengths.append((newer - older).days)

    for log in logs:
        start = as_date(log.get("start_date"))
        end = as_date(log.get("end_date"))
        if start and end and end >= start:
            bleeding_days.append(max(1, (end - start).days + 1))

    avg_cycle = round(sum(cycle_lengths) / len(cycle_lengths), 1) if cycle_lengths else None
    min_cycle = min(cycle_lengths) if cycle_lengths else None
    max_cycle = max(cycle_lengths) if cycle_lengths else None
    avg_bleed = round(sum(bleeding_days) / len(bleeding_days), 1) if bleeding_days else None

    return {
        "average_cycle_length": avg_cycle,
        "shortest_cycle_length": min_cycle,
        "longest_cycle_length": max_cycle,
        "average_bleeding_duration": avg_bleed,
    }

def build_model_features(logs_newest_first: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    features = []
    for i, log in enumerate(logs_newest_first):
        start = as_date(log.get("start_date"))
        end = as_date(log.get("end_date"))

        cycle_length = None
        if i + 1 < len(logs_newest_first):
            older_start = as_date(logs_newest_first[i + 1].get("start_date"))
            if start and older_start and (start - older_start).days > 0:
                cycle_length = (start - older_start).days

        if start and end and end >= start:
            flow_duration = max(1, (end - start).days + 1)
        else:
            flow_duration = 5
        flow_intensity = _FLOW_INTENSITY_TO_SCORE.get(
            (log.get("flow_intensity") or "").lower(), _FLOW_INTENSITY_WHEN_ABSENT
        )

        stress = log.get("stress_level")
        sleep = log.get("sleep_hours")

        features.append({
            "cycle_length": cycle_length if cycle_length is not None else DEFAULT_CYCLE_LENGTH,
            "flow_duration": flow_duration,
            "flow_intensity": flow_intensity,
            "symptom_count": len(log.get("symptoms") or []),
            "stress_avg": stress if stress is not None else 2.5,
            "sleep_avg": sleep if sleep is not None else 7.0,
        })
    return features

def get_user_scores(user_id: str) -> Dict[str, Any]:
    logs = CycleService.get_logs_for_user(user_id, limit=_LOGS_LIMIT)
    features = build_model_features(logs)
    profile = UserService.get_user_by_id(user_id)

    mhs = predict_mhs(features, profile=profile)
    cvi = predict_cvi(features)
    cvi_risk = risk_level(cvi).capitalize() if cvi is not None else None

    return {
        "logs": logs,
        "profile": profile,
        "mhs": mhs,
        "cvi": cvi,
        "cvi_risk": cvi_risk,
        "has_enough_data_for_insights": len(logs) >= 3,
        "logged_cycle_count": len(logs),
    }
