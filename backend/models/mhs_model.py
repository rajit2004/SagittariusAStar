
from typing import Optional
from .cvi_model import predict_cvi

_EXERCISE_SCORES = {
    "daily": 100.0,
    "weekly": 70.0,
    "rarely": 30.0,
    "never": 0.0,
}

_DIET_SCORES = {
    "balanced": 100.0,
    "vegetarian": 80.0,
    "vegan": 70.0,
    "high_protein": 80.0,
}

_DEFAULT_EXERCISE_SCORE = 50.0
_DEFAULT_DIET_SCORE = 50.0
_FALLBACK_LIFESTYLE_SCORE = 70.0

def _compute_lifestyle_score(profile: Optional[dict]) -> float:
    if profile is None:
        return _FALLBACK_LIFESTYLE_SCORE

    exercise_score = _EXERCISE_SCORES.get(
        profile.get("exercise_frequency"), _DEFAULT_EXERCISE_SCORE
    )
    diet_score = _DIET_SCORES.get(
        profile.get("diet_type"), _DEFAULT_DIET_SCORE
    )
    return (exercise_score + diet_score) / 2.0

def predict_mhs(cycle_logs: list[dict], profile: Optional[dict] = None) -> Optional[float]:
    if len(cycle_logs) < 2:
        return None

    recent = cycle_logs[:3]

    cvi = predict_cvi(cycle_logs)
    cvi_score = 100 - (cvi or 50)

    sleep_avg = sum(log.get("sleep_avg", 7.0) for log in recent) / len(recent)

    sleep_score = max(0.0, 100 - abs(sleep_avg - 8) * 15)

    stress_avg = sum(log.get("stress_avg", 2.5) for log in recent) / len(recent)
    stress_score = max(0.0, 100 - (stress_avg - 1) * 25)

    symptom_counts = [log.get("symptom_count", 0) for log in recent]
    avg_symptoms = sum(symptom_counts) / len(symptom_counts)
    symptom_score = max(0.0, 100 - avg_symptoms * 10)

    lifestyle_score = _compute_lifestyle_score(profile)

    mhs = (
        cvi_score       * 0.30
        + sleep_score   * 0.20
        + stress_score  * 0.20
        + symptom_score * 0.15
        + lifestyle_score * 0.15
    )

    return round(max(0.0, min(100.0, mhs)), 1)

def mhs_label(score: float) -> str:
    if score >= 75:
        return "Good"
    elif score >= 50:
        return "Fair"
    else:
        return "Needs attention"
