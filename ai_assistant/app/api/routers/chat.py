"""``POST /api/assistant/chat`` – one question to the assistant."""

from fastapi import APIRouter

from app.api.dependencies import AccessToken, ChatServiceDependency
from app.schemas.chat import ChatRequest, ChatResponse, TokenUsageInfo, ToolCallInfo

router = APIRouter(prefix="/internal/assistant", tags=["assistant"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"description": "Rejected by a guardrail (e.g. prompt injection)."},
        401: {"description": "Missing, invalid or expired JWT."},
        403: {"description": "The account is blocked."},
        422: {"description": "Empty or too long message."},
        503: {"description": "Language model or finance services unavailable."},
    },
)
async def chat(payload: ChatRequest, access_token: AccessToken, service: ChatServiceDependency) -> ChatResponse:
    result = await service.chat(payload.message, access_token)
    return ChatResponse(
        request_id=result.request_id,
        answer=result.answer,
        tool_calls=[
            ToolCallInfo(
                name=execution.name,
                arguments=execution.arguments,
                status=execution.status,
                duration_ms=execution.duration_ms,
            )
            for execution in result.tool_calls
        ],
        usage=TokenUsageInfo(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
        ),
        stopped_reason=result.stopped_reason,
    )
