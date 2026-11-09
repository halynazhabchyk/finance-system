"""Client-side infrastructure shared by the AI components (ЛР №4).

The package gives ``ai-assistant``, ``mcp-server``, ``budget-agent`` and
``report-agent`` one implementation of:

* ``config``     – settings read from environment variables;
* ``llm``        – the provider-neutral ``LLMClient`` and the Gemini adapter;
* ``gateway``    – the typed REST client of the public API behind Traefik;
* ``tools``      – the five whitelisted tools, their argument schemas and executor;
* ``guardrails`` – token limits, prompt-injection filter, data marking;
* ``agent``      – the function-calling loop.

It contains no business rules of User/Budget/Report Service: all amounts,
balances and limit checks are computed by those services.
"""
