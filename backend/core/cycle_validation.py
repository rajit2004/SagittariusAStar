
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, List, Optional, Sequence

FLOW_INTENSITIES: Sequence[str] = ("none", "spotting", "light", "medium", "heavy", "very_heavy")

MOODS: Sequence[str] = ("happy", "neutral", "sad", "frustrated", "loved")

KNOWN_SYMPTOMS: Sequence[str] = (
    "cramps",
    "headache",
    "bloating",
    "fatigue",
    "nausea",
    "acne",
    "back pain",
    "severe pain",
    "fainting",
)

_SYMPTOM_ALIASES = {
    "backpain": "back pain",
    "back_pain": "back pain",
    "lower back pain": "back pain",
    "cramp": "cramps",
    "period cramps": "cramps",
    "head ache": "headache",
    "tiredness": "fatigue",
    "tired": "fatigue",
    "nauseous": "nausea",
    "faint": "fainting",
    "passed out": "fainting",
    "severe cramps": "severe pain",
    "bad pain": "severe pain",
}

MIN_SLEEP_HOURS = 0.0
MAX_SLEEP_HOURS = 24.0

MIN_STRESS_LEVEL = 1
MAX_STRESS_LEVEL = 5

MAX_NOTES_CHARS = 2000

MAX_SYMPTOMS = 25
MAX_SYMPTOM_CHARS = 40

MAX_LOG_AGE_DAYS = 3653

MAX_PERIOD_DURATION_DAYS = 90

def _describe(allowed: Iterable[str]) -> str:
    return ", ".join(allowed)

def normalize_choice(
    value: Optional[str], allowed: Sequence[str], field: str
) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")

    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned not in allowed:
        raise ValueError(
            f"{field} must be one of: {_describe(allowed)} (got {value!r})"
        )
    return cleaned

def normalize_symptoms(value: Optional[Any]) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):

        raise ValueError("symptoms must be a list, not a single string")
    if not isinstance(value, (list, tuple)):
        raise ValueError("symptoms must be a list")

    cleaned: List[str] = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError("every symptom must be text")

        normalized = " ".join(item.split()).lower()
        if not normalized:
            continue
        normalized = _SYMPTOM_ALIASES.get(normalized, normalized)
        if len(normalized) > MAX_SYMPTOM_CHARS:
            raise ValueError(
                f"each symptom must be at most {MAX_SYMPTOM_CHARS} characters "
                f"(got {len(normalized)})"
            )
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)

    if len(cleaned) > MAX_SYMPTOMS:
        raise ValueError(
            f"at most {MAX_SYMPTOMS} symptoms can be logged for one day "
            f"(got {len(cleaned)})"
        )
    return cleaned

def normalize_notes(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("notes must be text")

    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > MAX_NOTES_CHARS:
        raise ValueError(
            f"notes must be at most {MAX_NOTES_CHARS} characters "
            f"(got {len(trimmed)})"
        )
    return trimmed

def validate_sleep_hours(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError("sleep_hours must be a number")
    numeric = float(value)
    if numeric != numeric or numeric in (float("inf"), float("-inf")):
        raise ValueError("sleep_hours must be a real number")
    if not MIN_SLEEP_HOURS <= numeric <= MAX_SLEEP_HOURS:
        raise ValueError(
            f"sleep_hours must be between {MIN_SLEEP_HOURS} and "
            f"{MAX_SLEEP_HOURS} (got {value})"
        )
    return numeric

def validate_stress_level(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("stress_level must be a number")
    if not MIN_STRESS_LEVEL <= value <= MAX_STRESS_LEVEL:
        raise ValueError(
            f"stress_level must be between {MIN_STRESS_LEVEL} and "
            f"{MAX_STRESS_LEVEL} (got {value})"
        )
    return value

def earliest_loggable_date(today: Optional[date] = None) -> date:
    return (today or date.today()) - timedelta(days=MAX_LOG_AGE_DAYS)

def validate_start_date(value: date, *, today: Optional[date] = None) -> date:
    reference = today or date.today()
    if value > reference:
        raise ValueError(
            f"start_date cannot be in the future (got {value.isoformat()}, "
            f"today is {reference.isoformat()})"
        )
    floor = earliest_loggable_date(reference)
    if value < floor:
        raise ValueError(
            f"start_date cannot be before {floor.isoformat()} "
            f"(got {value.isoformat()})"
        )
    return value

def validate_end_date(
    start: Optional[date], end: Optional[date], *, today: Optional[date] = None
) -> Optional[date]:
    if end is None:
        return None
    reference = today or date.today()
    if end > reference:
        raise ValueError(
            f"end_date cannot be in the future (got {end.isoformat()})"
        )
    if start is not None:
        if end < start:
            raise ValueError(
                f"end_date ({end.isoformat()}) cannot be before start_date "
                f"({start.isoformat()})"
            )
        span = (end - start).days + 1
        if span > MAX_PERIOD_DURATION_DAYS:
            raise ValueError(
                f"a single period cannot span more than "
                f"{MAX_PERIOD_DURATION_DAYS} days (got {span})"
            )
    return end

def loggable_values() -> dict:
    return {
        "flowIntensities": list(FLOW_INTENSITIES),
        "moods": list(MOODS),
        "knownSymptoms": list(KNOWN_SYMPTOMS),
        "symptomsAreOpenEnded": True,
        "limits": {
            "sleepHours": {"min": MIN_SLEEP_HOURS, "max": MAX_SLEEP_HOURS},
            "stressLevel": {"min": MIN_STRESS_LEVEL, "max": MAX_STRESS_LEVEL},
            "notesMaxChars": MAX_NOTES_CHARS,
            "maxSymptoms": MAX_SYMPTOMS,
            "symptomMaxChars": MAX_SYMPTOM_CHARS,
            "maxPeriodDurationDays": MAX_PERIOD_DURATION_DAYS,
            "earliestLoggableDate": earliest_loggable_date().isoformat(),
        },
    }
