
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from services.scoring_service import DEFAULT_CYCLE_LENGTH, as_date

SHORT_CYCLE_DAYS = 21

LONG_CYCLE_DAYS = 35

MAX_PLAUSIBLE_CYCLE_DAYS = 90
MIN_PLAUSIBLE_CYCLE_DAYS = 15

PROLONGED_BLEEDING_DAYS = 8

NO_RECENT_PERIOD_DAYS = 90

VARIABLE_CYCLE_SWING_DAYS = 9

CONSISTENT_SPREAD_DAYS = 4
SLIGHTLY_VARIABLE_SPREAD_DAYS = 8

HEAVY_FLOW_MIN_OCCURRENCES = 2
HEAVY_FLOW_WINDOW = 3

SYMPTOM_INCREASE_MULTIPLIER = 2.0
SYMPTOM_INCREASE_MIN_COUNT = 3

RECENT_WELLNESS_WINDOW = 3
HIGH_STRESS_MEAN = 4.0
SHORT_SLEEP_MEAN_HOURS = 6.0

PERIOD_LATE_DAYS = 7

MIN_CYCLES_FOR_ANALYSIS = 2

PAIN_SYMPTOMS = frozenset({"cramps", "back pain"})

SEVERE_PAIN_MIN_OCCURRENCES = 3
SEVERE_PAIN_WINDOW = 4

FREQUENT_BLEEDING_MAX_GAP_DAYS = 21
FREQUENT_BLEEDING_MIN_CONSECUTIVE = 2

DISCLAIMER_KEY = "insights.disclaimer"
DISCLAIMER_TEXT = (
    "These insights are based on the information you log and are intended "
    "for personal tracking only. They are not a medical diagnosis and "
    "should not replace advice from a qualified healthcare professional."
)

SEEK_CARE_SUFFIX = (
    "Consider discussing this with a qualified healthcare professional."
)

SEVERITY_INFO = "info"
SEVERITY_ATTENTION = "attention"
SEVERITY_SEEK_CARE = "seek_care"

SEVERITY_ORDER: Dict[str, int] = {
    SEVERITY_INFO: 0,
    SEVERITY_ATTENTION: 1,
    SEVERITY_SEEK_CARE: 2,
}

CONSISTENCY_UNKNOWN = "unknown"
CONSISTENCY_CONSISTENT = "consistent"
CONSISTENCY_SLIGHTLY_VARIABLE = "slightly_variable"
CONSISTENCY_VARIABLE = "variable"

@dataclass(frozen=True)
class Observation:

    code: str
    severity: str
    title: str
    body: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    priority: int = 100
    is_medical_advice: bool = False
    disclaimer_key: str = DISCLAIMER_KEY

    @property
    def title_key(self) -> str:
        return f"observations.{self.code}.title"

    @property
    def body_key(self) -> str:
        return f"observations.{self.code}.body"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "title": self.title,
            "body": self.body,
            "titleKey": self.title_key,
            "bodyKey": self.body_key,
            "evidence": self.evidence,
            "isMedicalAdvice": self.is_medical_advice,
            "disclaimerKey": self.disclaimer_key,
        }

@dataclass(frozen=True)
class CycleObservationInput:

    start_date: date
    end_date: Optional[date]
    bleeding_days: Optional[int]
    flow_intensity: Optional[str]
    symptoms: Sequence[str]
    stress_level: Optional[int]
    sleep_hours: Optional[float]

@dataclass(frozen=True)
class CycleAnalysis:

    cycles: List[CycleObservationInput]

    gaps: List[int]
    today: date
    profile: Dict[str, Any]

    @property
    def has_enough_cycles(self) -> bool:
        return len(self.gaps) >= 1 and len(self.cycles) >= MIN_CYCLES_FOR_ANALYSIS

    @property
    def average_cycle_length(self) -> int:
        if self.gaps:
            return round(sum(self.gaps) / len(self.gaps))
        declared = self.profile.get("cycle_length")
        if isinstance(declared, int) and MIN_PLAUSIBLE_CYCLE_DAYS <= declared <= MAX_PLAUSIBLE_CYCLE_DAYS:
            return declared
        return DEFAULT_CYCLE_LENGTH

    @property
    def days_since_last_start(self) -> Optional[int]:
        if not self.cycles:
            return None
        return (self.today - self.cycles[0].start_date).days

