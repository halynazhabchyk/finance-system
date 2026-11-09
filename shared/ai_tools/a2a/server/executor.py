"""``SkillExecutor`` – an A2A ``AgentExecutor`` that dispatches tasks to skill handlers.

Responsibilities shared by both agents:
* create the task and report every state change (logged with task_id);
* take the caller's JWT from the request and open an API client with it;
* apply guardrails to text parts (length, prompt-injection filter);
* turn expected failures into FAILED / REJECTED states with a clear message.
"""

from __future__ import annotations

import logging

from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from pydantic import ValidationError

from shared.ai_tools.a2a.requests import bearer_token, parse_skill_request
from shared.ai_tools.a2a.server.context import SkillContext, SkillHandler
from shared.ai_tools.a2a.server.errors import SkillFailed
from shared.ai_tools.config import AgentLimits
from shared.ai_tools.gateway import GatewayError
from shared.ai_tools.gateway.factory import ApiClientFactory
from shared.ai_tools.guardrails import (
    GuardrailViolation,
    check_user_message,
    ensure_no_active_content,
    ensure_no_prompt_injection,
)
from shared.ai_tools.llm import LLMError

logger = logging.getLogger(__name__)


class SkillExecutor(AgentExecutor):
    def __init__(
        self,
        *,
        agent_name: str,
        skills: dict[str, SkillHandler],
        api_client_factory: ApiClientFactory,
        limits: AgentLimits,
        default_text_skill: str | None = None,
    ) -> None:
        self._agent_name = agent_name
        self._skills = skills
        self._api_client_factory = api_client_factory
        self._limits = limits
        self._default_text_skill = default_text_skill

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        if context.current_task is None:
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        request = parse_skill_request(context)
        skill_id = request.skill_id or (self._default_text_skill if request.text else None)
        logger.info(
            "a2a_task_received agent=%s task_id=%s skill=%s structured=%s",
            self._agent_name,
            task.id,
            skill_id,
            request.is_structured,
        )

        token = bearer_token(context)
        if token is None:  # normally stopped earlier by BearerAuthMiddleware
            await updater.requires_auth(updater.new_agent_message([new_text_part("A user JWT is required.")]))
            return

        async with self._api_client_factory(token) as api:
            ctx = SkillContext(self._agent_name, task.id, request, token, api, updater)
            await self._run(ctx, skill_id)

    async def _run(self, ctx: SkillContext, skill_id: str | None) -> None:
        try:
            if ctx.request.text:
                check_user_message(ctx.request.text, self._limits.user_message_max_chars)
                ensure_no_prompt_injection(ctx.request.text, source=f"a2a:{self._agent_name}")
                ensure_no_active_content(ctx.request.text, source=f"a2a:{self._agent_name}")
            handler = self._skills.get(skill_id or "")
            if handler is None:
                await ctx.reject(f"Unknown skill '{skill_id}'. Available skills: {', '.join(self._skills)}.")
                return
            await ctx.working(f"Skill {skill_id} started.")
            await handler(ctx)
        except GuardrailViolation as violation:
            await ctx.reject(violation.user_message)
        except ValidationError as error:
            await ctx.reject("Invalid arguments: " + "; ".join(_validation_messages(error)))
        except SkillFailed as failure:
            if failure.data is not None:
                await ctx.artifact("failure", failure.data)
            await ctx.fail(failure.message)
        except GatewayError as error:
            await ctx.fail(error.llm_message)
        except LLMError as error:
            await ctx.fail(f"Language model error: {error}")
        except Exception:  # noqa: BLE001 - the task must end in a terminal state
            logger.exception("a2a_skill_crashed agent=%s task_id=%s skill=%s", self._agent_name, ctx.task_id, skill_id)
            await ctx.fail("Internal error of the agent.")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if task is not None:
            await TaskUpdater(event_queue, task.id, task.context_id).cancel()


def _validation_messages(error: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(part) for part in item['loc']) or 'arguments'}: {item['msg']}"
        for item in error.errors(include_url=False, include_input=False)
    ]
