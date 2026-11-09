"""Agent Card construction: identity, interface, modes, JWT security, skills."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    HTTPAuthSecurityScheme,
    SecurityRequirement,
    SecurityScheme,
    StringList,
)
from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, TransportProtocol

JSON_MODE = "application/json"
TEXT_MODE = "text/plain"
BEARER_SCHEME = "bearerAuth"


@dataclass(frozen=True)
class SkillDescription:
    id: str
    name: str
    description: str
    tags: Sequence[str]
    examples: Sequence[str] = field(default_factory=tuple)
    input_modes: Sequence[str] = (JSON_MODE, TEXT_MODE)
    output_modes: Sequence[str] = (JSON_MODE, TEXT_MODE)

    def to_proto(self) -> AgentSkill:
        return AgentSkill(
            id=self.id,
            name=self.name,
            description=self.description,
            tags=list(self.tags),
            examples=list(self.examples),
            input_modes=list(self.input_modes),
            output_modes=list(self.output_modes),
        )


def build_agent_card(
    *,
    name: str,
    description: str,
    version: str,
    public_url: str,
    skills: Sequence[SkillDescription],
) -> AgentCard:
    """Agent Card with JSON-RPC interface, streaming and HTTP Bearer (JWT of User Service)."""
    return AgentCard(
        name=name,
        description=description,
        version=version,
        provider=AgentProvider(organization="Finance System", url=public_url),
        supported_interfaces=[
            AgentInterface(
                url=public_url,
                protocol_binding=TransportProtocol.JSONRPC.value,
                protocol_version=PROTOCOL_VERSION_CURRENT,
            )
        ],
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        security_schemes={
            BEARER_SCHEME: SecurityScheme(
                http_auth_security_scheme=HTTPAuthSecurityScheme(
                    scheme="bearer",
                    bearer_format="JWT",
                    description="Access token of User Service (POST /api/users/auth/login).",
                )
            )
        },
        security_requirements=[SecurityRequirement(schemes={BEARER_SCHEME: StringList(list=[])})],
        default_input_modes=[JSON_MODE, TEXT_MODE],
        default_output_modes=[JSON_MODE, TEXT_MODE],
        skills=[skill.to_proto() for skill in skills],
    )
