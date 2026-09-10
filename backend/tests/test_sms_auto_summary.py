from datetime import date, timedelta
import pytest

from api.sms import generate_cycle_sms_summary

def test_generate_cycle_sms_summary_formatting():

    summary = generate_cycle_sms_summary("test_mock_user_id")
    assert isinstance(summary, str)
    assert len(summary) <= 160
    assert summary.startswith("Rhythma")
    assert "Log your last period" in summary

def test_generate_cycle_sms_summary_invents_no_countdown_without_data():

    summary = generate_cycle_sms_summary("test_mock_user_id")
    assert "~" not in summary
    assert "Next period expected" not in summary

def test_generate_cycle_sms_summary_includes_disclaimer():

    summary = generate_cycle_sms_summary("test_mock_user_id")
    assert len(summary) <= 160
    assert "Estimate only, not medical/contraceptive advice." in summary

def test_generate_cycle_sms_summary_never_truncates_disclaimer():

    summary = generate_cycle_sms_summary("test_mock_user_id")
    if "Estimate only" in summary:
        assert summary.rstrip().endswith("medical/contraceptive advice.")
