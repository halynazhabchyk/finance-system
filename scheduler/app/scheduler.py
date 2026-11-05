"""APScheduler jobs for daily and monthly report refresh requests."""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.events import build_report_update_event
from app.publisher import EventPublisher

logger = logging.getLogger(__name__)


class ReportScheduler:
    def __init__(
        self,
        publisher: EventPublisher,
        timezone_name: str,
        daily_time: str,
        monthly_time: str,
    ):
        self._publisher = publisher
        self._published_periods: set[tuple[str, date, date]] = set()
        self._timezone = ZoneInfo(timezone_name)
        self._scheduler = AsyncIOScheduler(timezone=self._timezone)
        daily_hour, daily_minute = self._parse_time(daily_time)
        monthly_hour, monthly_minute = self._parse_time(monthly_time)
        self._scheduler.add_job(
            self._publish_daily,
            CronTrigger(
                hour=daily_hour,
                minute=daily_minute,
                timezone=self._timezone,
            ),
            id="daily-report-update",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        self._scheduler.add_job(
            self._publish_monthly,
            CronTrigger(
                day="last",
                hour=monthly_hour,
                minute=monthly_minute,
                timezone=self._timezone,
            ),
            id="monthly-report-update",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )

    def start(self) -> None:
        self._scheduler.start()

    async def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=True)

    async def _publish_daily(self) -> None:
        today = datetime.now(self._timezone).date()
        await self._publish(
            "DailyReportUpdateRequested",
            today.replace(day=1),
            today,
        )

    async def _publish_monthly(self) -> None:
        today = datetime.now(self._timezone).date()
        await self._publish(
            "MonthlyReportUpdateRequested",
            today.replace(day=1),
            today,
        )

    async def _publish(
        self,
        event_type: str,
        period_start: date,
        period_end: date,
    ) -> None:
        period_key = (event_type, period_start, period_end)
        if period_key in self._published_periods:
            logger.info(
                "Skipping duplicate %s event for %s..%s.",
                event_type,
                period_start,
                period_end,
            )
            return
        event = build_report_update_event(
            event_type,
            period_start,
            period_end,
        )
        try:
            await self._publisher.publish(event)
            self._published_periods.add(period_key)
            logger.info("Published %s event %s.", event_type, event["event_id"])
        except Exception:
            logger.exception("Could not publish %s event.", event_type)

    @staticmethod
    def _parse_time(value: str) -> tuple[int, int]:
        try:
            hour, minute = (int(part) for part in value.split(":", 1))
            if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                raise ValueError
            return hour, minute
        except (TypeError, ValueError) as error:
            raise RuntimeError("Scheduler time must use HH:MM format.") from error
