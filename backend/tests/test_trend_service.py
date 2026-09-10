from datetime import date, timedelta

import pytest

from services.trend_service import (
    BASIS_CYCLE,
    BASIS_RECENT_LOGS,
    DIRECTION_DECREASED,
    DIRECTION_INCREASED,
    DIRECTION_UNCHANGED,
    MIN_DAYS_BETWEEN_PERIOD_STARTS,
    build_trends,
    cycle_windows,
    period_starts,
    recent_log_windows,
    to_day_records,
)

TODAY = date(2026, 6, 30)

def _log(day, **fields):
    return {"start_date": day, **fields}

def _period_days(first_day, length=5, **fields):
    return [
        _log(first_day + timedelta(days=offset), flow_intensity="medium", **fields)
        for offset in range(length)
    ]

def _statement(result, metric):
    for entry in result["trends"]:
        if entry["metric"] == metric:
            return entry
    return None

def test_a_run_of_bleeding_days_is_one_period_not_five():
    records = to_day_records(_period_days(date(2026, 5, 1), length=5))

    assert period_starts(records) == [date(2026, 5, 1)]

def test_a_single_missed_day_does_not_split_a_period_in_two():
    logs = [
        _log(date(2026, 5, 1), flow_intensity="medium"),
        _log(date(2026, 5, 2), flow_intensity="medium"),

        _log(date(2026, 5, 4), flow_intensity="light"),
    ]

    assert period_starts(to_day_records(logs)) == [date(2026, 5, 1)]

def test_mid_cycle_spotting_does_not_open_a_phantom_cycle():
    logs = _period_days(date(2026, 5, 1)) + [
        _log(date(2026, 5, 11), flow_intensity="spotting"),
    ] + _period_days(date(2026, 5, 29))

    starts = period_starts(to_day_records(logs))

    assert starts == [date(2026, 5, 1), date(2026, 5, 29)]
    for earlier, later in zip(starts, starts[1:]):
        assert (later - earlier).days >= MIN_DAYS_BETWEEN_PERIOD_STARTS

def test_flow_logged_as_none_is_not_bleeding():
    logs = [_log(date(2026, 5, 1), flow_intensity="none")]

    assert period_starts(to_day_records(logs)) == []

def test_a_cycle_window_runs_from_one_start_to_the_day_before_the_next():
    logs = _period_days(date(2026, 5, 1)) + _period_days(date(2026, 5, 29))

    windows = cycle_windows(to_day_records(logs), TODAY)

    assert len(windows) == 1
    assert windows[0].start == date(2026, 5, 1)
    assert windows[0].end == date(2026, 5, 28)
    assert windows[0].days == 28

def test_the_cycle_in_progress_is_excluded():
    logs = (
        _period_days(date(2026, 4, 3))
        + _period_days(date(2026, 5, 1))
        + _period_days(date(2026, 6, 29))
    )

    windows = cycle_windows(to_day_records(logs), TODAY)

    assert len(windows) == 2
    assert windows[-1].end == date(2026, 6, 28)
    assert all(window.end < date(2026, 6, 29) for window in windows)

def test_two_adjacent_days_are_no_longer_reported_as_two_periods():
    logs = [
        _log(date(2026, 6, 28), sleep_hours=8, stress_level=2),
        _log(date(2026, 6, 29), sleep_hours=6, stress_level=4),
    ]

    result = build_trends(logs, today=TODAY)

    assert result["basis"] == BASIS_RECENT_LOGS
    assert result["basis"] != BASIS_CYCLE
    assert "Average" not in result["sleep"]
    assert "Logged sleep has decreased" in result["sleep"]

def test_a_single_reading_is_never_called_an_average():
    logs = [
        _log(date(2026, 6, 28), sleep_hours=8),
        _log(date(2026, 6, 29), sleep_hours=6),
    ]

    result = build_trends(logs, today=TODAY)
    sleep = _statement(result, "sleep")

    assert sleep["evidence"]["previousSamples"] == 1
    assert sleep["evidence"]["currentSamples"] == 1
    assert sleep["evidence"]["averaged"] is False
    assert "Average" not in sleep["text"]

