from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from api.cycle import CycleLog, CycleLogUpdate
from core.cycle_validation import (
    FLOW_INTENSITIES,
    KNOWN_SYMPTOMS,
    MAX_LOG_AGE_DAYS,
    MAX_NOTES_CHARS,
    MAX_PERIOD_DURATION_DAYS,
    MAX_SLEEP_HOURS,
    MAX_STRESS_LEVEL,
    MAX_SYMPTOM_CHARS,
    MAX_SYMPTOMS,
    MIN_STRESS_LEVEL,
    MOODS,
    earliest_loggable_date,
    loggable_values,
    normalize_choice,
    normalize_notes,
    normalize_symptoms,
    validate_end_date,
    validate_sleep_hours,
    validate_start_date,
    validate_stress_level,
)

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)

def test_the_payload_from_the_issue_is_refused():
    with pytest.raises(ValidationError) as excinfo:
        CycleLog(
            start_date=date(3025, 1, 1),
            flow_intensity="banana",
            mood=" -not-a-mood",
            symptoms=["x" * 500] * 200,
            sleep_hours=-5000.0,
            stress_level=999999,
            notes="n" * 50000,
        )

    failed_fields = {error["loc"][0] for error in excinfo.value.errors()}
    assert {
        "start_date",
        "flow_intensity",
        "mood",
        "symptoms",
        "sleep_hours",
        "stress_level",
        "notes",
    } <= failed_fields

def test_an_ordinary_log_still_validates():
    log = CycleLog(
        start_date=YESTERDAY,
        end_date=TODAY,
        flow_intensity="medium",
        mood="neutral",
        symptoms=["cramps", "headache"],
        sleep_hours=7.5,
        stress_level=3,
        notes="Slept badly, cramps in the afternoon.",
    )

    assert log.flow_intensity == "medium"
    assert log.symptoms == ["cramps", "headache"]
    assert log.sleep_hours == 7.5

def test_a_bare_start_date_is_a_valid_log():
    assert CycleLog(start_date=TODAY).flow_intensity is None

@pytest.mark.parametrize("value", FLOW_INTENSITIES)
def test_every_documented_flow_intensity_is_accepted(value):
    assert CycleLog(start_date=TODAY, flow_intensity=value).flow_intensity == value

@pytest.mark.parametrize("value", MOODS)
def test_every_documented_mood_is_accepted(value):
    assert CycleLog(start_date=TODAY, mood=value).mood == value

def test_flutter_sends_none_and_it_must_keep_working():
    assert CycleLog(start_date=TODAY, flow_intensity="none").flow_intensity == "none"

@pytest.mark.parametrize("value", ["banana", "MEDIUM-ish", "3", "light heavy"])
def test_unknown_flow_intensities_are_refused(value):
    with pytest.raises(ValidationError):
        CycleLog(start_date=TODAY, flow_intensity=value)

def test_flow_intensity_is_casefolded_not_rejected():
    assert CycleLog(start_date=TODAY, flow_intensity="HEAVY").flow_intensity == "heavy"
    assert CycleLog(start_date=TODAY, flow_intensity=" Light ").flow_intensity == "light"

def test_an_empty_choice_is_treated_as_omission():
    assert CycleLog(start_date=TODAY, flow_intensity="").flow_intensity is None
    assert CycleLog(start_date=TODAY, mood="   ").mood is None

def test_the_rejection_message_names_the_allowed_values():
    with pytest.raises(ValidationError) as excinfo:
        CycleLog(start_date=TODAY, mood="ecstatic")

    message = str(excinfo.value)
    assert "happy" in message and "neutral" in message

def test_known_symptoms_pass_through():
    assert normalize_symptoms(list(KNOWN_SYMPTOMS)) == list(KNOWN_SYMPTOMS)

def test_unknown_symptoms_are_kept_not_refused():
    assert normalize_symptoms(["dizziness"]) == ["dizziness"]

def test_symptoms_are_casefolded_and_whitespace_collapsed():
    assert normalize_symptoms(["  Cramps ", "BACK    PAIN"]) == ["cramps", "back pain"]

