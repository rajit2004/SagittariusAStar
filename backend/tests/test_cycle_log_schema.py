from datetime import date
import pytest

from api.cycle import CycleLog, CycleLogResponse

def test_cycle_log_response_schema_validation():
    today = date.today()
    log_input = CycleLog(
        start_date=today,
        flow_intensity="medium",
        mood="happy",
        symptoms=["cramps"],
        sleep_hours=7.5,
        stress_level=2,
    )

    response_payload = {
        "message": "Cycle logged successfully",
        "id": "mock-log-123",
        "data": log_input,
    }

    response_model = CycleLogResponse(**response_payload)
    assert response_model.id == "mock-log-123"
    assert response_model.data.start_date == today
    assert response_model.data.flow_intensity == "medium"
    assert response_model.data.symptoms == ["cramps"]