def test_a_real_average_is_called_an_average_and_uses_every_value():
    logs = (
        _period_days(date(2026, 5, 1), sleep_hours=5)
        + _period_days(date(2026, 5, 29), sleep_hours=8)
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)
    sleep = _statement(result, "sleep")

    assert result["basis"] == BASIS_CYCLE
    assert sleep["evidence"]["previous"] == 5.0
    assert sleep["evidence"]["current"] == 8.0
    assert sleep["evidence"]["previousSamples"] == 5
    assert sleep["evidence"]["currentSamples"] == 5
    assert sleep["evidence"]["averaged"] is True
    assert "Average sleep has increased" in sleep["text"]

def test_one_bad_night_does_not_move_a_whole_cycle_average():
    previous = _period_days(date(2026, 5, 1), sleep_hours=7)
    current = [
        _log(date(2026, 5, 29), flow_intensity="medium", sleep_hours=8),
        _log(date(2026, 5, 30), flow_intensity="medium", sleep_hours=8),
        _log(date(2026, 5, 31), flow_intensity="medium", sleep_hours=8),
        _log(date(2026, 6, 1), flow_intensity="medium", sleep_hours=8),
        _log(date(2026, 6, 2), sleep_hours=3),
    ]
    logs = previous + current + _period_days(date(2026, 6, 26))

    result = build_trends(logs, today=TODAY)
    sleep = _statement(result, "sleep")

    assert sleep["evidence"]["current"] == 7.0
    assert sleep["direction"] == DIRECTION_UNCHANGED

