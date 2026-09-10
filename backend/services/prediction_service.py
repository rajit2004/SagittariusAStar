
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

from services.scoring_service import DEFAULT_CYCLE_LENGTH, as_date

MIN_PLAUSIBLE_CYCLE_DAYS = 15
MAX_PLAUSIBLE_CYCLE_DAYS = 60

RECENCY_DECAY = 0.75

OUTLIER_MAD_THRESHOLD = 3.0

MAD_TO_SIGMA = 1.4826

MIN_CYCLES_FOR_OUTLIER_REJECTION = 4

DEFAULT_LUTEAL_DAYS = 14
MIN_LUTEAL_DAYS = 10

SHORT_CYCLE_LUTEAL_THRESHOLD = 25

FERTILE_DAYS_BEFORE_OVULATION = 5
FERTILE_DAYS_AFTER_OVULATION = 1

HIGH_CONFIDENCE_MIN_CYCLES = 5
HIGH_CONFIDENCE_MAX_SPREAD = 3.0
MEDIUM_CONFIDENCE_MIN_CYCLES = 3
MEDIUM_CONFIDENCE_MAX_SPREAD = 7.0

MIN_RANGE_HALF_WIDTH_DAYS = 2
MAX_RANGE_HALF_WIDTH_DAYS = 14

DEFAULT_PERIOD_DAYS = 5

DEFAULT_FORECAST_HORIZON = 3

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

SOURCE_HISTORY = "logged_history"
SOURCE_PROFILE = "declared_cycle_length"
SOURCE_DEFAULT = "population_default"

PHASE_PERIOD = "period"
PHASE_FOLLICULAR = "follicular"
PHASE_OVULATION = "ovulation"
PHASE_LUTEAL = "luteal"

PHASE_LATE = "late"
PHASE_UNKNOWN = "unknown"

DISCLAIMER = (
    "Predictions are estimates based on the dates you have logged. They are "
    "not a medical or contraceptive tool."
)

@dataclass(frozen=True)
class CycleLengthEstimate:

    days: int
    source: str
    confidence: str

    sample_size: int

    spread_days: float

    excluded: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "days": self.days,
            "source": self.source,
            "confidence": self.confidence,
            "sampleSize": self.sample_size,
            "spreadDays": round(self.spread_days, 1),
            "excludedCycleLengths": self.excluded,
        }

@dataclass(frozen=True)
class Prediction:

    cycle_length: CycleLengthEstimate
    last_period_start: Optional[date]
    current_cycle_day: Optional[int]
    phase: str
    next_period_date: Optional[date]

    days_until_next_period: Optional[int]
    is_overdue: bool
    days_overdue: int
    predicted_earliest: Optional[date]
    predicted_latest: Optional[date]
    ovulation_date: Optional[date]
    fertile_window_start: Optional[date]
    fertile_window_end: Optional[date]
    upcoming_periods: List[date]
    today: date

    def to_dict(self) -> Dict[str, Any]:
        def iso(value: Optional[date]) -> Optional[str]:
            return value.isoformat() if value else None

        return {
            "today": self.today.isoformat(),
            "cycleLength": self.cycle_length.to_dict(),
            "lastPeriodStart": iso(self.last_period_start),
            "currentCycleDay": self.current_cycle_day,
            "phase": self.phase,
            "nextPeriodDate": iso(self.next_period_date),
            "daysUntilNextPeriod": self.days_until_next_period,
            "isOverdue": self.is_overdue,
            "daysOverdue": self.days_overdue,
            "predictedRange": {
                "earliest": iso(self.predicted_earliest),
                "latest": iso(self.predicted_latest),
            },
            "ovulation": {
                "date": iso(self.ovulation_date),
                "isEstimate": True,
            },
            "fertileWindow": {
                "start": iso(self.fertile_window_start),
                "end": iso(self.fertile_window_end),
                "isEstimate": True,
                "notForContraception": True,
            },
            "upcomingPeriods": [d.isoformat() for d in self.upcoming_periods],
            "confidence": self.cycle_length.confidence,
            "disclaimer": DISCLAIMER,
        }

def observed_gaps(logs: Sequence[Dict[str, Any]]) -> List[int]:
    starts = sorted(
        {d for d in (as_date(log.get("start_date")) for log in logs or []) if d},
        reverse=True,
    )
    return [(newer - older).days for newer, older in zip(starts, starts[1:])]

