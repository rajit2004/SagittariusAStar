from datetime import date, timedelta

import pytest

from services.prediction_service import predict
from services.sms_summary_service import (
    DEFAULT_LANGUAGE,
    GSM7_ELLIPSIS,
    GSM7_SINGLE_SEGMENT,
    UCS2_ELLIPSIS,
    SITUATION_DUE_TODAY,
    SITUATION_NO_ANCHOR,
    SITUATION_OVERDUE,
    SITUATION_UNMEASURED,
    SITUATION_UPCOMING,
    SUPPORTED_SMS_LANGUAGES,
    TEMPLATES,
    UCS2_CONCATENATED_SEGMENT,
    UCS2_MAX_SEGMENTS,
    build_summary,
    compose,
    describe,
    fit_to_budget,
    gsm7_length,
    is_gsm7,
    measured_length,
    resolve_language,
    segment_budget,
    template_placeholders,
)

TODAY = date(2026, 6, 1)

def _starts(*offsets_back):
    return [{"start_date": TODAY - timedelta(days=back)} for back in offsets_back]

def _regular_28_day_history(days_since_last_start):
    return _starts(
        days_since_last_start,
        days_since_last_start + 28,
        days_since_last_start + 56,
        days_since_last_start + 84,
    )

def test_a_late_period_is_reported_as_late_not_as_zero_days():
    result = describe(_regular_28_day_history(33), profile={}, today=TODAY)

    assert result["situation"] == SITUATION_OVERDUE
    assert result["isOverdue"] is True
    assert result["daysOverdue"] == 5
    assert "5 days late" in result["body"]
    assert "~0 days" not in result["body"]

def test_the_number_in_the_sms_matches_the_number_the_dashboard_would_show():
    logs = _regular_28_day_history(37)
    prediction = predict(logs, profile={}, today=TODAY)

    result = describe(logs, profile={}, today=TODAY)

    assert result["daysOverdue"] == prediction.days_overdue
    assert result["daysUntilNextPeriod"] == prediction.days_until_next_period
    assert str(prediction.days_overdue) in result["body"]

def test_due_today_is_its_own_sentence_not_a_countdown_of_zero():

    result = describe(_regular_28_day_history(28), profile={}, today=TODAY)

    assert result["situation"] == SITUATION_DUE_TODAY
    assert result["daysUntilNextPeriod"] == 0
    assert "expected today" in result["body"]

def test_an_upcoming_period_still_reads_as_it_always_did():
    result = describe(_regular_28_day_history(14), profile={}, today=TODAY)

    assert result["situation"] == SITUATION_UPCOMING
    assert "Rhythma Summary" in result["body"]
    assert "Next period expected" in result["body"]
    assert "~14 days" in result["body"]

def test_consecutive_day_logs_are_not_averaged_into_a_one_day_cycle():
    three_days_running = _starts(2, 3, 4)

    result = describe(three_days_running, profile={}, today=TODAY)

    assert result["estimateSource"] != "logged_history"
    assert "1 days" not in result["body"]

def test_one_outlier_cycle_does_not_drag_the_estimate():
    logs = _starts(10, 38, 66, 150, 178, 206)

    result = describe(logs, profile={}, today=TODAY)
    prediction = predict(logs, profile={}, today=TODAY)

    assert prediction.cycle_length.days == 28
    assert result["estimateSource"] == "logged_history"

def test_a_user_with_no_history_is_not_told_a_population_default_is_her_cycle():
    result = describe(
        [{"start_date": TODAY - timedelta(days=10)}], profile={}, today=TODAY
    )

    assert result["situation"] == SITUATION_UNMEASURED
    assert result["estimateSource"] == "population_default"
    assert "Next period expected" not in result["body"]

def test_a_declared_cycle_length_is_used_before_the_population_default():
    profile = {"cycle_length": 35}
    logs = [{"start_date": TODAY - timedelta(days=30)}]

    result = describe(logs, profile=profile, today=TODAY)

    assert result["estimateSource"] == "declared_cycle_length"
    assert result["situation"] == SITUATION_UPCOMING
    assert "~5 days" in result["body"]

def test_no_anchor_at_all_invents_no_date():
    result = describe([], profile={}, today=TODAY)

    assert result["situation"] == SITUATION_NO_ANCHOR
    assert result["daysUntilNextPeriod"] is None
    assert "Log your last period" in result["body"]

    assert "~" not in result["body"]

def test_the_onboarding_last_period_anchors_a_user_who_has_logged_nothing():
    profile = {"last_period": "2026-05-18", "cycle_length": 30}

    result = describe([], profile=profile, today=TODAY)

    assert result["situation"] == SITUATION_UPCOMING
    assert "~16 days" in result["body"]

@pytest.mark.parametrize("code", sorted(SUPPORTED_SMS_LANGUAGES))
def test_every_supported_language_renders_every_situation(code):
    for days_back, expected in (
        (33, SITUATION_OVERDUE),
        (28, SITUATION_DUE_TODAY),
        (14, SITUATION_UPCOMING),
    ):
        logs = _regular_28_day_history(days_back)
        prediction = predict(logs, profile={}, today=TODAY)
        body = compose(prediction, code)

        assert body, f"{code}/{expected} rendered empty"
        assert "{" not in body and "}" not in body

