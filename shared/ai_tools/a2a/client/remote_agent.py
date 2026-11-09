"""Client side of A2A: discover a remote agent and run one of its skills.

The remote agent is reached through the gateway (``GATEWAY_URL/agents/<name>``).
Its Agent Card advertises the public URL (``http://localhost:8080/...``), which
does not resolve inside the Docker network, so requests are sent to the base
URL the card was fetched from. The card is still validated: the skill must be
declared and the agent must accept HTTP Bearer (JWT) authentication.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.client.errors import A2AClientError, AgentCardResolutionError
from a2a.helpers.proto_helpers import get_data_parts, get_text_parts, new_data_part, new_text_part
from a2a.types import AgentCard, Message, Role, SendMessageRequest, TaskState

from shared.ai_tools.a2a.card import BEARER_SCHEME
from shared.ai_tools.a2a.client.result import RemoteAgentError, RemoteTaskResult, StateListener
from shared.ai_tools.a2a.requests import normalize_numbers

logger = logging.getLogger(__name__)


class RemoteAgentClient:
    def __init__(
        self,
        *,
        base_url: str,
        access_token: str,
        timeout_seconds: float = 90.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )
        self.card: AgentCard | None = None

    async def __aenter__(self) -> RemoteAgentClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._http.aclose()

    async def discover(self, required_skill: str) -> AgentCard:
        try:
            card = await A2ACardResolver(self._http, self._base_url).get_agent_card()
        except AgentCardResolutionError as error:
            raise RemoteAgentError(f"Agent Card at {self._base_url} is not available.") from error
        skills = [skill.id for skill in card.skills]
        if required_skill not in skills:
            raise RemoteAgentError(f"Agent '{card.name}' has no skill '{required_skill}'.")
        if BEARER_SCHEME not in card.security_schemes:
            raise RemoteAgentError(f"Agent '{card.name}' does not declare JWT (Bearer) authentication.")
        advertised = card.supported_interfaces[0].url if card.supported_interfaces else ""
        card.supported_interfaces[0].url = self._base_url + "/"
        logger.info(
            "a2a_agent_card_resolved name=%s version=%s advertised_url=%s used_url=%s skills=%s",
            card.name,
            card.version,
            advertised,
            self._base_url,
            ",".join(skills),
        )
        self.card = card
        return card

    async def run_skill(
        self,
        skill_id: str,
        arguments: dict[str, Any],
        *,
        on_state: StateListener | None = None,
    ) -> RemoteTaskResult:
        """Structured request: data part ``{"skill_id", "arguments"}``."""
        if self.card is None:
            await self.discover(skill_id)
        return await self._send([new_data_part({"skill_id": skill_id, "arguments": arguments})], on_state)

    async def run_text(self, text: str, *, on_state: StateListener | None = None) -> RemoteTaskResult:
        """Free-text request, handled by the remote agent's default text skill. Call ``discover`` first."""
        if self.card is None:
            raise RemoteAgentError("discover() must be called before run_text().")
        return await self._send([new_text_part(text)], on_state)

    async def _send(self, parts: list[Any], on_state: StateListener | None) -> RemoteTaskResult:
        client = ClientFactory(ClientConfig(httpx_client=self._http, streaming=True)).create(self.card)
        message = Message(message_id=str(uuid.uuid4()), role=Role.ROLE_USER, parts=parts)
        result = RemoteTaskResult()
        try:
            async for event in client.send_message(SendMessageRequest(message=message)):
                await self._apply(event, result, on_state)
        except A2AClientError as error:
            raise RemoteAgentError(f"A2A call to '{self.card.name}' failed: {error}") from error
        return result

    async def _apply(self, event: Any, result: RemoteTaskResult, on_state: StateListener | None) -> None:
        kind = event.WhichOneof("payload")
        if kind == "task":
            result.task_id = event.task.id
            await self._state(result, event.task.status, on_state)
            for artifact in event.task.artifacts:
                self._artifact(result, artifact)
        elif kind == "status_update":
            result.task_id = event.status_update.task_id
            await self._state(result, event.status_update.status, on_state)
        elif kind == "artifact_update":
            self._artifact(result, event.artifact_update.artifact)

    async def _state(self, result: RemoteTaskResult, status: Any, on_state: StateListener | None) -> None:
        state = TaskState.Name(status.state).removeprefix("TASK_STATE_")
        text = "\n".join(get_text_parts(status.message.parts)) if status.HasField("message") else ""
        if result.states and result.states[-1] == state and not text:
            return
        result.state, result.message = state, text or result.message
        result.states.append(state)
        logger.info("a2a_remote_task task_id=%s state=%s detail=%s", result.task_id, state, text[:160].replace("\n", " "))
        if on_state is not None:
            await on_state(state, text)

    @staticmethod
    def _artifact(result: RemoteTaskResult, artifact: Any) -> None:
        for data in get_data_parts(artifact.parts):
            if isinstance(data, dict):
                result.artifacts[artifact.name or artifact.artifact_id] = normalize_numbers(data)