def reject_outliers(gaps: Sequence[int]) -> tuple[List[int], List[int]]:
    plausible = [
        gap for gap in gaps if MIN_PLAUSIBLE_CYCLE_DAYS <= gap <= MAX_PLAUSIBLE_CYCLE_DAYS
    ]
    implausible = [gap for gap in gaps if gap not in plausible]

    if len(plausible) < MIN_CYCLES_FOR_OUTLIER_REJECTION:

        return plausible, implausible

    median = statistics.median(plausible)
    deviations = [abs(gap - median) for gap in plausible]
    mad = statistics.median(deviations)

    if mad == 0:

        kept = [gap for gap in plausible if abs(gap - median) <= MIN_RANGE_HALF_WIDTH_DAYS]
        rejected = [gap for gap in plausible if gap not in kept]
        return kept, implausible + rejected

    limit = OUTLIER_MAD_THRESHOLD * mad * MAD_TO_SIGMA
    kept = [gap for gap in plausible if abs(gap - median) <= limit]
    rejected = [gap for gap in plausible if abs(gap - median) > limit]
    return kept, implausible + rejected

def weighted_mean(values: Sequence[float], decay: float = RECENCY_DECAY) -> float:
    if not values:
        raise ValueError("weighted_mean requires at least one value")
    weights = [decay**index for index in range(len(values))]
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)

