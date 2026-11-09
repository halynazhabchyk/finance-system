"""Server side of A2A: an agent that accepts tasks (Agent Card, JSON-RPC, skills, JWT check)."""

from shared.ai_tools.a2a.server.app import create_agent_app
from shared.ai_tools.a2a.server.context import SkillContext, SkillHandler
from shared.ai_tools.a2a.server.errors import SkillFailed
from shared.ai_tools.a2a.server.executor import SkillExecutor

__all__ = ["SkillContext", "SkillExecutor", "SkillFailed", "SkillHandler", "create_agent_app"]