def _normalize_symptoms(raw: Any) -> Sequence[str]:
    if not raw:
        return ()
    if isinstance(raw, str):
        return (raw,)
    try:
        return tuple(str(item) for item in raw)
    except TypeError:
        return ()

def _bleeding_days(start: Optional[date], end: Optional[date]) -> Optional[int]:
    if start is None or end is None:
        return None
    span = (end - start).days + 1
    return span if span > 0 else None

def build_analysis(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
) -> CycleAnalysis:
    resolved_today = today or date.today()
    resolved_profile = dict(profile or {})

    normalized: List[CycleObservationInput] = []
    for log in logs or []:
        start = as_date(log.get("start_date"))
        if start is None:

            continue
        end = as_date(log.get("end_date"))
        stress = log.get("stress_level")
        sleep = log.get("sleep_hours")
        normalized.append(
            CycleObservationInput(
                start_date=start,
                end_date=end,
                bleeding_days=_bleeding_days(start, end),
                flow_intensity=(log.get("flow_intensity") or "").lower() or None,
                symptoms=_normalize_symptoms(log.get("symptoms")),
                stress_level=int(stress) if isinstance(stress, (int, float)) else None,
                sleep_hours=float(sleep) if isinstance(sleep, (int, float)) else None,
            )
        )

    normalized.sort(key=lambda c: c.start_date, reverse=True)

    gaps: List[int] = []
    for newer, older in zip(normalized, normalized[1:]):
        delta = (newer.start_date - older.start_date).days
        if MIN_PLAUSIBLE_CYCLE_DAYS <= delta <= MAX_PLAUSIBLE_CYCLE_DAYS:
            gaps.append(delta)

    return CycleAnalysis(
        cycles=normalized,
        gaps=gaps,
        today=resolved_today,
        profile=resolved_profile,
    )

def rule_insufficient_data(analysis: CycleAnalysis) -> Optional[Observation]:
    if analysis.has_enough_cycles:
        return None
    logged = len(analysis.cycles)
    return Observation(
        code="insufficient_data",
        severity=SEVERITY_INFO,
        title="Keep logging to see your patterns",
        body=(
            f"You've logged {logged} "
            f"{'cycle' if logged == 1 else 'cycles'} so far. "
            "Once there are a couple of cycles to compare, this page can "
            "describe your own patterns."
        ),
        evidence={"logged_cycles": logged, "needed": MIN_CYCLES_FOR_ANALYSIS},
        priority=10,
    )

def rule_no_recent_period_logged(analysis: CycleAnalysis) -> Optional[Observation]:
    days = analysis.days_since_last_start
    if days is None or days <= NO_RECENT_PERIOD_DAYS:
        return None
    return Observation(
        code="no_recent_period_logged",
        severity=SEVERITY_SEEK_CARE,
        title="No period logged recently",
        body=(
            f"Your last logged period started {days} days ago. If a period "
            "has happened since then, it may simply need logging. "
            f"If not, {SEEK_CARE_SUFFIX[0].lower()}{SEEK_CARE_SUFFIX[1:]}"
        ),
        evidence={
            "days_since_last_start": days,
            "threshold_days": NO_RECENT_PERIOD_DAYS,
            "last_start_date": analysis.cycles[0].start_date.isoformat(),
        },
        priority=10,
    )

