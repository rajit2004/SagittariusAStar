
import os
import numpy as np
from typing import Optional

_model = None
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "cvi_model.joblib")

def _load_model():
    global _model
    if _model is None:
        try:
            import joblib
            _model = joblib.load(_MODEL_PATH)
        except FileNotFoundError:
            _model = None
    return _model

def predict_cvi(cycle_logs: list[dict]) -> Optional[float]:
    if len(cycle_logs) < 3:
        return None

    recent = cycle_logs[:6]
    lengths = [log.get("cycle_length", 28) for log in recent]
    flows = [log.get("flow_duration", 5) for log in recent]
    stresses = [log.get("stress_avg", 2.5) for log in recent]
    sleeps = [log.get("sleep_avg", 7.0) for log in recent]

    features = np.array([[
        np.mean(lengths),
        np.std(lengths),
        np.mean(flows),
        np.std(flows),
        max(lengths) - min(lengths),
        np.mean(stresses),
        np.mean(sleeps),
        len(recent),
    ]])

    model = _load_model()

    if model is not None:

        raw = float(model.predict(features)[0])
        return max(0.0, min(100.0, raw))
    else:

        std_dev = float(np.std(lengths))

        heuristic_cvi = min(100.0, std_dev * 8 + 30)
        return round(heuristic_cvi, 1)

def risk_level(cvi: float) -> str:
    if cvi < 30:
        return "low"
    elif cvi < 65:
        return "medium"
    else:
        return "high"
