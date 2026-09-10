import pytest
from unittest.mock import patch
from models.mhs_model import predict_mhs, mhs_label, _compute_lifestyle_score

@pytest.fixture(autouse=True)
def mock_cvi_no_model():
    with patch("models.cvi_model._load_model", return_value=None):
        yield

def test_predict_mhs_insufficient_data():
    assert predict_mhs([]) is None
    assert predict_mhs([{}]) is None

def test_predict_mhs_two_logs():
    logs = [{"cycle_length": 28, "sleep_avg": 8.0, "stress_avg": 1.0, "symptom_count": 0}] * 2
    assert predict_mhs(logs) == 80.5

def test_predict_mhs_happy_path():
    logs = [{"cycle_length": 28, "sleep_avg": 8.0, "stress_avg": 1.0, "symptom_count": 0}] * 3
    assert predict_mhs(logs) == 86.5

def test_predict_mhs_missing_optional_fields():
    logs = [{}, {}, {}]
    assert predict_mhs(logs) == 76.0

def test_predict_mhs_worst_case():
    logs = [
        {"cycle_length": 14, "sleep_avg": 24.0, "stress_avg": 5.0, "symptom_count": 10},
        {"cycle_length": 42, "sleep_avg": 24.0, "stress_avg": 5.0, "symptom_count": 10},
        {"cycle_length": 14, "sleep_avg": 24.0, "stress_avg": 5.0, "symptom_count": 10}
    ]
    assert predict_mhs(logs) == 10.5

def test_predict_mhs_zero_values():
    logs = [{"cycle_length": 28, "sleep_avg": 0.0, "stress_avg": 0.0, "symptom_count": 0}] * 3
    assert predict_mhs(logs) == 71.5

def test_mhs_label():
    assert mhs_label(0.0) == "Needs attention"
    assert mhs_label(49.9) == "Needs attention"
    assert mhs_label(50.0) == "Fair"
    assert mhs_label(74.9) == "Fair"
    assert mhs_label(75.0) == "Good"
    assert mhs_label(100.0) == "Good"

def test_lifestyle_fallback_default():
    assert _compute_lifestyle_score(None) == 70.0

def test_lifestyle_fallback_empty_profile():
    assert _compute_lifestyle_score({}) == 50.0

def test_lifestyle_daily_balanced():
    profile = {"exercise_frequency": "daily", "diet_type": "balanced"}
    assert _compute_lifestyle_score(profile) == 100.0

def test_lifestyle_weekly_vegetarian():
    profile = {"exercise_frequency": "weekly", "diet_type": "vegetarian"}
    assert _compute_lifestyle_score(profile) == 75.0

def test_lifestyle_rarely_vegan():
    profile = {"exercise_frequency": "rarely", "diet_type": "vegan"}
    assert _compute_lifestyle_score(profile) == 50.0

def test_lifestyle_never_high_protein():
    profile = {"exercise_frequency": "never", "diet_type": "high_protein"}
    assert _compute_lifestyle_score(profile) == 40.0

def test_lifestyle_unknown_values():
    profile = {"exercise_frequency": "extreme", "diet_type": "paleo"}
    assert _compute_lifestyle_score(profile) == 50.0

def test_lifestyle_partial_only_exercise():
    profile = {"exercise_frequency": "daily"}
    assert _compute_lifestyle_score(profile) == 75.0

def test_lifestyle_partial_only_diet():
    profile = {"diet_type": "balanced"}
    assert _compute_lifestyle_score(profile) == 75.0

def test_predict_mhs_with_profile():
    logs = [{"cycle_length": 28, "sleep_avg": 8.0, "stress_avg": 1.0, "symptom_count": 0}] * 3
    profile = {"exercise_frequency": "daily", "diet_type": "balanced"}
    assert predict_mhs(logs, profile=profile) == 91.0

def test_predict_mhs_with_profile_no_lifestyle_fields():
    logs = [{"cycle_length": 28, "sleep_avg": 8.0, "stress_avg": 1.0, "symptom_count": 0}] * 3
    profile = {"age": 25, "city": "Delhi"}
    assert predict_mhs(logs, profile=profile) == 83.5