def rule_prolonged_bleeding(analysis: CycleAnalysis) -> Optional[Observation]:
    for cycle in analysis.cycles:
        if cycle.bleeding_days is not None and cycle.bleeding_days >= PROLONGED_BLEEDING_DAYS:
            return Observation(
                code="prolonged_bleeding",
                severity=SEVERITY_SEEK_CARE,
                title="A longer period than usual",
                body=(
                    f"You logged {cycle.bleeding_days} days of bleeding "
                    f"starting {cycle.start_date.isoformat()}. "
                    f"{SEEK_CARE_SUFFIX}"
                ),
                evidence={
                    "bleeding_days": cycle.bleeding_days,
                    "threshold_days": PROLONGED_BLEEDING_DAYS,
                    "start_date": cycle.start_date.isoformat(),
                },
                priority=20,
            )
    return None

def rule_repeated_heavy_flow(analysis: CycleAnalysis) -> Optional[Observation]:
    window = analysis.cycles[:HEAVY_FLOW_WINDOW]
    heavy = [c for c in window if c.flow_intensity == "heavy"]
    if len(heavy) < HEAVY_FLOW_MIN_OCCURRENCES:
        return None
    return Observation(
        code="repeated_heavy_flow",
        severity=SEVERITY_ATTENTION,
        title="Heavy flow logged more than once recently",
        body=(
            f"You described your flow as heavy in {len(heavy)} of your last "
            f"{len(window)} logged cycles. If this feels different from "
            "what's normal for you, it's worth mentioning to a healthcare "
            "professional."
        ),
        evidence={
            "heavy_cycles": len(heavy),
            "window": len(window),
            "start_dates": [c.start_date.isoformat() for c in heavy],
        },
        priority=30,
    )

def rule_short_cycle_observed(analysis: CycleAnalysis) -> Optional[Observation]:
    if not analysis.has_enough_cycles:
        return None
    short = [gap for gap in analysis.gaps if gap < SHORT_CYCLE_DAYS]
    if not short:
        return None
    return Observation(
        code="short_cycle_observed",
        severity=SEVERITY_ATTENTION,
        title="A shorter cycle than most",
        body=(
            f"One of your recent cycles was {min(short)} days, shorter than "
            f"the {SHORT_CYCLE_DAYS}-{LONG_CYCLE_DAYS} day range most cycles "
            "fall into. If this is new for you, consider mentioning it at "
            "your next check-up."
        ),
        evidence={
            "shortest_cycle_days": min(short),
            "threshold_days": SHORT_CYCLE_DAYS,
            "occurrences": len(short),
        },
        priority=40,
    )

def rule_long_cycle_observed(analysis: CycleAnalysis) -> Optional[Observation]:
    if not analysis.has_enough_cycles:
        return None
    long_cycles = [gap for gap in analysis.gaps if gap > LONG_CYCLE_DAYS]
    if not long_cycles:
        return None
    return Observation(
        code="long_cycle_observed",
        severity=SEVERITY_ATTENTION,
        title="A longer cycle than most",
        body=(
            f"One of your recent cycles was {max(long_cycles)} days, longer "
            f"than the {SHORT_CYCLE_DAYS}-{LONG_CYCLE_DAYS} day range most "
            "cycles fall into. If this is new for you, consider mentioning "
            "it at your next check-up."
        ),
        evidence={
            "longest_cycle_days": max(long_cycles),
            "threshold_days": LONG_CYCLE_DAYS,
            "occurrences": len(long_cycles),
        },
        priority=40,
    )

def rule_variable_cycle_lengths(analysis: CycleAnalysis) -> Optional[Observation]:
    if len(analysis.gaps) < 2:
        return None
    swings = [abs(a - b) for a, b in zip(analysis.gaps, analysis.gaps[1:])]
    largest = max(swings)
    if largest < VARIABLE_CYCLE_SWING_DAYS:
        return None
    return Observation(
        code="variable_cycle_lengths",
        severity=SEVERITY_ATTENTION,
        title="Your cycle lengths have varied",
        body=(
            f"Your cycle length has ranged from {min(analysis.gaps)} to "
            f"{max(analysis.gaps)} days across your last "
            f"{len(analysis.gaps)} cycles. If this feels different from "
            "what is normal for you, or you have concerns, consider "
            "discussing it with a healthcare professional."
        ),
        evidence={
            "shortest_cycle_days": min(analysis.gaps),
            "longest_cycle_days": max(analysis.gaps),
            "largest_swing_days": largest,
            "cycles_compared": len(analysis.gaps),
        },
        priority=50,
    )