def spread_of(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    median = statistics.median(values)
    mad = statistics.median([abs(value - median) for value in values])
    quarter_range = (max(values) - min(values)) / 4

    if mad == 0:

        return (max(values) - min(values)) / 2

    return max(mad * MAD_TO_SIGMA, quarter_range)

def _confidence_for(sample_size: int, spread: float) -> str:
    if sample_size >= HIGH_CONFIDENCE_MIN_CYCLES and spread <= HIGH_CONFIDENCE_MAX_SPREAD:
        return CONFIDENCE_HIGH
    if (
        sample_size >= MEDIUM_CONFIDENCE_MIN_CYCLES
        and spread <= MEDIUM_CONFIDENCE_MAX_SPREAD
    ):
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW

def estimate_cycle_length(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
) -> CycleLengthEstimate:
    profile = profile or {}
    gaps = observed_gaps(logs)
    kept, rejected = reject_outliers(gaps)

    if kept:
        spread = spread_of(kept)
        return CycleLengthEstimate(
            days=max(
                MIN_PLAUSIBLE_CYCLE_DAYS,
                min(MAX_PLAUSIBLE_CYCLE_DAYS, round(weighted_mean(kept))),
            ),
            source=SOURCE_HISTORY,
            confidence=_confidence_for(len(kept), spread),
            sample_size=len(kept),
            spread_days=spread,
            excluded=sorted(rejected),
        )

    declared = profile.get("cycle_length")
    if (
        isinstance(declared, (int, float))
        and MIN_PLAUSIBLE_CYCLE_DAYS <= declared <= MAX_PLAUSIBLE_CYCLE_DAYS
    ):
        return CycleLengthEstimate(
            days=int(declared),
            source=SOURCE_PROFILE,

            confidence=CONFIDENCE_LOW,
            sample_size=0,
            spread_days=0.0,
            excluded=sorted(rejected),
        )

    return CycleLengthEstimate(
        days=DEFAULT_CYCLE_LENGTH,
        source=SOURCE_DEFAULT,
        confidence=CONFIDENCE_LOW,
        sample_size=0,
        spread_days=0.0,
        excluded=sorted(rejected),
    )

def luteal_length_for(cycle_length: int) -> int:
    if cycle_length >= SHORT_CYCLE_LUTEAL_THRESHOLD:
        return DEFAULT_LUTEAL_DAYS
    return max(MIN_LUTEAL_DAYS, cycle_length - 11)

def range_half_width(estimate: CycleLengthEstimate) -> int:
    derived = round(estimate.spread_days) if estimate.spread_days else 0
    if estimate.source != SOURCE_HISTORY:

        derived = max(derived, 4)
    return max(MIN_RANGE_HALF_WIDTH_DAYS, min(MAX_RANGE_HALF_WIDTH_DAYS, derived))

def phase_for(
    cycle_day: Optional[int],
    cycle_length: int,
    period_days: int,
    ovulation_day: int,
) -> str:
    if cycle_day is None or cycle_day < 1:
        return PHASE_UNKNOWN
    if cycle_day <= period_days:
        return PHASE_PERIOD
    if cycle_day < ovulation_day - 1:
        return PHASE_FOLLICULAR
    if cycle_day <= ovulation_day + 1:
        return PHASE_OVULATION
    if cycle_day <= cycle_length:
        return PHASE_LUTEAL
    return PHASE_LATE

def _period_days_from(
    logs: Sequence[Dict[str, Any]], profile: Dict[str, Any]
) -> int:
    durations = []
    for log in logs or []:
        start = as_date(log.get("start_date"))
        end = as_date(log.get("end_date"))
        if start and end:
            span = (end - start).days + 1
            if 1 <= span <= 15:
                durations.append(span)

    if durations:
        return round(statistics.median(durations))

    declared = profile.get("period_duration")
    if isinstance(declared, (int, float)) and 1 <= declared <= 15:
        return int(declared)

    return DEFAULT_PERIOD_DAYS

def _last_period_start(
    logs: Sequence[Dict[str, Any]], profile: Dict[str, Any]
) -> Optional[date]:
    starts = [as_date(log.get("start_date")) for log in logs or []]
    starts = [start for start in starts if start]
    if starts:
        return max(starts)

    declared = profile.get("last_period")
    if isinstance(declared, str):
        try:
            return date.fromisoformat(declared[:10])
        except ValueError:
            return None
    return as_date(declared)

def predict(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
    horizon: int = DEFAULT_FORECAST_HORIZON,
) -> Prediction:
    profile = dict(profile or {})
    today = today or date.today()

    estimate = estimate_cycle_length(logs, profile)
    last_start = _last_period_start(logs, profile)
    period_days = _period_days_from(logs, profile)

    if last_start is None:

        return Prediction(
            cycle_length=estimate,
            last_period_start=None,
            current_cycle_day=None,
            phase=PHASE_UNKNOWN,
            next_period_date=None,
            days_until_next_period=None,
            is_overdue=False,
            days_overdue=0,
            predicted_earliest=None,
            predicted_latest=None,
            ovulation_date=None,
            fertile_window_start=None,
            fertile_window_end=None,
            upcoming_periods=[],
            today=today,
        )

    cycle_day = (today - last_start).days + 1
    next_period = last_start + timedelta(days=estimate.days)
    days_until = (next_period - today).days

    is_overdue = days_until < 0
    days_overdue = -days_until if is_overdue else 0

    half_width = range_half_width(estimate)
    luteal = luteal_length_for(estimate.days)
    ovulation = next_period - timedelta(days=luteal)

    upcoming: List[date] = []
    cursor = next_period
    for _ in range(max(0, horizon)):
        upcoming.append(cursor)
        cursor = cursor + timedelta(days=estimate.days)

    return Prediction(
        cycle_length=estimate,
        last_period_start=last_start,
        current_cycle_day=cycle_day if cycle_day >= 1 else None,
        phase=phase_for(
            cycle_day,
            estimate.days,
            period_days,
            ovulation_day=(ovulation - last_start).days + 1,
        ),
        next_period_date=next_period,
        days_until_next_period=days_until,
        is_overdue=is_overdue,
        days_overdue=days_overdue,
        predicted_earliest=next_period - timedelta(days=half_width),
        predicted_latest=next_period + timedelta(days=half_width),
        ovulation_date=ovulation,
        fertile_window_start=ovulation - timedelta(days=FERTILE_DAYS_BEFORE_OVULATION),
        fertile_window_end=ovulation + timedelta(days=FERTILE_DAYS_AFTER_OVULATION),
        upcoming_periods=upcoming,
        today=today,
    )

def dashboard_summary(prediction: Prediction) -> Dict[str, Any]:
    def iso(value: Optional[date]) -> Optional[str]:
        return value.isoformat() if value else None

    return {
        "nextPeriodDate": iso(prediction.next_period_date),
        "daysUntilNextPeriod": prediction.days_until_next_period,
        "isOverdue": prediction.is_overdue,
        "daysOverdue": prediction.days_overdue,
        "phase": prediction.phase,
        "confidence": prediction.cycle_length.confidence,
        "estimateSource": prediction.cycle_length.source,
        "predictedRange": {
            "earliest": iso(prediction.predicted_earliest),
            "latest": iso(prediction.predicted_latest),
        },
        "fertileWindow": {
            "start": iso(prediction.fertile_window_start),
            "end": iso(prediction.fertile_window_end),
            "isEstimate": True,
            "notForContraception": True,
        },
    }

__all__ = [
    "CONFIDENCE_HIGH",
    "CONFIDENCE_LOW",
    "CONFIDENCE_MEDIUM",
    "DISCLAIMER",
    "PHASE_FOLLICULAR",
    "PHASE_LATE",
    "PHASE_LUTEAL",
    "PHASE_OVULATION",
    "PHASE_PERIOD",
    "PHASE_UNKNOWN",
    "SOURCE_DEFAULT",
    "SOURCE_HISTORY",
    "SOURCE_PROFILE",
    "CycleLengthEstimate",
    "Prediction",
    "dashboard_summary",
    "estimate_cycle_length",
    "luteal_length_for",
    "observed_gaps",
    "phase_for",
    "predict",
    "range_half_width",
    "reject_outliers",
    "spread_of",
    "weighted_mean",
]
