"""Client side of A2A: discover a remote agent and run one of its skills."""

from shared.ai_tools.a2a.client.remote_agent import RemoteAgentClient
from shared.ai_tools.a2a.client.result import RemoteAgentError, RemoteTaskResult

__all__ = ["RemoteAgentClient", "RemoteAgentError", "RemoteTaskResult"]
