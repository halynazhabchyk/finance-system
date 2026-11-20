"""ReportScheduler: job periods, duplicate suppression, time format."""

import asyncio
from datetime import date

import pytest

from app.workers.report_scheduler import ReportScheduler


class RecordingPublisher:
    def __init__(self, fail: bool = False):
        self.events: list[dict] = []
        self.fail = fail

    async def publish(self, event: dict) -> None:
        if self.fail:
            raise RuntimeError("broker down")
        self.events.append(event)


def scheduler(publisher, daily="23:00", monthly="23:30"):
    return ReportScheduler(publisher, "Europe/Kyiv", daily, monthly)


def test_daily_job_publishes_month_to_date_period():
    publisher = RecordingPublisher()

    asyncio.run(scheduler(publisher)._publish_daily())

    event = publisher.events[0]
    assert event["event_type"] == "DailyReportUpdateRequested"
    assert event["period_start"].endswith("-01")
    assert event["period_start"][:7] == event["period_end"][:7]


def test_monthly_job_publishes_monthly_event():
    publisher = RecordingPublisher()

    asyncio.run(scheduler(publisher)._publish_monthly())

    assert publisher.events[0]["event_type"] == "MonthlyReportUpdateRequested"


def test_same_period_is_published_once():
    publisher = RecordingPublisher()
    jobs = scheduler(publisher)

    async def twice():
        await jobs._publish("DailyReportUpdateRequested", date(2026, 11, 1), date(2026, 11, 20))
        await jobs._publish("DailyReportUpdateRequested", date(2026, 11, 1), date(2026, 11, 20))

    asyncio.run(twice())

    assert len(publisher.events) == 1


def test_failed_publication_is_retried_next_time():
    """A period is remembered only after a successful publication."""
    publisher = RecordingPublisher(fail=True)
    jobs = scheduler(publisher)
    period = ("DailyReportUpdateRequested", date(2026, 11, 1), date(2026, 11, 20))

    asyncio.run(jobs._publish(*period))
    publisher.fail = False
    asyncio.run(jobs._publish(*period))

    assert len(publisher.events) == 1


@pytest.mark.parametrize("value", ["24:00", "12:60", "noon", "12", ""])
def test_invalid_time_is_rejected(value):
    with pytest.raises(RuntimeError, match="HH:MM"):
        scheduler(RecordingPublisher(), daily=value)
