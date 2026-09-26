"""Turn orchestrator: calls ai's stateless /ai/decide, then decides — in code,
never in the model — whether a tool call is actually safe to dispatch.

Resolved eagerly (not inside the SSE generator) so `AiRateLimitedError` can
still become a real HTTP 429 before any stream opens — see chat_routes.py.
"""

from dataclasses import dataclass

from pydantic import ValidationError

from shared.ai_client import AiClient, ChatTurn, Reply
from app.schemas.tools import TOOL_PARAM_MODELS
from app.services.tool_registry import ToolRegistry


@dataclass
class TurnResult:
    reply: str
    tool_name: str | None = None
    tool_params: dict | None = None
    tool_result: str | None = None
    created_resource_id: str | None = None


def _clarify_message(exc: ValidationError) -> str:
    missing = [".".join(str(p) for p in err["loc"]) for err in exc.errors()]
    return f"I need a bit more information: {', '.join(missing)}."


async def run_turn(
    *,
    message: str,
    history: list[ChatTurn],
    context_id: str | None,
    page: str | None,
    token: str,
    ai_client: AiClient,
    registry: ToolRegistry,
) -> TurnResult:
    tools = registry.list_tools(page)
    decision = await ai_client.decide(
        message=message,
        history=history,
        tools=tools,
        domain_context=None,
        user_token=token,
    )

    if isinstance(decision, Reply):
        return TurnResult(reply=decision.text)

    name = decision.name

    if name in registry.targeted_tools and context_id is None:
        return TurnResult(
            reply=f"{registry.no_active_resource_message} Want me to create one first?"
        )

    param_model = TOOL_PARAM_MODELS.get(name)
    if param_model is None:
        return TurnResult(reply="I tried to do something I don't know how to do just yet.")

    try:
        validated = param_model(**decision.params)
    except ValidationError as exc:
        return TurnResult(reply=_clarify_message(exc))

    params = validated.model_dump(mode="json", exclude_none=True)
    if name in registry.targeted_tools:
        params[registry.resource_id_param] = context_id

    result = await registry.call_tool(name, params, token=token)

    return TurnResult(
        reply=result.message,
        tool_name=name,
        tool_params=params,
        tool_result=result.message,
        created_resource_id=result.created_resource_id if name in registry.creating_tools else None,
    )