def test_noise_is_reported_as_unchanged_rather_than_as_a_trend():
    logs = (
        _period_days(date(2026, 5, 1), sleep_hours=7.0)
        + _period_days(date(2026, 5, 29), sleep_hours=7.1)
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert _statement(result, "sleep")["direction"] == DIRECTION_UNCHANGED
    assert "about the same" in result["sleep"]

def test_a_symptom_is_reported_as_a_rate_not_as_present_or_absent():
    previous = [
        _log(date(2026, 5, 1), flow_intensity="medium", symptoms=["cramps"]),
        _log(date(2026, 5, 2), flow_intensity="medium", symptoms=[]),
        _log(date(2026, 5, 3), flow_intensity="medium", symptoms=[]),
        _log(date(2026, 5, 4), flow_intensity="medium", symptoms=[]),
        _log(date(2026, 5, 5), flow_intensity="medium", symptoms=[]),
    ]
    current = [
        _log(date(2026, 5, 29), flow_intensity="medium", symptoms=["cramps"]),
        _log(date(2026, 5, 30), flow_intensity="medium", symptoms=["cramps"]),
        _log(date(2026, 5, 31), flow_intensity="medium", symptoms=["cramps"]),
        _log(date(2026, 6, 1), flow_intensity="medium", symptoms=["cramps"]),
        _log(date(2026, 6, 2), flow_intensity="medium", symptoms=[]),
    ]
    logs = previous + current + _period_days(date(2026, 6, 26))

    result = build_trends(logs, today=TODAY)
    cramps = _statement(result, "cramps")

    assert cramps["direction"] == DIRECTION_INCREASED
    assert cramps["evidence"]["previousRate"] == 0.2
    assert cramps["evidence"]["currentRate"] == 0.8

def test_a_symptom_logged_in_neither_window_is_omitted_entirely():
    logs = (
        _period_days(date(2026, 5, 1), symptoms=["cramps"])
        + _period_days(date(2026, 5, 29), symptoms=["cramps"])
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert "acne" not in result["symptoms"]
    assert _statement(result, "acne") is None
    assert _statement(result, "cramps") is not None

def test_every_statement_carries_a_key_and_its_evidence():
    logs = (
        _period_days(date(2026, 5, 1), sleep_hours=5, stress_level=2, symptoms=["cramps"])
        + _period_days(date(2026, 5, 29), sleep_hours=8, stress_level=4, symptoms=["cramps"])
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert result["trends"]
    for statement in result["trends"]:
        assert statement["key"].startswith("trends.")
        assert statement["direction"] in {
            DIRECTION_INCREASED,
            DIRECTION_DECREASED,
            DIRECTION_UNCHANGED,
        }
        assert statement["evidence"], statement
        assert statement["text"]

    assert result["disclaimerKey"] == "insights.disclaimer"

def test_the_legacy_fields_still_carry_the_english_sentences():
    logs = (
        _period_days(date(2026, 5, 1), sleep_hours=5, stress_level=2, symptoms=["cramps"])
        + _period_days(date(2026, 5, 29), sleep_hours=8, stress_level=4, symptoms=["cramps"])
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert isinstance(result["sleep"], str)
    assert isinstance(result["stress"], str)
    assert isinstance(result["symptoms"], dict)
    assert result["notEnoughData"] is False

def test_stress_direction_follows_the_logged_values():
    logs = (
        _period_days(date(2026, 5, 1), stress_level=4)
        + _period_days(date(2026, 5, 29), stress_level=2)
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert _statement(result, "stress")["direction"] == DIRECTION_DECREASED

def test_no_logs_at_all_is_not_enough_data():
    result = build_trends([], today=TODAY)

    assert result["notEnoughData"] is True
    assert result["basis"] is None
    assert result["trends"] == []

def test_one_log_is_not_enough_data():
    result = build_trends([_log(date(2026, 6, 1), sleep_hours=7)], today=TODAY)

    assert result["notEnoughData"] is True

def test_two_windows_with_nothing_recorded_in_them_is_not_enough_data():
    logs = (
        _period_days(date(2026, 5, 1))
        + _period_days(date(2026, 5, 29))
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert result["notEnoughData"] is True
    assert result["trends"] == []

    assert result["basis"] == BASIS_CYCLE
    assert result["comparedWindows"] is not None

def test_a_user_who_never_logs_flow_still_gets_a_correctly_labelled_answer():
    logs = [
        _log(date(2026, 6, 20) + timedelta(days=offset), sleep_hours=6 + (offset % 3))
        for offset in range(8)
    ]

    result = build_trends(logs, today=TODAY)

    assert result["notEnoughData"] is False
    assert result["basis"] == BASIS_RECENT_LOGS
    assert result["comparedWindows"]["previous"]["loggedDays"] == 4
    assert result["comparedWindows"]["current"]["loggedDays"] == 4

def test_logs_are_re_sorted_rather_than_trusted():
    ascending = (
        _period_days(date(2026, 5, 1), sleep_hours=5)
        + _period_days(date(2026, 5, 29), sleep_hours=8)
        + _period_days(date(2026, 6, 26))
    )

    forwards = build_trends(ascending, today=TODAY)
    backwards = build_trends(list(reversed(ascending)), today=TODAY)

    assert forwards["trends"] == backwards["trends"]
    assert _statement(forwards, "sleep")["direction"] == DIRECTION_INCREASED

def test_a_duplicated_day_is_not_counted_twice():
    logs = _period_days(date(2026, 6, 20), length=4, sleep_hours=6)
    logs.append(_log(date(2026, 6, 20), flow_intensity="medium", sleep_hours=6))

    records = to_day_records(logs)

    assert len(records) == 4
    assert len({record.day for record in records}) == 4

def test_documents_without_a_start_date_are_skipped_not_crashed_on():
    logs = [
        {"sleep_hours": 7},
        _log(date(2026, 6, 28), sleep_hours=8),
        _log(date(2026, 6, 29), sleep_hours=6),
    ]

    result = build_trends(logs, today=TODAY)

    assert result["notEnoughData"] is False

def test_non_numeric_values_are_ignored_rather_than_averaged():
    logs = [
        _log(date(2026, 6, 27), sleep_hours="eight"),
        _log(date(2026, 6, 28), sleep_hours=8),
        _log(date(2026, 6, 29), sleep_hours=6),
        _log(date(2026, 6, 30), sleep_hours=6),
    ]

    result = build_trends(logs, today=TODAY)

    assert result["notEnoughData"] is False

def test_recent_log_windows_needs_at_least_two_records():
    assert recent_log_windows(to_day_records([_log(date(2026, 6, 1))])) == []
