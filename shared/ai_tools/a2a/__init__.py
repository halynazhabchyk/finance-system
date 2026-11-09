"""A2A (Agent-to-Agent) infrastructure shared by ``budget-agent`` and ``report-agent``.

A2A is the channel *between agents*. It never replaces RabbitMQ: domain events
are still published only by Budget Service through its Outbox, and the agents
work exclusively through the public REST API with the user's JWT.
"""
