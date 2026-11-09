"""How an A2A message is interpreted: which skill, which arguments, which text.

Convention of this system: a structured request is a data part
``{"skill_id": "...", "arguments": {...}}``; a free-text request is a text part
(then the agent's default text skill is used). ``skill_id`` may also be put in
the message metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from a2a.helpers.proto_helpers import get_data_parts, get_text_parts
from a2a.server.agent_execution import RequestContext


@dataclass(frozen=True)
class SkillRequest:
    skill_id: str | None
    arguments: dict[str, Any] = field(default_factory=dict)
    text: str = ""

    @property
    def is_structured(self) -> bool:
        return self.skill_id is not None and not self.text


def parse_skill_request(context: RequestContext) -> SkillRequest:
    message = context.message
    if message is None:
        return SkillRequest(skill_id=None)
    skill_id: str | None = None
    arguments: dict[str, Any] = {}
    for data in get_data_parts(message.parts):
        if isinstance(data, dict):
            skill_id = data.get("skill_id", skill_id)
            if isinstance(data.get("arguments"), dict):
                arguments = normalize_numbers(data["arguments"])
    metadata_skill = context.metadata.get("skill_id") if context.metadata else None
    text = "\n".join(part.strip() for part in get_text_parts(message.parts) if part.strip())
    return SkillRequest(skill_id=skill_id or metadata_skill, arguments=arguments, text=text)


def normalize_numbers(value: Any) -> Any:
    """protobuf ``Value`` stores every number as float (2026 -> 2026.0); restore integers."""
    if isinstance(value, dict):
        return {key: normalize_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_numbers(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def bearer_token(context: RequestContext) -> str | None:
    """JWT of the caller from the HTTP ``Authorization`` header of the A2A request."""
    headers = context.call_context.state.get("headers", {}) if context.call_context else {}
    scheme, _, token = str(headers.get("authorization", "")).partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None
