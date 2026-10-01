import time
from typing import AsyncIterator

from jinja2 import Template
from pydantic_ai import Agent

from app.schemas.ai_schema import LLMBudgetOutput, ParseBudgetResponse
from app.services.audit import write_audit_log
from app.services.prompt_loader import load_prompt
from app.services.provider import ResolvedModel, build_agent
from app.core.logging import get_logger

logger = get_logger(__name__)


async def build_parse_stream(
    *,
    text: str,
    resolved: ResolvedModel,
    customer_id: str,
    user_id: str,
) -> AsyncIterator[str]:
    """Load prompt, run PydanticAI structured-output agent, emit SSE events, write audit log.

    Yields raw SSE lines. Callers wrap this in StreamingResponse.
    On prompt load failure yields a single `event: unavailable` and returns.
    """
    try:
        loaded_prompt = await load_prompt("parse_budget")
        user_message = Template(loaded_prompt.user_template).render(text=text)
        prompt_version = loaded_prompt.version
        system_prompt = loaded_prompt.system_prompt
    except Exception as exc:
        logger.error("prompt_load_failed", error=str(exc))
        yield "event: unavailable\ndata: {}\n\n"
        return

    async for event in _run_parse_agent(
        text=text,
        user_message=user_message,
        system_prompt=system_prompt,
        prompt_version=prompt_version,
        resolved=resolved,
        customer_id=customer_id,
        user_id=user_id,
    ):
        yield event


async def _run_parse_agent(
    *,
    text: str,
    user_message: str,
    system_prompt: str,
    prompt_version: str,
    resolved: ResolvedModel,
    customer_id: str,
    user_id: str,
) -> AsyncIterator[str]:
    start = time.monotonic()
    success = True
    error_message = None
    output_json = None
    input_tokens = 0
    output_tokens = 0

    try:
        yield 'event: progress\ndata: {"status": "Analyzing your description..."}\n\n'

        agent: Agent[None, LLMBudgetOutput] = build_agent(
            resolved.model,
            output_type=LLMBudgetOutput,
            system_prompt=system_prompt,
        )
        result = await agent.run(user_message)

        usage = result.usage
        input_tokens = usage.input_tokens or 0
        output_tokens = usage.output_tokens or 0

        yield 'event: progress\ndata: {"status": "Building budget preview..."}\n\n'

        llm_output: LLMBudgetOutput = result.output
        response = ParseBudgetResponse(
            **llm_output.model_dump(),
            prompt_version=prompt_version,
        )
        output_json = response.model_dump(mode="json")
        yield f"event: done\ndata: {response.model_dump_json()}\n\n"

    except Exception as exc:
        success = False
        error_message = str(exc)
        logger.error(
            "ai_parse_error", error=error_message, customer_id=customer_id, user_id=user_id
        )
        yield "event: error\ndata: unexpected error\n\n"
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        try:
            await write_audit_log(
                customer_id=customer_id,
                user_id=user_id,
                prompt_version=prompt_version,
                input_text=text,
                output_json=output_json,
                provider=resolved.provider_name,
                model=resolved.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                success=success,
                error_message=error_message,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            logger.error(
                "audit_log_write_failed",
                error=str(exc),
                customer_id=customer_id,
                user_id=user_id,
            )