def test_known_alternate_spellings_are_folded_together():
    assert normalize_symptoms(["backpain", "back_pain", "back pain"]) == ["back pain"]
    assert normalize_symptoms(["tiredness"]) == ["fatigue"]

def test_duplicates_are_dropped_and_order_preserved():
    assert normalize_symptoms(["headache", "cramps", "headache"]) == [
        "headache",
        "cramps",
    ]

def test_blank_symptoms_are_dropped():
    assert normalize_symptoms(["cramps", "", "   "]) == ["cramps"]

def test_too_many_symptoms_are_refused():
    with pytest.raises(ValueError, match="at most"):
        normalize_symptoms([f"symptom-{i}" for i in range(MAX_SYMPTOMS + 1)])

def test_exactly_the_maximum_number_of_symptoms_is_allowed():
    assert (
        len(normalize_symptoms([f"symptom-{i}" for i in range(MAX_SYMPTOMS)]))
        == MAX_SYMPTOMS
    )

def test_an_over_long_symptom_is_refused():
    with pytest.raises(ValueError, match="characters"):
        normalize_symptoms(["x" * (MAX_SYMPTOM_CHARS + 1)])

def test_a_bare_string_is_refused_rather_than_treated_as_one_symptom():
    with pytest.raises(ValueError, match="list"):
        normalize_symptoms("cramps")

def test_non_text_symptoms_are_refused():
    with pytest.raises(ValueError, match="text"):
        normalize_symptoms(["cramps", 42])

@pytest.mark.parametrize("value", [0.0, 4.0, 7.5, 9.5, 24.0])
def test_plausible_sleep_hours_are_accepted(value):
    assert validate_sleep_hours(value) == value

@pytest.mark.parametrize("value", [-0.1, -5000.0, 24.1, 900.0])
def test_impossible_sleep_hours_are_refused(value):
    with pytest.raises(ValueError, match="sleep_hours"):
        validate_sleep_hours(value)

def test_sleep_hours_bounds_are_inclusive():
    assert validate_sleep_hours(0.0) == 0.0
    assert validate_sleep_hours(MAX_SLEEP_HOURS) == MAX_SLEEP_HOURS

def test_infinity_and_nan_are_refused():
    for value in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(ValueError):
            validate_sleep_hours(value)

def test_a_boolean_is_not_a_number_of_hours():
    with pytest.raises(ValueError):
        validate_sleep_hours(True)

@pytest.mark.parametrize("value", [1, 2, 3, 4, 5])
def test_the_full_stress_scale_is_accepted(value):
    assert validate_stress_level(value) == value

@pytest.mark.parametrize("value", [0, -1, 6, 999999])
def test_out_of_range_stress_is_refused(value):
    with pytest.raises(ValueError, match="stress_level"):
        validate_stress_level(value)

def test_stress_bounds_are_inclusive():
    assert validate_stress_level(MIN_STRESS_LEVEL) == MIN_STRESS_LEVEL
    assert validate_stress_level(MAX_STRESS_LEVEL) == MAX_STRESS_LEVEL

def test_notes_are_trimmed():
    assert normalize_notes("  cramps all day  ") == "cramps all day"

def test_whitespace_only_notes_become_absent():
    assert normalize_notes("   \n\t ") is None

def test_notes_at_the_limit_are_accepted():
    assert len(normalize_notes("n" * MAX_NOTES_CHARS)) == MAX_NOTES_CHARS

def test_over_long_notes_are_refused():
    with pytest.raises(ValueError, match="characters"):
        normalize_notes("n" * (MAX_NOTES_CHARS + 1))

def test_a_long_note_is_measured_after_trimming():
    assert normalize_notes(" " * 5000 + "short" + " " * 5000) == "short"

def test_today_is_loggable():
    assert validate_start_date(TODAY, today=TODAY) == TODAY

def test_a_future_start_date_is_refused():
    with pytest.raises(ValueError, match="future"):
        validate_start_date(TODAY + timedelta(days=1), today=TODAY)

