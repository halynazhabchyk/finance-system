"""SAGA "create expense" coordinated by Budget Service (choreography).

Local transactions:
    T1  Budget Service  expense PENDING + saga STARTED + outbox ExpenseCreated
    T2  Report Service  read model + inbox, then replies ExpenseProcessed
    C   Budget Service  saga COMPLETED, expense CONFIRMED          (lifecycle.py)
    CT1 Budget Service  expense CANCELLED + saga CANCELLED
                        + outbox ExpenseCancelled                  (compensation.py)
    CT2 Report Service  applies the newer ExpenseCancelled snapshot
"""

from app.services.saga.compensation import CompensationHandler, cancel_expense
from app.services.saga.lifecycle import SagaService, saga_service, saga_timeout_seconds, utcnow

__all__ = [
    "CompensationHandler",
    "SagaService",
    "cancel_expense",
    "saga_service",
    "saga_timeout_seconds",
    "utcnow",
]