def rule_period_later_than_usual(analysis: CycleAnalysis) -> Optional[Observation]:
    days = analysis.days_since_last_start
    if days is None or not analysis.gaps:
        return None
    average = analysis.average_cycle_length
    overdue = days - average
    if overdue < PERIOD_LATE_DAYS:
        return None

    if days > NO_RECENT_PERIOD_DAYS:
        return None
    return Observation(
        code="period_later_than_usual",
        severity=SEVERITY_ATTENTION,
        title="Running later than your usual cycle",
        body=(
            f"It's day {days} of your current cycle, and your recent average "
            f"is {average} days. Cycles vary for lots of everyday reasons."
        ),
        evidence={
            "current_cycle_day": days,
            "average_cycle_days": average,
            "days_past_average": overdue,
        },
        priority=60,
    )

def rule_symptom_increase(analysis: CycleAnalysis) -> Optional[Observation]:
    if len(analysis.cycles) < MIN_CYCLES_FOR_ANALYSIS:
        return None
    latest = len(analysis.cycles[0].symptoms)
    previous = analysis.cycles[1:]
    if not previous:
        return None
    prior_average = sum(len(c.symptoms) for c in previous) / len(previous)
    if latest < SYMPTOM_INCREASE_MIN_COUNT:
        return None
    if prior_average <= 0 or latest < prior_average * SYMPTOM_INCREASE_MULTIPLIER:
        return None
    return Observation(
        code="symptom_increase",
        severity=SEVERITY_INFO,
        title="More symptoms logged this cycle",
        body=(
            f"You logged {latest} symptoms this cycle, compared with an "
            f"average of {prior_average:.1f} in your previous "
            f"{len(previous)} cycles."
        ),
        evidence={
            "latest_symptom_count": latest,
            "previous_average": round(prior_average, 1),
            "cycles_compared": len(previous),
            "symptoms": list(analysis.cycles[0].symptoms),
        },
        priority=70,
    )

def rule_sustained_high_stress(analysis: CycleAnalysis) -> Optional[Observation]:
    values = [
        c.stress_level
        for c in analysis.cycles[:RECENT_WELLNESS_WINDOW]
        if c.stress_level is not None
    ]
    if len(values) < RECENT_WELLNESS_WINDOW:
        return None
    mean = sum(values) / len(values)
    if mean < HIGH_STRESS_MEAN:
        return None
    return Observation(
        code="sustained_high_stress",
        severity=SEVERITY_INFO,
        title="Stress has been high lately",
        body=(
            f"Your logged stress has averaged {mean:.1f} out of 5 across "
            f"your last {len(values)} entries."
        ),
        evidence={
            "average_stress": round(mean, 1),
            "entries": len(values),
            "scale_max": 5,
        },
        priority=80,
    )

def rule_short_sleep_trend(analysis: CycleAnalysis) -> Optional[Observation]:
    values = [
        c.sleep_hours
        for c in analysis.cycles[:RECENT_WELLNESS_WINDOW]
        if c.sleep_hours is not None
    ]
    if len(values) < RECENT_WELLNESS_WINDOW:
        return None
    mean = sum(values) / len(values)
    if mean >= SHORT_SLEEP_MEAN_HOURS:
        return None
    return Observation(
        code="short_sleep_trend",
        severity=SEVERITY_INFO,
        title="Sleep has been on the shorter side",
        body=(
            f"You've logged an average of {mean:.1f} hours of sleep across "
            f"your last {len(values)} entries."
        ),
        evidence={"average_sleep_hours": round(mean, 1), "entries": len(values)},
        priority=90,
    )

