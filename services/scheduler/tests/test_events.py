"""Report update events: shared format and a stable event_id per period."""

from datetime import date

from app.integrations.events import build_report_update_event


def test_daily_event_has_shared_format_and_period():
    event = build_report_update_event("DailyReportUpdateRequested", date(2026, 11, 1), date(2026, 11, 20))

    assert event["event_type"] == "DailyReportUpdateRequested"
    assert event["scope"] == "daily"
    assert event["period_start"] == "2026-11-01"
    assert event["period_end"] == "2026-11-20"
    assert event["event_id"]


def test_monthly_event_scope():
    event = build_report_update_event("MonthlyReportUpdateRequested", date(2026, 11, 1), date(2026, 11, 30))

    assert event["scope"] == "monthly"


def test_event_id_is_the_same_for_the_same_period():
    """Consumers deduplicate by event_id, so a repeated publication must reuse it."""
    first = build_report_update_event("DailyReportUpdateRequested", date(2026, 11, 1), date(2026, 11, 20))
    again = build_report_update_event("DailyReportUpdateRequested", date(2026, 11, 1), date(2026, 11, 20))
    other_day = build_report_update_event("DailyReportUpdateRequested", date(2026, 11, 1), date(2026, 11, 21))

    assert first["event_id"] == again["event_id"]
    assert first["event_id"] != other_day["event_id"]
