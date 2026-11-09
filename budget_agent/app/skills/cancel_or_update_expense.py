"""Skill ``cancel_or_update_expense``: change or delete an expense only after explicit confirmation.

Deterministic, no LLM (decision Р1). Budget Service allows this only for
CONFIRMED expenses (ЛР №3), otherwise it answers 409 and the task FAILS.
"""

from __future__ import annotations

from shared.ai_tools.a2a.server import SkillContext
from shared.ai_tools.tools import projections

from app.skills.schemas import ChangeExpenseArgs


async def cancel_or_update_expense(ctx: SkillContext) -> None:
    if not ctx.request.is_structured:
        await ctx.reject("cancel_or_update_expense accepts structured data only (no language model is used).")
        return
    args = ChangeExpenseArgs.model_validate(ctx.request.arguments)
    description = (
        f"delete expense {args.expense_id}"
        if args.action == "delete"
        else f"change expense {args.expense_id}: {args.changes.to_payload()}"
    )
    if not args.confirm:
        await ctx.require_input(
            f"Confirmation required to {description}. Send the same arguments with \"confirm\": true."
        )
        return

    if args.action == "delete":
        await ctx.api.delete_expense(args.budget_id, args.expense_id)
        await ctx.artifact("expense", {"expense_id": str(args.expense_id), "status": "deleted"})
        await ctx.complete(f"Expense {args.expense_id} deleted (event ExpenseDeleted).")
        return

    expense = await ctx.api.update_expense(args.budget_id, args.expense_id, args.changes.to_payload())
    await ctx.artifact(
        "expense",
        {
            "expense_id": expense["expense_id"],
            "amount": projections.money(expense["amount"], expense["currency"]),
            "occurred_at": expense["occurred_at"],
            "saga_status": expense["saga_status"],
            "status": "updated",
        },
    )
    await ctx.complete(f"Expense {args.expense_id} changed (event ExpenseUpdated).")