def test_an_ancient_start_date_is_refused():
    with pytest.raises(ValueError, match="before"):
        validate_start_date(date(1900, 1, 1), today=TODAY)

def test_the_age_floor_is_inclusive():
    floor = earliest_loggable_date(TODAY)
    assert validate_start_date(floor, today=TODAY) == floor
    with pytest.raises(ValueError):
        validate_start_date(floor - timedelta(days=1), today=TODAY)

def test_importing_a_few_years_of_history_still_works():
    three_years_ago = TODAY - timedelta(days=365 * 3)
    assert validate_start_date(three_years_ago, today=TODAY) == three_years_ago
    assert MAX_LOG_AGE_DAYS > 365 * 3

def test_an_end_date_before_the_start_date_is_refused():
    with pytest.raises(ValueError, match="before start_date"):
        validate_end_date(TODAY, TODAY - timedelta(days=2), today=TODAY)

def test_an_end_date_equal_to_the_start_date_is_a_one_day_period():
    assert validate_end_date(TODAY, TODAY, today=TODAY) == TODAY

def test_a_future_end_date_is_refused():
    with pytest.raises(ValueError, match="future"):
        validate_end_date(YESTERDAY, TODAY + timedelta(days=3), today=TODAY)

def test_an_implausibly_long_period_is_refused():
    start = TODAY - timedelta(days=MAX_PERIOD_DURATION_DAYS + 10)
    with pytest.raises(ValueError, match="span"):
        validate_end_date(start, TODAY, today=TODAY)

def test_a_long_but_plausible_period_is_accepted():
    start = TODAY - timedelta(days=13)
    assert validate_end_date(start, TODAY, today=TODAY) == TODAY

def test_the_model_rejects_an_inverted_range():
    with pytest.raises(ValidationError):
        CycleLog(start_date=TODAY, end_date=TODAY - timedelta(days=3))

@pytest.mark.parametrize(
    "payload",
    [
        {"flow_intensity": "banana"},
        {"mood": "ecstatic"},
        {"sleep_hours": -5000.0},
        {"stress_level": 999999},
        {"notes": "n" * (MAX_NOTES_CHARS + 1)},
        {"symptoms": ["x" * 500]},
        {"end_date": TODAY + timedelta(days=5)},
    ],
)
def test_the_update_schema_refuses_what_the_create_schema_refuses(payload):
    with pytest.raises(ValidationError):
        CycleLogUpdate(**payload)

    with pytest.raises(ValidationError):
        CycleLog(start_date=TODAY, **payload)

def test_the_update_schema_normalises_the_same_way():
    updated = CycleLogUpdate(flow_intensity="HEAVY", symptoms=["  Cramps "])
    assert updated.flow_intensity == "heavy"
    assert updated.symptoms == ["cramps"]

def test_normalize_choice_passes_none_through():
    assert normalize_choice(None, FLOW_INTENSITIES, "flow_intensity") is None

def test_normalize_choice_refuses_non_text():
    with pytest.raises(ValueError, match="text"):
        normalize_choice(3, FLOW_INTENSITIES, "flow_intensity")

def test_loggable_values_describes_what_is_enforced():
    described = loggable_values()

    assert described["flowIntensities"] == list(FLOW_INTENSITIES)
    assert described["moods"] == list(MOODS)
    assert described["knownSymptoms"] == list(KNOWN_SYMPTOMS)
    assert described["symptomsAreOpenEnded"] is True
    assert described["limits"]["stressLevel"] == {
        "min": MIN_STRESS_LEVEL,
        "max": MAX_STRESS_LEVEL,
    }
    assert described["limits"]["notesMaxChars"] == MAX_NOTES_CHARS

def test_every_described_choice_actually_validates():
    described = loggable_values()
    for value in described["flowIntensities"]:
        assert CycleLog(start_date=TODAY, flow_intensity=value)
    for value in described["moods"]:
        assert CycleLog(start_date=TODAY, mood=value)
    for value in described["knownSymptoms"]:
        assert CycleLog(start_date=TODAY, symptoms=[value])