def rule_severe_pain_pattern(analysis: CycleAnalysis) -> Optional[Observation]:
    window = analysis.cycles[:SEVERE_PAIN_WINDOW]
    if len(window) < SEVERE_PAIN_WINDOW:
        return None
    pain_cycles = [
        c for c in window
        if any(s in PAIN_SYMPTOMS for s in c.symptoms)
    ]
    if len(pain_cycles) < SEVERE_PAIN_MIN_OCCURRENCES:
        return None
    return Observation(
        code="severe_pain_pattern",
        severity=SEVERITY_SEEK_CARE,
        title="Pain symptoms logged repeatedly",
        body=(
            f"You logged pain-related symptoms in {len(pain_cycles)} of your "
            f"last {len(window)} cycles. If you are experiencing severe or "
            "persistent pain, please consult a qualified healthcare "
            "professional."
        ),
        evidence={
            "pain_cycles": len(pain_cycles),
            "window": len(window),
            "start_dates": [c.start_date.isoformat() for c in pain_cycles],
            "symptoms_seen": sorted(
                set(
                    s
                    for c in pain_cycles
                    for s in c.symptoms
                    if s in PAIN_SYMPTOMS
                )
            ),
        },
        priority=15,
    )

def rule_repeated_heavy_flow_seek_care(analysis: CycleAnalysis) -> Optional[Observation]:
    window = analysis.cycles[:HEAVY_FLOW_WINDOW]
    heavy = [c for c in window if c.flow_intensity == "heavy"]
    if len(heavy) < HEAVY_FLOW_MIN_OCCURRENCES:
        return None
    return Observation(
        code="repeated_heavy_flow_concern",
        severity=SEVERITY_SEEK_CARE,
        title="Heavy bleeding may require medical attention",
        body=(
            f"You described your flow as heavy in {len(heavy)} of your last "
            f"{len(window)} logged cycles. Very heavy or prolonged bleeding "
            "can sometimes be a sign that needs checking. "
            "Please consult a qualified healthcare professional."
        ),
        evidence={
            "heavy_cycles": len(heavy),
            "window": len(window),
            "start_dates": [c.start_date.isoformat() for c in heavy],
        },
        priority=25,
    )

def rule_frequent_bleeding_pattern(analysis: CycleAnalysis) -> Optional[Observation]:
    if len(analysis.gaps) < FREQUENT_BLEEDING_MIN_CONSECUTIVE:
        return None
    consecutive_short = 0
    for gap in analysis.gaps:
        if gap < FREQUENT_BLEEDING_MAX_GAP_DAYS:
            consecutive_short += 1
        else:
            consecutive_short = 0
        if consecutive_short >= FREQUENT_BLEEDING_MIN_CONSECUTIVE:
            break
    if consecutive_short < FREQUENT_BLEEDING_MIN_CONSECUTIVE:
        return None
    return Observation(
        code="frequent_bleeding_pattern",
        severity=SEVERITY_SEEK_CARE,
        title="Cycles have been shorter than usual recently",
        body=(
            f"Your last {consecutive_short} cycles have been shorter than "
            f"{FREQUENT_BLEEDING_MAX_GAP_DAYS} days. Frequent or closely "
            "spaced periods can sometimes need medical attention. "
            "Please consult a qualified healthcare professional."
        ),
        evidence={
            "consecutive_short_cycles": consecutive_short,
            "threshold_days": FREQUENT_BLEEDING_MAX_GAP_DAYS,
            "recent_gaps": analysis.gaps[:consecutive_short],
        },
        priority=35,
    )

