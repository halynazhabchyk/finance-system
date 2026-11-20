"""Event contracts published by Scheduler."""

from __future__ import annotations

from datetime import date
import uuid

from shared.contracts.events import new_event


def build_report_update_event(
    event_type: str,
    period_start: date,
    period_end: date,
) -> dict[str, str]:
    return new_event(
        event_type,
        {
            "scope": "daily" if event_type == "DailyReportUpdateRequested" else "monthly",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        },
        event_id=str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"finance-report:{event_type}:{period_start.isoformat()}:{period_end.isoformat()}",
            )
        ),
    )
