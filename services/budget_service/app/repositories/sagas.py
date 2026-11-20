"""Data access for SAGA instances (no business rules here)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import SagaInstance
from app.models.saga_instance import SAGA_COMPENSATING, SAGA_STARTED


def add_saga(db: Session, saga: SagaInstance) -> SagaInstance:
    db.add(saga)
    return saga


def get_saga(
    db: Session,
    saga_id: uuid.UUID,
    *,
    for_update: bool = False,
    skip_locked: bool = False,
) -> SagaInstance | None:
    statement = select(SagaInstance).where(SagaInstance.saga_id == saga_id)
    if for_update:
        statement = statement.with_for_update(skip_locked=skip_locked)
    return db.scalar(statement)


def get_saga_for_aggregate(
    db: Session,
    saga_type: str,
    aggregate_id: uuid.UUID,
) -> SagaInstance | None:
    return db.scalar(
        select(SagaInstance).where(
            SagaInstance.saga_type == saga_type,
            SagaInstance.aggregate_id == aggregate_id,
        )
    )


def find_sagas_needing_compensation(
    db: Session,
    now: datetime,
    limit: int,
) -> list[uuid.UUID]:
    """STARTED sagas past their deadline and unfinished compensations (6.8)."""
    return list(
        db.scalars(
            select(SagaInstance.saga_id)
            .where(
                or_(
                    and_(
                        SagaInstance.status == SAGA_STARTED,
                        SagaInstance.deadline_at < now,
                    ),
                    SagaInstance.status == SAGA_COMPENSATING,
                )
            )
            .order_by(SagaInstance.deadline_at)
            .limit(limit)
        ).all()
    )
