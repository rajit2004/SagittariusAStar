
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

from services.scoring_service import as_date

BLEEDING_FLOWS = frozenset({"spotting", "light", "medium", "heavy", "very_heavy"})

PERIOD_RUN_GAP_TOLERANCE_DAYS = 1

MIN_DAYS_BETWEEN_PERIOD_STARTS = 15

MIN_SAMPLES_FOR_AVERAGE = 2

SLEEP_MEANINGFUL_DELTA_HOURS = 0.3
STRESS_MEANINGFUL_DELTA = 0.5

SYMPTOM_MEANINGFUL_DELTA = 0.2

CANONICAL_SYMPTOMS = ("cramps", "headache", "bloating", "acne")

MIN_LOGS_FOR_RECENT_SPLIT = 2

DIRECTION_INCREASED = "increased"
DIRECTION_DECREASED = "decreased"
DIRECTION_UNCHANGED = "unchanged"

BASIS_CYCLE = "cycle"

BASIS_RECENT_LOGS = "recent_logs"

DISCLAIMER_KEY = "insights.disclaimer"

DISCLAIMER = (
    "These are descriptions of what you logged, not medical advice."
)

@dataclass(frozen=True)
class DayRecord:

    day: date
    flow_intensity: Optional[str]
    sleep_hours: Optional[float]
    stress_level: Optional[int]
    symptoms: frozenset

    @property
    def is_bleeding(self) -> bool:
        return self.flow_intensity in BLEEDING_FLOWS

@dataclass(frozen=True)
class Window:

    start: date
    end: date
    records: List[DayRecord] = field(default_factory=list)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def values(self, attribute: str) -> List[float]:
        return [
            float(getattr(record, attribute))
            for record in self.records
            if getattr(record, attribute) is not None
        ]

    def mean(self, attribute: str) -> Optional[float]:
        values = self.values(attribute)
        return statistics.fmean(values) if values else None

    def symptom_rate(self, symptom: str) -> Optional[float]:
        logged = [record for record in self.records if record.symptoms is not None]
        if not logged:
            return None
        return sum(1 for record in logged if symptom in record.symptoms) / len(logged)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "days": self.days,
            "loggedDays": len(self.records),
        }

@dataclass(frozen=True)
class TrendStatement:

    metric: str
    direction: str
    key: str
    text: str
    evidence: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "direction": self.direction,
            "key": self.key,
            "text": self.text,
            "evidence": self.evidence,
        }

def _normalize_symptoms(value: Any) -> frozenset:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(
        str(item).strip().lower() for item in value if str(item).strip()
    )

def to_day_records(logs: Sequence[Dict[str, Any]]) -> List[DayRecord]:
    records: List[DayRecord] = []
    for log in logs or []:
        day = as_date(log.get("start_date"))
        if day is None:
            continue

        sleep = log.get("sleep_hours")
        stress = log.get("stress_level")
        records.append(
            DayRecord(
                day=day,
                flow_intensity=(log.get("flow_intensity") or "").strip().lower() or None,
                sleep_hours=float(sleep) if isinstance(sleep, (int, float)) else None,
                stress_level=int(stress) if isinstance(stress, (int, float)) else None,
                symptoms=_normalize_symptoms(log.get("symptoms")),
            )
        )

    by_day: Dict[date, DayRecord] = {record.day: record for record in records}
    return sorted(by_day.values(), key=lambda record: record.day)

def period_starts(records: Sequence[DayRecord]) -> List[date]:
    bleeding = [record.day for record in records if record.is_bleeding]
    if not bleeding:
        return []

    starts = [bleeding[0]]
    for previous, current in zip(bleeding, bleeding[1:]):
        if (current - previous).days > PERIOD_RUN_GAP_TOLERANCE_DAYS + 1:
            starts.append(current)

    merged = [starts[0]]
    for start in starts[1:]:
        if (start - merged[-1]).days >= MIN_DAYS_BETWEEN_PERIOD_STARTS:
            merged.append(start)
    return merged

def cycle_windows(records: Sequence[DayRecord], today: date) -> List[Window]:
    starts = period_starts(records)
    if len(starts) < 2:
        return []

    windows: List[Window] = []
    for start, next_start in zip(starts, starts[1:]):
        end = next_start - timedelta(days=1)
        windows.append(
            Window(
                start=start,
                end=end,
                records=[r for r in records if start <= r.day <= end],
            )
        )
    return windows

def recent_log_windows(records: Sequence[DayRecord]) -> List[Window]:
    if len(records) < MIN_LOGS_FOR_RECENT_SPLIT:
        return []

    midpoint = len(records) // 2
    older, newer = records[:midpoint], records[midpoint:]
    if not older or not newer:
        return []

    return [
        Window(start=older[0].day, end=older[-1].day, records=list(older)),
        Window(start=newer[0].day, end=newer[-1].day, records=list(newer)),
    ]

def _direction(previous: float, current: float, threshold: float) -> str:
    if abs(current - previous) < threshold:
        return DIRECTION_UNCHANGED
    return DIRECTION_INCREASED if current > previous else DIRECTION_DECREASED

