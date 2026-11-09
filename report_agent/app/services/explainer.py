"""Optional natural-language explanation of prepared data by the LLM.

The model receives the data as untrusted content and has no tools here, so it
can only explain; the same token limits apply (``FunctionCallingLoop``).
If no model is configured or it fails, the skill still returns its data.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from shared.ai_tools.agent import FunctionCallingLoop
from shared.ai_tools.config import AgentLimits
from shared.ai_tools.gateway import FinanceApiClient
from shared.ai_tools.guardrails import mark_as_untrusted_data
from shared.ai_tools.llm import LLMClient, LLMError
from shared.ai_tools.tools import ToolExecutor

from app.core.prompts import EXPLAIN_PROMPT

logger = logging.getLogger(__name__)


class Explainer:
    def __init__(self, *, llm_factory: Callable[[], LLMClient | None], limits: AgentLimits) -> None:
        self._llm_factory = llm_factory
        self._limits = limits

    async def explain(self, api: FinanceApiClient, task: str, data: dict[str, Any], *, request_id: str) -> str | None:
        llm = self._llm_factory()
        if llm is None:
            return None
        loop = FunctionCallingLoop(
            llm=llm,
            executor=ToolExecutor(api, tools=()),
            system_prompt=EXPLAIN_PROMPT,
            limits=self._limits,
        )
        message = f"Task: {task}\nData:\n{json.dumps(mark_as_untrusted_data(data), ensure_ascii=False)}"
        try:
            result = await loop.run(message, request_id=request_id)
        except LLMError as error:
            logger.warning("explanation_unavailable request_id=%s error=%s", request_id, type(error).__name__)
            return None
        return result.answer if result.stopped_reason == "completed" else None
