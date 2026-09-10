import os
import pytest
from unittest.mock import patch
from models.cvi_model import predict_cvi, risk_level

@pytest.fixture
def mock_no_model():
    with patch("models.cvi_model._load_model", return_value=None):
        yield

@pytest.mark.usefixtures("mock_no_model")
class TestHeuristicFallback:
    def test_predict_cvi_insufficient_data(self):
        assert predict_cvi([]) is None
        assert predict_cvi([{"cycle_length": 28}]) is None
        assert predict_cvi([{"cycle_length": 28}, {"cycle_length": 28}]) is None

    def test_predict_cvi_perfect_regularity(self):
        logs = [{"cycle_length": 28}] * 3
        assert predict_cvi(logs) == 30.0

    def test_predict_cvi_high_variance(self):
        logs = [{"cycle_length": 14}, {"cycle_length": 42}] * 2
        assert predict_cvi(logs) == 100.0

    def test_predict_cvi_missing_fields(self):
        logs = [{}, {}, {}]
        assert predict_cvi(logs) == 30.0

    def test_predict_cvi_known_variance(self):
        logs = [
            {"cycle_length": 24},
            {"cycle_length": 28},
            {"cycle_length": 32}
        ]
        assert predict_cvi(logs) == 56.1

    def test_risk_level_boundaries(self):
        assert risk_level(0) == "low"
        assert risk_level(29.9) == "low"
        assert risk_level(30.0) == "medium"
        assert risk_level(64.9) == "medium"
        assert risk_level(65.0) == "high"
        assert risk_level(100.0) == "high"

    def test_predict_cvi_uses_latest_logs(self):
        logs = [{"cycle_length": 28}] * 6 + [{"cycle_length": 40}, {"cycle_length": 15}, {"cycle_length": 40}, {"cycle_length": 15}]
        assert predict_cvi(logs) == 30.0

def test_model_artifact_exists():
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "models",
        "cvi_model.joblib",
    )
    assert os.path.exists(model_path), (
        "cvi_model.joblib not found. Run python scripts/train_cvi_model.py to generate it."
    )

def test_model_artifact_is_loadable():
    import joblib
    model_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "models",
        "cvi_model.joblib",
    )
    model = joblib.load(model_path)
    import numpy as np
    sample = np.array([[28.0, 2.0, 5.0, 0.5, 6.0, 2.5, 7.0, 4.0]])
    pred = float(model.predict(sample)[0])
    assert 0.0 <= pred <= 100.0, "Prediction must be in valid CVI range 0-100"

def test_predict_cvi_uses_real_model():
    logs = [{"cycle_length": 28}] * 3
    result = predict_cvi(logs)
    assert result is not None
    assert result != 30.0, "Heuristic fallback (30.0) was used instead of the real model"
