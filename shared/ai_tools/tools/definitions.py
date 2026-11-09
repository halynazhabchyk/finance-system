"""``ToolDefinition`` – one tool as the model sees it and as the executor runs it."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from shared.ai_tools.gateway.client import FinanceApiClient
from shared.ai_tools.llm.client import ToolSpec
from shared.ai_tools.tools.schemas import ToolArguments

ToolHandler = Callable[[FinanceApiClient, Any], Awaitable[dict[str, Any]]]

# JSON Schema keywords that every function-calling provider understands.
_SUPPORTED_KEYWORDS = {
    "type",
    "description",
    "properties",
    "required",
    "format",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "enum",
    "items",
}


@dataclass(frozen=True)
class ToolDefinition:
    """Name, description for the model (when to call), argument schema, endpoint and handler."""

    name: str
    description: str
    args_model: type[ToolArguments]
    endpoint: str
    handler: ToolHandler

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=llm_parameters_schema(self.args_model),
        )


def llm_parameters_schema(model: type[ToolArguments]) -> dict[str, Any]:
    """Simplified JSON schema of ``model`` for the LLM.

    Pydantic remains the source of truth and validates every call; the model
    only needs types, formats, ranges and descriptions.
    """
    schema = model.model_json_schema()
    properties = {
        name: _simplify(prop)
        for name, prop in schema.get("properties", {}).items()
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(schema.get("required", [])),
    }


def _simplify(prop: dict[str, Any]) -> dict[str, Any]:
    variants = prop.get("anyOf")
    if variants:
        non_null = [variant for variant in variants if variant.get("type") != "null"]
        numeric = [variant for variant in non_null if variant.get("type") == "number"]
        # Decimal is rendered as number|string (constraints live in the number variant);
        # optional fields as X|null.
        base = dict(numeric[0]) if numeric else dict(non_null[0])
        merged = {**base, **{key: value for key, value in prop.items() if key != "anyOf"}}
        return _simplify(merged)
    simplified = {key: value for key, value in prop.items() if key in _SUPPORTED_KEYWORDS}
    if "exclusiveMinimum" in prop and simplified.get("type") == "number":
        simplified["description"] = f"{simplified.get('description', '')} Must be greater than {prop['exclusiveMinimum']}.".strip()
    return simplified
