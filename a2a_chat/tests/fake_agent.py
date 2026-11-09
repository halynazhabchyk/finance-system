"""A real A2A server for the client tests, built from the shared server components.

Its text skill replaces the language model with a simple rule: without a month
in the text it asks for one (INPUT_REQUIRED); otherwise it reports progress and
completes with an ``expense`` artifact, like budget-agent does after the SAGA.
"""

from __future__ import annotations

from shared.ai_tools.a2a.card import SkillDescription, build_agent_card
from shared.ai_tools.a2a.server import SkillContext, SkillExecutor, create_agent_app
from shared.ai_tools.config import AgentLimits, GatewaySettings
from shared.ai_tools.gateway.client import AuthenticationFailed
from shared.ai_tools.gateway.factory import gateway_client_factory
from shared.service_discovery.consul import ServiceConfig

CARD = build_agent_card(
    name="budget-agent",
    description="test agent",
    version="1.0.0",
    public_url="http://localhost:8080/agents/budget/",
    skills=[SkillDescription(id="register_expense", name="Register an expense", description="d", tags=["expense"])],
)


def create_text_agent(received_texts: list[str], *, valid_token: str):
    async def register_expense(ctx: SkillContext) -> None:
        received_texts.append(ctx.request.text)
        if "листопад" not in ctx.request.text.lower():
            await ctx.require_input("За який місяць додати витрату?")
            return
        await ctx.working("Expense accepted with saga_status PENDING; waiting for the SAGA.")
        await ctx.artifact("expense", {"amount": "250.00 UAH", "saga_status": "CONFIRMED"})
        await ctx.complete("Expense is CONFIRMED.")

    async def verify(token: str) -> None:
        if token != valid_token:
            raise AuthenticationFailed("invalid token")

    return create_agent_app(
        card=CARD,
        executor=SkillExecutor(
            agent_name="budget-agent",
            skills={"register_expense": register_expense},
            api_client_factory=gateway_client_factory(GatewaySettings(base_url="http://unused.test")),
            limits=AgentLimits(),
            default_text_skill="register_expense",
        ),
        verifier=verify,
        service_config=ServiceConfig.from_env("budget-agent", 8041),
    )
