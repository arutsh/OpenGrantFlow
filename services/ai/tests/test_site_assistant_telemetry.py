"""Spans from the site assistant carry IDs and token counts but never visitor or answer text."""

from unittest.mock import AsyncMock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.services import site_assistant
from app.services.provider import ResolvedModel
from app.services.rate_limiter import DailyCapReached
from tests.test_site_assistant_routes import _chunk, _seeded_prompt

QUESTION = "zebra-question-marker how do I export"
ANSWER = "quokka-answer-marker use the export button"


@pytest.fixture
def exporter(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    with patch.object(site_assistant, "_tracer_provider", return_value=provider):
        yield memory


def _respond(messages, info: AgentInfo) -> ModelResponse:
    args = {"answer": ANSWER, "cited_chunk_ids": ["export"], "answerable": True}
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])


@pytest.mark.anyio
async def test_spans_carry_ids_and_tokens_but_no_text(exporter):
    chunks = [_chunk("export", score=0.6), _chunk("reports", score=0.3)]
    resolved = ResolvedModel(FunctionModel(_respond), "anthropic", "test-model")
    with (
        patch.object(site_assistant, "retrieve", AsyncMock(return_value=chunks)),
        patch.object(site_assistant, "load_prompt", AsyncMock(return_value=_seeded_prompt())),
    ):
        response = await site_assistant.ask(None, QUESTION, "funder", resolved)
    assert response.answer == ANSWER

    spans = exporter.get_finished_spans()
    names = {s.name for s in spans}
    assert {
        "site_assistant.ask",
        "site_assistant.retrieve",
        "site_assistant.generate",
        "site_assistant.cite",
    } <= names

    root = next(s for s in spans if s.name == "site_assistant.ask")
    attrs = dict(root.attributes)
    assert list(attrs["site_assistant.retrieved_ids"]) == ["export", "reports"]
    assert list(attrs["site_assistant.retrieved_scores"]) == [0.6, 0.3]
    assert attrs["site_assistant.prompt_version"] == "v1"
    assert attrs["gen_ai.request.model"] == "test-model"
    assert attrs["site_assistant.answerable"] is True
    assert attrs["site_assistant.citation_count"] == 1
    assert attrs["gen_ai.usage.input_tokens"] > 0
    assert attrs["gen_ai.usage.output_tokens"] > 0

    dumped = repr([(s.name, dict(s.attributes), [e.attributes for e in s.events]) for s in spans])
    assert "zebra-question-marker" not in dumped
    assert "quokka-answer-marker" not in dumped


def _invalid_tool_args(messages, info: AgentInfo) -> ModelResponse:
    args = {"answer": [ANSWER], "cited_chunk_ids": ANSWER, "answerable": ANSWER}
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])


def _plain_text(messages, info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart(ANSWER)])


@pytest.mark.anyio
@pytest.mark.parametrize("respond", [_invalid_tool_args, _plain_text])
async def test_invalid_output_does_not_leak_into_spans(exporter, respond):
    chunks = [_chunk("export", score=0.6)]
    resolved = ResolvedModel(FunctionModel(respond), "anthropic", "test-model")
    with (
        patch.object(site_assistant, "retrieve", AsyncMock(return_value=chunks)),
        patch.object(site_assistant, "load_prompt", AsyncMock(return_value=_seeded_prompt())),
    ):
        response = await site_assistant.ask(None, QUESTION, None, resolved)
    assert response.answerable is False

    spans = exporter.get_finished_spans()
    assert any(e.name == "exception" for s in spans for e in s.events)
    dumped = repr([(s.name, dict(s.attributes), [e.attributes for e in s.events]) for s in spans])
    assert "quokka-answer-marker" not in dumped
    assert "zebra-question-marker" not in dumped


@pytest.mark.anyio
async def test_pipeline_error_message_not_recorded(exporter):
    resolved = ResolvedModel(FunctionModel(_respond), "anthropic", "test-model")
    failing = AsyncMock(side_effect=RuntimeError(f"bad SQL param {QUESTION}"))
    with patch.object(site_assistant, "retrieve", failing):
        with pytest.raises(site_assistant.SiteAssistantUnavailable):
            await site_assistant.ask(None, QUESTION, None, resolved)

    spans = exporter.get_finished_spans()
    dumped = repr([(s.name, dict(s.attributes), [e.attributes for e in s.events]) for s in spans])
    assert "zebra-question-marker" not in dumped
    assert "RuntimeError" in dumped


@pytest.mark.anyio
async def test_short_circuit_span_records_no_model_attributes(exporter):
    resolved = ResolvedModel(FunctionModel(_respond), "anthropic", "test-model")
    with patch.object(site_assistant, "retrieve", AsyncMock(return_value=[])):
        response = await site_assistant.ask(None, QUESTION, None, resolved)
    assert response.answerable is False

    root = next(s for s in exporter.get_finished_spans() if s.name == "site_assistant.ask")
    assert root.attributes["site_assistant.answerable"] is False
    assert "gen_ai.usage.input_tokens" not in root.attributes


@pytest.mark.anyio
async def test_daily_cap_hit_is_not_a_span_error(exporter):
    resolved = ResolvedModel(FunctionModel(_respond), "anthropic", "test-model")

    async def _capped() -> None:
        raise DailyCapReached(60)

    with (
        patch.object(site_assistant, "retrieve", AsyncMock(return_value=[_chunk("export")])),
        patch.object(site_assistant, "load_prompt", AsyncMock(return_value=_seeded_prompt())),
    ):
        with pytest.raises(DailyCapReached):
            await site_assistant.ask(None, QUESTION, None, resolved, before_model_call=_capped)

    root = next(s for s in exporter.get_finished_spans() if s.name == "site_assistant.ask")
    assert root.status.status_code is not StatusCode.ERROR
    assert not root.events
    assert root.attributes["site_assistant.daily_cap_reached"] is True
