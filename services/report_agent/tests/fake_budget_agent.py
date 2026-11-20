"""An in-process budget-agent for report-agent tests."""

from __future__ import annotations

from ai_tools.a2a.card import SkillDescription, build_agent_card
from ai_tools.a2a.server import SkillContext, SkillExecutor, SkillFailed, create_agent_app
from ai_tools.config import AgentLimits
from ai_tools.gateway import FinanceApiClient
from ai_tools.testing import FakeFinanceApi
from shared.service_discovery.consul import ServiceConfig

CARD = build_agent_card(
    name="budget-agent",
    description="test double",
    version="1.0.0",
    public_url="http://localhost:8080/agents/budget/",
    skills=[SkillDescription(id="register_expense", name="Register", description="d", tags=["expense"])],
)


def create_fake_budget_agent(api: FakeFinanceApi, *, received_tokens: list[str] | None = None):
    def client(token: str) -> FinanceApiClient:
        if received_tokens is not None:
            received_tokens.append(token)
        return FinanceApiClient(base_url="http://gateway.test", access_token=token, transport=api.transport())

    async def register_expense(ctx: SkillContext) -> None:
        args = ctx.request.arguments
        expense = await ctx.api.create_expense(args["budget_id"], {k: v for k, v in args.items() if k != "budget_id"})
        await ctx.working(f"Expense {expense['expense_id']} PENDING, waiting for the SAGA.")
        saga = {"status": "STARTED"}
        while saga["status"] == "STARTED":
            saga = await ctx.api._request("GET", f"/api/budgets/{args['budget_id']}/expenses/{expense['expense_id']}/saga")
        if saga["status"] == "COMPLETED":
            await ctx.artifact("expense", {"expense_id": expense["expense_id"], "saga_status": "CONFIRMED", "saga_id": saga["saga_id"]})
            await ctx.complete("Expense CONFIRMED.")
            return
        raise SkillFailed(
            f"SAGA cancelled the expense (reason: {saga['failure_reason']}).",
            {"saga_status": "CANCELLED", "failure_reason": saga["failure_reason"]},
        )

    async def verify(token: str) -> None:
        async with client(token) as api_client:
            await api_client.verify_current_user()

    return create_agent_app(
        card=CARD,
        executor=SkillExecutor(
            agent_name="budget-agent",
            skills={"register_expense": register_expense},
            api_client_factory=client,
            limits=AgentLimits(),
        ),
        verifier=verify,
        service_config=ServiceConfig.from_env("budget-agent", 8041),
    )
