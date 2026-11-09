"""Business helpers shared by budget, category, expense and saga use cases."""

from __future__ import annotations

import calendar
import uuid
from datetime import date

from sqlalchemy.orm import Session

from shared.errors import BusinessRuleError, NotFoundError
from app.integrations.events import build_budget_snapshot_event
from app.integrations.outbox import add_outbox_event
from app.models import Budget
from app.repositories import budgets as repository


def budget_or_404(
    db: Session,
    budget_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> Budget:
    """Return the user's own budget; another user's budget looks like a missing one."""
    budget = repository.get_budget(db, budget_id, for_update=for_update)
    if budget is None or budget.user_id != user_id:
        raise NotFoundError("Budget was not found.")
    return budget


def validate_period(period_start: date, period_end: date) -> None:
    """A budget always covers exactly one calendar month."""
    last_day = calendar.monthrange(period_start.year, period_start.month)[1]
    if (
        period_start.day != 1
        or period_end.year != period_start.year
        or period_end.month != period_start.month
        or period_end.day != last_day
    ):
        raise BusinessRuleError("A budget period must cover one complete calendar month.")


def record_budget_change(
    db: Session,
    budget: Budget,
    event_type: str,
    *,
    bump_version: bool = True,
    **event_fields,
) -> None:
    """Stage the snapshot event for a change made in the caller's transaction.

    The aggregate version grows with every change, so Report Service can
    ignore snapshots that arrive out of order.
    """
    if bump_version:
        budget.aggregate_version += 1
    db.flush()
    add_outbox_event(db, build_budget_snapshot_event(db, budget, event_type, **event_fields))