@pytest.mark.parametrize("code", sorted(SUPPORTED_SMS_LANGUAGES - {"en"}))
def test_a_translation_may_not_drop_a_placeholder(code):
    reference = template_placeholders()

    for situation, expected in reference.items():
        template = getattr(TEMPLATES[code], situation)
        used = sorted(
            {
                name
                for name in expected
                if "{" + name + "}" in template
            }
        )
        assert used == expected, f"{code}.{situation} uses {used}, expected {expected}"

def test_the_summary_is_written_in_the_language_on_the_account():
    hindi = describe(_regular_28_day_history(14), profile={"language": "hi"}, today=TODAY)
    english = describe(_regular_28_day_history(14), profile={"language": "en"}, today=TODAY)

    assert hindi["language"] == "hi"
    assert hindi["body"] != english["body"]
    assert "Rhythma Summary" not in hindi["body"]

@pytest.mark.parametrize(
    "stored,expected",
    [
        ("hi", "hi"),
        ("HI", "hi"),
        (" hi ", "hi"),
        ("hi-IN", "hi"),
        ("hi_IN", "hi"),
        ("mr", "mr"),

        ("fr", DEFAULT_LANGUAGE),
        ("", DEFAULT_LANGUAGE),
        (None, DEFAULT_LANGUAGE),
        (42, DEFAULT_LANGUAGE),
    ],
)
def test_stored_language_values_are_normalized_rather_than_trusted(stored, expected):
    assert resolve_language({"language": stored}) == expected

def test_a_missing_profile_falls_back_to_english_rather_than_failing():
    assert resolve_language(None) == DEFAULT_LANGUAGE
    assert resolve_language({}) == DEFAULT_LANGUAGE

def test_english_summaries_are_gsm7_and_fit_one_segment():
    for days_back in (5, 14, 27, 33, 40):
        body = build_summary(_regular_28_day_history(days_back), profile={}, today=TODAY)
        assert is_gsm7(body), body
        assert gsm7_length(body) <= GSM7_SINGLE_SEGMENT, body

def test_an_indic_summary_is_measured_against_a_ucs2_budget_not_160():
    body = build_summary(
        _regular_28_day_history(14), profile={"language": "hi"}, today=TODAY
    )

    assert not is_gsm7(body)
    assert segment_budget(body) == UCS2_CONCATENATED_SEGMENT * UCS2_MAX_SEGMENTS
    assert measured_length(body) <= segment_budget(body)

@pytest.mark.parametrize("code", sorted(SUPPORTED_SMS_LANGUAGES))
def test_no_language_produces_a_message_over_its_own_budget(code):
    for days_back in (5, 14, 27, 33, 40, 95):
        body = build_summary(
            _regular_28_day_history(days_back), profile={"language": code}, today=TODAY
        )
        assert measured_length(body) <= segment_budget(body), f"{code}: {body}"

def test_the_disclaimer_is_all_or_nothing():
    body = build_summary(_regular_28_day_history(14), profile={}, today=TODAY)

    assert "Estimate only" in body
    assert body.rstrip().endswith("medical/contraceptive advice.")

@pytest.mark.parametrize("code", sorted(SUPPORTED_SMS_LANGUAGES))
def test_every_language_carries_its_disclaimer(code):
    body = build_summary(
        _regular_28_day_history(14), profile={"language": code}, today=TODAY
    )

    assert TEMPLATES[code].disclaimer.strip() in body

def test_gsm7_detection_knows_the_extended_characters_cost_two():
    assert is_gsm7("Rhythma: day 14")
    assert gsm7_length("abc") == 3

    assert is_gsm7("€")
    assert gsm7_length("€") == 2

    assert not is_gsm7("रिदमा")

def test_a_long_summary_is_cut_at_a_word_not_through_a_number():
    text = "Rhythma Summary: " + ("word " * 60) + "final"

    fitted = fit_to_budget(text)

    assert measured_length(fitted) <= segment_budget(text)
    assert fitted.endswith(GSM7_ELLIPSIS)
    assert not fitted.rstrip(".").endswith("wor")

def test_trimming_a_gsm7_message_does_not_re_encode_it_as_ucs2():
    text = "Rhythma Summary: " + ("word " * 60) + "final"
    assert is_gsm7(text)

    fitted = fit_to_budget(text)

    assert is_gsm7(fitted), "trimming must not force UCS-2"
    assert gsm7_length(fitted) <= GSM7_SINGLE_SEGMENT
    assert UCS2_ELLIPSIS not in fitted

def test_trimming_a_ucs2_message_keeps_the_typographic_ellipsis():
    text = "रिदमा " + ("शब्द " * 60) + "अंत"
    assert not is_gsm7(text)

    fitted = fit_to_budget(text)

    assert fitted.endswith(UCS2_ELLIPSIS)
    assert measured_length(fitted) <= segment_budget(text)

def test_a_short_summary_is_returned_untouched():
    text = "Rhythma: day 14 of your cycle."
    assert fit_to_budget(text) == text

def test_describe_reports_the_encoding_it_actually_used():
    english = describe(_regular_28_day_history(14), profile={}, today=TODAY)
    tamil = describe(
        _regular_28_day_history(14), profile={"language": "ta"}, today=TODAY
    )

    assert english["encoding"] == "GSM-7"
    assert tamil["encoding"] == "UCS-2"