def _numeric_statement(
    metric: str,
    previous_window: Window,
    current_window: Window,
    attribute: str,
    threshold: float,
    unit: str,
    noun: str,
) -> Optional[TrendStatement]:
    previous = previous_window.mean(attribute)
    current = current_window.mean(attribute)
    if previous is None or current is None:
        return None

    previous_samples = len(previous_window.values(attribute))
    current_samples = len(current_window.values(attribute))
    direction = _direction(previous, current, threshold)

    previous_display = round(previous, 1)
    current_display = round(current, 1)

    averaged = (
        previous_samples >= MIN_SAMPLES_FOR_AVERAGE
        and current_samples >= MIN_SAMPLES_FOR_AVERAGE
    )
    subject = f"Average {noun}" if averaged else f"Logged {noun}"

    if direction == DIRECTION_UNCHANGED:
        text = f"{subject} is about the same ({current_display}{unit})."
    else:
        text = (
            f"{subject} has {direction} "
            f"({previous_display}{unit} → {current_display}{unit})."
        )

    return TrendStatement(
        metric=metric,
        direction=direction,
        key=f"trends.{metric}.{direction}",
        text=text,
        evidence={
            "previous": previous_display,
            "current": current_display,
            "delta": round(current - previous, 1),
            "unit": unit or None,
            "previousSamples": previous_samples,
            "currentSamples": current_samples,
            "averaged": averaged,
        },
    )

def _symptom_statement(
    symptom: str, previous_window: Window, current_window: Window
) -> Optional[TrendStatement]:
    previous = previous_window.symptom_rate(symptom)
    current = current_window.symptom_rate(symptom)
    if previous is None or current is None:
        return None
    if previous == 0 and current == 0:
        return None

    direction = _direction(previous, current, SYMPTOM_MEANINGFUL_DELTA)
    previous_pct = round(previous * 100)
    current_pct = round(current * 100)

    if direction == DIRECTION_UNCHANGED:
        text = f"Logged on a similar share of days ({current_pct}%)."
    else:
        text = f"Logged on {previous_pct}% of days, now {current_pct}%."

    return TrendStatement(
        metric=symptom,
        direction=direction,
        key=f"trends.symptom.{direction}",
        text=text,
        evidence={
            "symptom": symptom,
            "previousRate": round(previous, 2),
            "currentRate": round(current, 2),
            "previousDays": previous_window.days,
            "currentDays": current_window.days,
        },
    )

def build_trends(
    logs: Sequence[Dict[str, Any]], today: Optional[date] = None
) -> Dict[str, Any]:
    resolved_today = today or date.today()
    records = to_day_records(logs)

    windows = cycle_windows(records, resolved_today)
    basis = BASIS_CYCLE
    if len(windows) < 2:
        windows = recent_log_windows(records)
        basis = BASIS_RECENT_LOGS

    if len(windows) < 2:
        return {
            "sleep": None,
            "stress": None,
            "symptoms": {},
            "notEnoughData": True,
            "basis": None,
            "comparedWindows": None,
            "trends": [],
            "disclaimer": DISCLAIMER,
            "disclaimerKey": DISCLAIMER_KEY,
        }

    previous_window, current_window = windows[-2], windows[-1]

    sleep = _numeric_statement(
        "sleep", previous_window, current_window,
        attribute="sleep_hours",
        threshold=SLEEP_MEANINGFUL_DELTA_HOURS,
        unit="h",
        noun="sleep",
    )
    stress = _numeric_statement(
        "stress", previous_window, current_window,
        attribute="stress_level",
        threshold=STRESS_MEANINGFUL_DELTA,
        unit="",
        noun="stress",
    )

    symptom_statements = [
        statement
        for statement in (
            _symptom_statement(symptom, previous_window, current_window)
            for symptom in CANONICAL_SYMPTOMS
        )
        if statement is not None
    ]

    statements = [s for s in (sleep, stress) if s is not None] + symptom_statements

    if not statements:
        return {
            "sleep": None,
            "stress": None,
            "symptoms": {},
            "notEnoughData": True,
            "basis": basis,
            "comparedWindows": {
                "previous": previous_window.to_dict(),
                "current": current_window.to_dict(),
            },
            "trends": [],
            "disclaimer": DISCLAIMER,
            "disclaimerKey": DISCLAIMER_KEY,
        }

    return {
        "sleep": sleep.text if sleep else None,
        "stress": stress.text if stress else None,
        "symptoms": {s.metric: s.text for s in symptom_statements},
        "notEnoughData": False,
        "basis": basis,
        "comparedWindows": {
            "previous": previous_window.to_dict(),
            "current": current_window.to_dict(),
        },
        "trends": [statement.to_dict() for statement in statements],
        "disclaimer": DISCLAIMER,
        "disclaimerKey": DISCLAIMER_KEY,
    }

__all__ = [
    "BASIS_CYCLE",
    "BASIS_RECENT_LOGS",
    "BLEEDING_FLOWS",
    "CANONICAL_SYMPTOMS",
    "DIRECTION_DECREASED",
    "DIRECTION_INCREASED",
    "DIRECTION_UNCHANGED",
    "DISCLAIMER",
    "DISCLAIMER_KEY",
    "MIN_DAYS_BETWEEN_PERIOD_STARTS",
    "DayRecord",
    "TrendStatement",
    "Window",
    "build_trends",
    "cycle_windows",
    "period_starts",
    "recent_log_windows",
    "to_day_records",
]
