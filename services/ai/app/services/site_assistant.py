"""Grounded site-assistant pipeline: retrieve → generate → resolve citations, failing closed."""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from jinja2 import Template
from opentelemetry import trace
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.instrumented import InstrumentationSettings
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.services.prompt_loader import LoadedPrompt, load_prompt
from app.services.provider import ResolvedModel, build_agent
from app.services.rate_limiter import DailyCapReached
from app.services.redacted_tracing import RedactedSpan, RedactingTracer
from app.services.site_retrieval import Persona, RetrievedChunk, retrieve

logger = get_logger(__name__)

PROMPT_NAME = "site_assistant"
FALLBACK_ANSWER = (
    "I couldn't find an answer to that on this website. Try browsing the pages below instead."
)
_MAX_OUTPUT_TOKENS = 600
# Bare domains match any alphabetic TLD; a false positive only costs the fallback answer.
_LINK_RE = re.compile(
    r"https?://[^\s<>\"')\]]+|\bwww\.[^\s<>\"')\]]+|\b(?:[\w-]+\.)+[^\W\d_]{2,63}\b",
    re.IGNORECASE,
)


class SiteAssistantUnavailable(Exception):
    """Pipeline failure (retrieval, prompt or render); routes map it to 503."""


class SiteAnswer(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    answer: str
    cited_chunk_ids: list[str]
    answerable: bool


class Citation(BaseModel):
    content_id: str
    url: str
    title: str


class AskResponse(BaseModel):
    answer: str
    answerable: bool
    citations: list[Citation]


@dataclass
class _Prepared:
    prompt: LoadedPrompt
    model: Model
    tracer_provider: trace.TracerProvider
    template: Template
    agent: Agent[None, SiteAnswer]


_prepared: _Prepared | None = None


def _unanswerable() -> AskResponse:
    return AskResponse(answer=FALLBACK_ANSWER, answerable=False, citations=[])


def _unavailable(stage: str, exc: Exception) -> SiteAssistantUnavailable:
    # Type only: DB and template errors can echo the question or prompt text.
    logger.error("site_assistant_unavailable", stage=stage, error_type=type(exc).__name__)
    return SiteAssistantUnavailable(stage)


def _tracer_provider() -> trace.TracerProvider:
    return trace.get_tracer_provider()


def _prepare(prompt: LoadedPrompt, resolved: ResolvedModel) -> _Prepared:
    """Compiled template and agent, rebuilt only when the prompt, model or tracer changes."""
    global _prepared
    provider = _tracer_provider()
    cached = _prepared
    if (
        cached is not None
        and cached.prompt == prompt
        and cached.model is resolved.model
        and cached.tracer_provider is provider
    ):
        return cached

    instrument = InstrumentationSettings(include_content=False, tracer_provider=provider)
    instrument.tracer = RedactingTracer(instrument.tracer)  # type: ignore[assignment]
    agent = build_agent(
        resolved.model,
        output_type=SiteAnswer,
        system_prompt=prompt.system_prompt,
        model_settings={"max_tokens": _MAX_OUTPUT_TOKENS},
        instrument=instrument,
    )
    _prepared = _Prepared(prompt, resolved.model, provider, Template(prompt.user_template), agent)
    return _prepared


def _citation(chunk: RetrievedChunk) -> Citation:
    title = chunk.page_title
    if chunk.heading and chunk.heading != chunk.page_title:
        title = f"{chunk.page_title}: {chunk.heading}"
    return Citation(content_id=chunk.content_id, url=chunk.url, title=title)


def reaches_model(chunks: list[RetrievedChunk]) -> bool:
    """True when retrieval is strong enough to ask the model; weaker questions short-circuit."""
    return bool(chunks) and chunks[0].score >= settings.SITE_ASSISTANT_MIN_SCORE


def has_unverified_link(text: str) -> bool:
    """True if the text links to any host outside SITE_ASSISTANT_LINK_HOSTS."""
    for match in _LINK_RE.finditer(text):
        link = match.group(0)
        host = urlsplit(link if "://" in link else f"//{link}").hostname or ""
        if host.rstrip(".").lower() not in settings.site_assistant_link_hosts:
            return True
    return False


def resolve_citations(output: SiteAnswer, chunks: list[RetrievedChunk]) -> AskResponse:
    """Keep only retrieved IDs, resolve them server-side, and downgrade when none survive."""
    if not output.answerable or has_unverified_link(output.answer):
        return _unanswerable()
    by_id = {chunk.content_id: chunk for chunk in chunks}
    cited = dict.fromkeys(cid for cid in output.cited_chunk_ids if cid in by_id)
    if not cited or not output.answer.strip():
        return _unanswerable()
    return AskResponse(
        answer=output.answer.strip(),
        answerable=True,
        citations=[_citation(by_id[cid]) for cid in cited],
    )


async def ask(
    db: AsyncSession,
    question: str,
    persona: Persona | None,
    resolved: ResolvedModel,
    before_model_call: Callable[[], Awaitable[None]] | None = None,
) -> AskResponse:
    """Answer one question; raises SiteAssistantUnavailable when the pipeline itself fails.
    `before_model_call` runs only when the model will be called (the global cap hook)."""
    tracer = RedactingTracer(trace.get_tracer(__name__, tracer_provider=_tracer_provider()))
    with tracer.start_as_current_span("site_assistant.ask") as span:
        span.set_attribute("site_assistant.question_length", len(question))
        span.set_attribute("gen_ai.system", resolved.provider_name)
        span.set_attribute("gen_ai.request.model", resolved.model_name)

        try:
            with tracer.start_as_current_span("site_assistant.retrieve"):
                chunks = await retrieve(db, question, settings.SITE_ASSISTANT_TOP_K, persona)
        except Exception as exc:
            raise _unavailable("retrieve", exc) from exc
        span.set_attribute("site_assistant.retrieved_ids", [c.content_id for c in chunks])
        span.set_attribute("site_assistant.retrieved_scores", [c.score for c in chunks])

        capped: DailyCapReached | None = None
        if not reaches_model(chunks):
            response = _unanswerable()
        else:
            try:
                response = await _generate(
                    tracer, span, question, persona, chunks, resolved, before_model_call
                )
            except DailyCapReached as exc:
                # Expected throttling: tag the span, re-raise only after it closes cleanly.
                span.set_attribute("site_assistant.daily_cap_reached", True)
                capped = exc
        if capped is None:
            span.set_attribute("site_assistant.answerable", response.answerable)
            span.set_attribute("site_assistant.citation_count", len(response.citations))
            return response
    raise capped


async def _generate(
    tracer: RedactingTracer,
    span: RedactedSpan,
    question: str,
    persona: Persona | None,
    chunks: list[RetrievedChunk],
    resolved: ResolvedModel,
    before_model_call: Callable[[], Awaitable[None]] | None,
) -> AskResponse:
    try:
        prompt = await load_prompt(PROMPT_NAME)
        prepared = _prepare(prompt, resolved)
        user_message = prepared.template.render(chunks=chunks, persona=persona, question=question)
    except Exception as exc:
        raise _unavailable("prompt", exc) from exc
    span.set_attribute("site_assistant.prompt_version", prompt.version)

    if before_model_call is not None:
        await before_model_call()

    with tracer.start_as_current_span("site_assistant.generate"):
        try:
            result = await prepared.agent.run(user_message)
        except Exception as exc:
            logger.warning("site_assistant_model_failed", error_type=type(exc).__name__)
            return _unanswerable()

    usage = result.usage
    span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens or 0)
    span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens or 0)
    with tracer.start_as_current_span("site_assistant.cite"):
        return resolve_citations(result.output, chunks)