RULES = (
    rule_insufficient_data,
    rule_no_recent_period_logged,
    rule_prolonged_bleeding,
    rule_severe_pain_pattern,
    rule_repeated_heavy_flow_seek_care,
    rule_frequent_bleeding_pattern,
    rule_repeated_heavy_flow,
    rule_short_cycle_observed,
    rule_long_cycle_observed,
    rule_variable_cycle_lengths,
    rule_period_later_than_usual,
    rule_symptom_increase,
    rule_sustained_high_stress,
    rule_short_sleep_trend,
)

def sort_observations(observations: Sequence[Observation]) -> List[Observation]:
    return sorted(
        observations,
        key=lambda o: (-SEVERITY_ORDER.get(o.severity, 0), o.priority, o.code),
    )

def describe_consistency(analysis: CycleAnalysis) -> str:
    if len(analysis.gaps) < MIN_CYCLES_FOR_ANALYSIS:
        return CONSISTENCY_UNKNOWN
    spread = max(analysis.gaps) - min(analysis.gaps)
    if spread <= CONSISTENT_SPREAD_DAYS:
        return CONSISTENCY_CONSISTENT
    if spread <= SLIGHTLY_VARIABLE_SPREAD_DAYS:
        return CONSISTENCY_SLIGHTLY_VARIABLE
    return CONSISTENCY_VARIABLE

def describe_consistency_text(analysis: CycleAnalysis) -> str:
    if len(analysis.cycles) < MIN_CYCLES_FOR_ANALYSIS:
        return "Not enough cycle data yet to describe your patterns."

    gaps = analysis.gaps
    if not gaps:
        return "Not enough cycle data yet to describe your patterns."

    spread = max(gaps) - min(gaps)
    count = len(gaps)
    avg = round(sum(gaps) / count)

    if spread <= CONSISTENT_SPREAD_DAYS:
        return (
            f"Your recent cycles have been fairly consistent, "
            f"averaging about {avg} days."
        )

    if spread <= SLIGHTLY_VARIABLE_SPREAD_DAYS:
        return (
            f"Your cycle length has varied by about {spread} days "
            f"over the last {count} cycles."
        )

    return (
        f"Your cycle length has become more variable recently, "
        f"ranging from {min(gaps)} to {max(gaps)} days."
    )

def evaluate(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
) -> List[Observation]:
    analysis = build_analysis(logs, profile=profile, today=today)
    fired = [observation for rule in RULES if (observation := rule(analysis))]
    return sort_observations(fired)

def top_observation(observations: Sequence[Observation]) -> Optional[Observation]:
    ordered = sort_observations(observations)
    return ordered[0] if ordered else None

def get_user_observations(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    analysis = build_analysis(logs, profile=profile, today=today)
    observations = sort_observations(
        [observation for rule in RULES if (observation := rule(analysis))]
    )
    highest = observations[0] if observations else None

    return {
        "observations": [o.to_dict() for o in observations],
        "topObservation": highest.to_dict() if highest else None,
        "cycleConsistency": describe_consistency(analysis),
        "cycleConsistencyDescription": describe_consistency_text(analysis),
        "averageCycleLength": analysis.average_cycle_length if analysis.gaps else None,
        "analyzedCycleCount": len(analysis.cycles),
        "disclaimer": DISCLAIMER_TEXT,
        "disclaimerKey": DISCLAIMER_KEY,
    }

__all__ = [
    "CONSISTENCY_CONSISTENT",
    "CONSISTENCY_SLIGHTLY_VARIABLE",
    "CONSISTENCY_UNKNOWN",
    "CONSISTENCY_VARIABLE",
    "DISCLAIMER_KEY",
    "DISCLAIMER_TEXT",
    "PAIN_SYMPTOMS",
    "RULES",
    "SEVERITY_ATTENTION",
    "SEVERITY_INFO",
    "SEVERITY_ORDER",
    "SEVERITY_SEEK_CARE",
    "CycleAnalysis",
    "CycleObservationInput",
    "Observation",
    "build_analysis",
    "describe_consistency",
    "describe_consistency_text",
    "evaluate",
    "get_user_observations",
    "sort_observations",
    "top_observation",
]
