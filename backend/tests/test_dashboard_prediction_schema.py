from unittest.mock import MagicMock

import pytest

from main import app
from api import dashboard as dashboard_module
from api.dashboard import (
    DashboardFertileWindow,
    DashboardPrediction,
    DashboardPredictionRange,
    DashboardResponse,
)

@pytest.fixture(scope="module")
def schema():
    return app.openapi()

@pytest.fixture(scope="module")
def components(schema):
    return schema["components"]["schemas"]

def _resolve(components, node):
    if "$ref" in node:
        return components[node["$ref"].rsplit("/", 1)[-1]]
    for branch in node.get("anyOf", []):
        if "$ref" in branch:
            return components[branch["$ref"].rsplit("/", 1)[-1]]
    return None

def _ref_name(node):
    if "$ref" in node:
        return node["$ref"].rsplit("/", 1)[-1]
    for branch in node.get("anyOf", []):
        if "$ref" in branch:
            return branch["$ref"].rsplit("/", 1)[-1]
    return None

def test_dashboard_declares_dashboard_prediction_exactly_once():
    source = open(dashboard_module.__file__, encoding="utf-8").read()
    assert source.count("class DashboardPrediction(BaseModel)") == 1

def test_no_model_in_the_module_is_declared_twice():
    import re

    source = open(dashboard_module.__file__, encoding="utf-8").read()
    names = re.findall(r"^class (\w+)\(BaseModel\)", source, flags=re.MULTILINE)
    duplicates = {name for name in names if names.count(name) > 1}
    assert duplicates == set()

def test_dashboard_module_imports_nothing_it_does_not_use():
    source = open(dashboard_module.__file__, encoding="utf-8").read()
    assert "from services.firestore_service import UserService" not in source

def test_prediction_is_a_typed_object_on_the_response(components):
    assert _ref_name(DashboardResponse.model_json_schema()["properties"]["prediction"])

def test_predicted_range_is_a_typed_model_not_a_free_dict(components):
    node = components["DashboardPrediction"]["properties"]["predictedRange"]
    assert _ref_name(node) == "DashboardPredictionRange"

    resolved = _resolve(components, node)
    assert set(resolved["properties"]) == {"earliest", "latest"}

def test_fertile_window_is_a_typed_model_not_a_free_dict(components):
    node = components["DashboardPrediction"]["properties"]["fertileWindow"]
    assert _ref_name(node) == "DashboardFertileWindow"

    resolved = _resolve(components, node)
    assert set(resolved["properties"]) == {
        "start",
        "end",
        "isEstimate",
        "notForContraception",
    }

def test_the_contraception_warning_is_in_the_published_schema(components):
    resolved = _resolve(
        components, components["DashboardPrediction"]["properties"]["fertileWindow"]
    )
    assert resolved["properties"]["notForContraception"]["default"] is True
    assert resolved["properties"]["isEstimate"]["default"] is True

def test_both_nested_models_are_published(components):
    assert "DashboardPredictionRange" in components
    assert "DashboardFertileWindow" in components

def test_days_until_next_period_keeps_its_documented_meaning(components):
    node = components["DashboardPrediction"]["properties"]["daysUntilNextPeriod"]
    assert "not clamped" in node.get("description", "").lower()

def test_confidence_defaults_to_the_most_conservative_value():
    assert DashboardPrediction().confidence == "low"

def test_estimate_source_defaults_to_the_population_default():
    assert DashboardPrediction().estimateSource == "population_default"

def test_nested_defaults_are_real_objects_not_empty_dicts():
    prediction = DashboardPrediction()
    assert isinstance(prediction.predictedRange, DashboardPredictionRange)
    assert isinstance(prediction.fertileWindow, DashboardFertileWindow)
    assert prediction.fertileWindow.notForContraception is True
    assert prediction.fertileWindow.isEstimate is True

def test_a_default_prediction_still_serialises_every_field():
    dumped = DashboardPrediction().model_dump()
    assert dumped["predictedRange"] == {"earliest": None, "latest": None}
    assert dumped["fertileWindow"] == {
        "start": None,
        "end": None,
        "isEstimate": True,
        "notForContraception": True,
    }

def _service_shaped_summary():
    return {
        "nextPeriodDate": "2026-09-01",
        "daysUntilNextPeriod": -3,
        "isOverdue": True,
        "daysOverdue": 3,
        "phase": "late",
        "confidence": "medium",
        "estimateSource": "logged_history",
        "predictedRange": {"earliest": "2026-08-29", "latest": "2026-09-04"},
        "fertileWindow": {
            "start": "2026-08-15",
            "end": "2026-08-20",
            "isEstimate": True,
            "notForContraception": True,
        },
    }

def test_the_service_payload_validates_against_the_model():
    prediction = DashboardPrediction(**_service_shaped_summary())

    assert prediction.predictedRange.earliest == "2026-08-29"
    assert prediction.fertileWindow.end == "2026-08-20"
    assert prediction.daysUntilNextPeriod == -3
    assert prediction.isOverdue is True

def test_a_signed_days_until_survives_serialisation():
    prediction = DashboardPrediction(**_service_shaped_summary())
    assert prediction.model_dump()["daysUntilNextPeriod"] == -3

def test_a_new_user_with_no_anchor_date_still_validates():
    prediction = DashboardPrediction(
        nextPeriodDate=None,
        daysUntilNextPeriod=None,
        phase="unknown",
        confidence="low",
        estimateSource="population_default",
        predictedRange={"earliest": None, "latest": None},
        fertileWindow={
            "start": None,
            "end": None,
            "isEstimate": True,
            "notForContraception": True,
        },
    )
    assert prediction.nextPeriodDate is None
    assert prediction.isOverdue is False
    assert prediction.daysOverdue == 0

def test_prediction_is_still_nullable_on_the_response():
    node = DashboardResponse.model_json_schema()["properties"]["prediction"]
    assert any(branch.get("type") == "null" for branch in node.get("anyOf", []))

def test_the_model_matches_the_service_key_for_key():
    from datetime import date as date_type

    from services.prediction_service import dashboard_summary, predict

    emitted = dashboard_summary(predict([], profile={}, today=date_type(2026, 8, 6)))

    assert set(emitted) == set(DashboardPrediction.model_fields)
    assert set(emitted["predictedRange"]) == set(
        DashboardPredictionRange.model_fields
    )
    assert set(emitted["fertileWindow"]) == set(DashboardFertileWindow.model_fields)
