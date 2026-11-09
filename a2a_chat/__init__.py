"""Interactive console client of the A2A agents (demonstration).

The user talks to budget-agent (producer) or report-agent (consumer) in natural
language. The client logs in through User Service, discovers the agent by its
Agent Card and sends text messages over A2A through the gateway; task states
are printed as they arrive (streaming). A2A itself is the shared
``RemoteAgentClient`` – the same client report-agent uses to call budget-agent.

Run from the project root:  .\\.venv\\Scripts\\python.exe -m a2a_chat
"""
