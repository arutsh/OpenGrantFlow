"""Answer-eval library tests: config, metering, metrics and caps, with scripted models only."""

import json
from dataclasses import replace
from unittest.mock import patch

import pytest
import yaml
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from app.services import site_assistant
from app.services.provider import ResolvedModel, build_agent
from tests.evals.answer_eval import (
    CONFIG_PATH,
    CallRecord,
    CostLedger,
    EstimateOverCap,
    EvalConfigError,
    Price,
    QuestionResult,
    SpendCapReached,
    TokenUsage,
    UnpricedModel,
    compute_metrics,
    dataset_fingerprint,
    estimate_cost,
    load_config,
    metered,
    metrics_by_category,
    p95,
    run_answer_eval,
    write_result,
)
from tests.evals.retrieval_eval import load_dataset
from tests.evals.site_assistant_eval import ScriptedModel, eval_corpus_session, seeded_prompt
from tests.postgres_schema import requires_postgres

_HONEST = {"answer": "The site does not cover that.", "cited_chunk_ids": [], "answerable": False}


def _config(**overrides):
    config = load_config()
    prices = {**config.prices, "scripted": Price(1.0, 5.0)}
    return replace(config, prices=prices, **overrides)


def _write_config(tmp_path, mutate):
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    mutate(raw)
    path = tmp_path / "answer_eval.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


# Config


def test_committed_config_loads_with_pinned_judge_and_priced_production_model():
    config = load_config()
    assert config.per_run_cap_usd == 0.50 and config.monthly_cap_usd == 1.00
    assert config.judge_model.endswith("-20251001")
    config.price("claude-haiku-4-5-20251001")
    config.price(config.judge_model)


@pytest.mark.parametrize("field", ["caps.per_run_usd", "tolerances.answer_rate", "prices.as_of"])
def test_config_missing_field_fails(tmp_path, field):
    def drop(raw):
        *parents, leaf = field.split(".")
        node = raw
        for key in parents:
            node = node[key]
        del node[leaf]

    with pytest.raises(EvalConfigError, match=field):
        load_config(_write_config(tmp_path, drop))


def test_ollama_is_free_but_unpriced_hosted_models_still_raise():
    config = load_config()
    assert config.price("llama3.2", "ollama") == Price(0.0, 0.0)
    with pytest.raises(UnpricedModel):
        config.price("llama3.2", "anthropic")


def test_fingerprint_covers_every_dataset_file(tmp_path):
    paths = tuple(tmp_path / name for name in ("golden.yaml", "probes.yaml", "injections.yaml"))
    for path in paths:
        path.write_text("x: 1\n")
    before = dataset_fingerprint(paths)
    paths[2].write_text("x: 2\n")
    assert dataset_fingerprint(paths) != before


def test_config_undated_judge_model_fails(tmp_path):
    path = _write_config(tmp_path, lambda raw: raw["judge"].update(model="claude-haiku-4-5"))
    with pytest.raises(EvalConfigError, match="dated version"):
        load_config(path)


# Metering


def _counting_model():
    calls = []

    def respond(messages, info):
        calls.append(messages)
        return ModelResponse(parts=[TextPart("ok")])

    return FunctionModel(respond), calls


@pytest.mark.anyio
async def test_metered_model_records_usage_per_call():
    model, calls = _counting_model()
    ledger = CostLedger(cap_usd=1.0)
    resolved = metered(ResolvedModel(model, "test", "scripted"), _config(), ledger, "generation")
    agent = build_agent(resolved.model, instrument=False)
    await agent.run("first question")
    await agent.run("a second, somewhat longer question")

    assert len(calls) == 2 and len(ledger.calls) == 2
    for record in ledger.calls:
        assert record.role == "generation" and record.model_name == "scripted"
        assert record.input_tokens > 0 and record.output_tokens > 0
        assert record.cost_usd == Price(1.0, 5.0).cost(record.input_tokens, record.output_tokens)
    assert ledger.calls[1].input_tokens > ledger.calls[0].input_tokens
    assert ledger.total_usd == sum(r.cost_usd for r in ledger.calls)


def test_unpriced_model_raises_before_any_request():
    model, calls = _counting_model()
    with pytest.raises(UnpricedModel, match="no-such-model"):
        metered(ResolvedModel(model, "test", "no-such-model"), _config(), CostLedger(1.0), "x")
    assert calls == []


@pytest.mark.anyio
async def test_metered_model_counts_provider_errors():
    def fail(messages, info):
        raise RuntimeError("529 overloaded")

    ledger = CostLedger(cap_usd=1.0)
    model = FunctionModel(fail)
    resolved = metered(ResolvedModel(model, "test", "scripted"), _config(), ledger, "generation")
    with pytest.raises(RuntimeError):
        await build_agent(resolved.model, instrument=False).run("q")
    assert ledger.request_errors == 1 and ledger.calls == []


@pytest.mark.anyio
async def test_metered_model_refuses_requests_at_cap():
    model, calls = _counting_model()
    ledger = CostLedger(cap_usd=0.01)
    ledger.calls.append(CallRecord("generation", "scripted", 0, 0, 0.0, 0.01))
    resolved = metered(ResolvedModel(model, "test", "scripted"), _config(), ledger, "generation")
    with pytest.raises(SpendCapReached):
        await build_agent(resolved.model, instrument=False).run("q")
    assert calls == [] and ledger.blocked == 1


# Metrics


def _call(duration: float = 1.0, cost: float = 0.001) -> CallRecord:
    return CallRecord("generation", "scripted", 1000, 100, duration, cost)


def _golden(id_, answerable=True, served=True, cited=(), expected=("a",), category="c", **kw):
    return QuestionResult(
        id=id_,
        kind="golden",
        category=category,
        answerable=answerable,
        expected_content_ids=list(expected) if answerable else [],
        served=served,
        cited_ids=list(cited),
        **kw,
    )


def test_answer_citing_wrong_source_counts_as_answered_not_cited():
    results = [_golden("right", cited=["a"]), _golden("wrong", cited=["b"])]
    metrics = compute_metrics(results)
    assert metrics["answer_rate"] == 1.0
    assert metrics["citation_hit_rate"] == 0.5


def test_model_refusal_of_unanswerable_counts_as_correctly_refused():
    reached_and_refused = _golden("u1", answerable=False, served=False, calls=[_call()])
    short_circuited = _golden("u2", answerable=False, served=False, short_circuited=True)
    wrongly_served = _golden("u3", answerable=False, served=True, calls=[_call()])
    metrics = compute_metrics([reached_and_refused, short_circuited, wrongly_served])
    assert metrics["refusal_accuracy"] == pytest.approx(2 / 3)
    assert metrics["answer_rate"] is None


def test_model_error_is_never_a_correct_refusal():
    errored = _golden("u1", answerable=False, served=False, model_error=True, provider_error=True)
    refused = _golden("u2", answerable=False, served=False, calls=[_call()])
    metrics = compute_metrics([errored, refused])
    assert metrics["refusal_accuracy"] == 0.5
    assert metrics["model_errors"] == 1 and metrics["provider_errors"] == 1


def test_p95_latency_is_per_question_generation_time():
    judge = CallRecord("judge", "scripted", 10, 10, 10.0, 0.0)
    retried = _golden("a1", cited=["a"], calls=[_call(1.0), _call(2.0), judge])
    assert compute_metrics([retried])["p95_latency_s"] == 3.0


def test_metrics_overall_and_per_category():
    results = [
        _golden("a1", cited=["a"], category="budgeting", calls=[_call(1.0, 0.002)]),
        _golden("a2", served=False, category="budgeting", calls=[_call(3.0, 0.002)]),
        _golden("a3", category="export", model_error=True, served=False),
        QuestionResult("p1", "probe", "hallucination", calls=[_call(2.0)]),
        QuestionResult(
            "p2",
            "probe",
            "hallucination",
            model_violations=["forbidden_claim"],
            served_violations=["forbidden_claim"],
            calls=[_call(5.0)],
        ),
        QuestionResult("p3", "probe", "hallucination", short_circuited=True),
        QuestionResult("skipped", "probe", "hallucination", asked=False, calls=[]),
    ]
    metrics = compute_metrics(results)
    assert metrics["answer_rate"] == pytest.approx(1 / 3)
    assert metrics["citation_hit_rate"] == 1.0
    assert metrics["probe_model_violation_rate"] == 0.5
    assert metrics["probe_served_violations"] == 1
    assert metrics["p95_latency_s"] == 5.0
    assert metrics["input_tokens"] == 4000 and metrics["output_tokens"] == 400
    assert metrics["cost_usd"] == pytest.approx(0.006)

    by_category = metrics_by_category(results)
    assert set(by_category) == {"budgeting", "export", "hallucination"}
    assert by_category["budgeting"]["answer_rate"] == 0.5
    assert by_category["export"]["answer_rate"] == 0.0
    assert by_category["hallucination"]["answer_rate"] is None


def test_calls_of_question_cut_short_by_cap_still_count_as_spend():
    cut_short = _golden("a1", asked=False, served=False, calls=[_call(1.0, 0.004)])
    metrics = compute_metrics([_golden("a2", cited=["a"], calls=[_call(1.0, 0.002)]), cut_short])
    assert metrics["cost_usd"] == pytest.approx(0.006)
    assert metrics["input_tokens"] == 2000
    assert metrics["answer_rate"] == 1.0


def test_p95_nearest_rank():
    assert p95([]) is None
    assert p95([0.5]) == 0.5
    assert p95([float(i) for i in range(1, 21)]) == 19.0


def test_estimate_scales_with_questions_and_tokens():
    price = Price(1.0, 5.0)
    assert estimate_cost(60, TokenUsage(3000, 200), price) == pytest.approx(0.24)
    assert estimate_cost(0, TokenUsage(3000, 200), price) == 0.0


# Runner over the seeded corpus (Postgres)


@requires_postgres
@pytest.mark.anyio
async def test_estimate_over_cap_refuses_to_start():
    scripted = ScriptedModel(_HONEST)
    resolved = ResolvedModel(scripted.model, "test", "scripted")
    async with eval_corpus_session("eval_answer_estimate") as db:
        with pytest.raises(EstimateOverCap):
            await run_answer_eval(
                db,
                resolved,
                seeded_prompt(),
                _config(),
                entries=load_dataset()[:3],
                probes=[],
                estimate_tokens=TokenUsage(10**9, 0),
            )
    assert scripted.calls == []


@requires_postgres
@pytest.mark.anyio
async def test_cap_reached_mid_run_stops_and_marks_incomplete():
    entries = [e for e in load_dataset() if e.answerable][:4]
    scripted = ScriptedModel(_HONEST)
    resolved = ResolvedModel(scripted.model, "test", "scripted")
    async with eval_corpus_session("eval_answer_cap") as db:
        result = await run_answer_eval(
            db,
            resolved,
            seeded_prompt(),
            _config(per_run_cap_usd=1e-9),
            entries=entries,
            probes=[],
            estimate_tokens=TokenUsage(0, 0),
        )
    assert result.complete is False
    assert len(scripted.calls) == 1
    asked = [q for q in result.questions if q.asked]
    assert len(asked) == 1 and asked[0].calls
    assert result.not_asked == [e.id for e in entries[1:]]
    assert result.cost_usd >= result.cap_usd


@requires_postgres
@pytest.mark.anyio
async def test_full_run_writes_result_and_short_circuits_cost_nothing(tmp_path):
    scripted = ScriptedModel(_HONEST)
    resolved = ResolvedModel(scripted.model, "test", "scripted")
    async with eval_corpus_session("eval_answer_full") as db:
        result = await run_answer_eval(db, resolved, seeded_prompt(), _config())
    path = tmp_path / "result.json"
    write_result(result, path)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["configuration"] == {
        "provider": "test",
        "model": "scripted",
        "prompt_version": "v1",
    }
    assert len(data["dataset_fingerprint"]) == 64
    assert data["complete"] is True and data["not_asked"] == []
    assert data["provider_errors"] == [] and data["error"] is None
    for key in ("estimate_usd", "cost_usd", "cap_usd", "categories", "tokens_per_question"):
        assert key in data
    for key in (
        "answer_rate",
        "refusal_accuracy",
        "citation_hit_rate",
        "probe_model_violation_rate",
        "probe_served_violations",
        "model_errors",
        "provider_errors",
        "p95_latency_s",
        "input_tokens",
        "output_tokens",
        "cost_usd",
    ):
        assert key in data["metrics"]

    questions = data["questions"]
    short_circuited = [q for q in questions if q["short_circuited"]]
    assert short_circuited and all(q["calls"] == [] for q in short_circuited)
    reached = [q for q in questions if not q["short_circuited"]]
    assert len(scripted.calls) == len(reached)
    assert all(len(q["calls"]) == 1 for q in reached)
    assert {q["kind"] for q in questions} == {"golden", "probe"}


async def _run_subset(db, model, entries, **kwargs):
    resolved = ResolvedModel(model, "test", "scripted")
    return await run_answer_eval(
        db, resolved, seeded_prompt(), _config(), entries=entries, probes=[], **kwargs
    )


def _reaching_entries(n: int):
    return [e for e in load_dataset() if e.answerable][:n]


@requires_postgres
@pytest.mark.anyio
async def test_provider_error_marks_run_incomplete_but_malformed_output_does_not():
    def fail(messages, info):
        raise RuntimeError("529 overloaded")

    entries = _reaching_entries(2)
    async with eval_corpus_session("eval_answer_errors") as db:
        failed = await _run_subset(db, FunctionModel(fail), entries)
        malformed = await _run_subset(db, ScriptedModel({"text": "junk"}).model, entries)

    assert failed.complete is False
    assert failed.provider_errors == [e.id for e in entries]
    assert failed.metrics["model_errors"] == 2
    assert malformed.complete is True and malformed.provider_errors == []
    assert malformed.metrics["model_errors"] == 2
    assert malformed.metrics["answer_rate"] == 0.0


@requires_postgres
@pytest.mark.anyio
async def test_pipeline_exception_stops_run_and_keeps_spend():
    entries = _reaching_entries(3)
    scripted = ScriptedModel(_HONEST)
    real_ask = site_assistant.ask
    asked = []

    async def flaky_ask(*args, **kwargs):
        asked.append(args[1])
        if len(asked) == 2:
            raise site_assistant.SiteAssistantUnavailable("retrieve")
        return await real_ask(*args, **kwargs)

    async with eval_corpus_session("eval_answer_exception") as db:
        with patch.object(site_assistant, "ask", flaky_ask):
            result = await _run_subset(db, scripted.model, entries)

    assert result.complete is False
    assert result.error == f"{entries[1].id}: SiteAssistantUnavailable: retrieve"
    assert result.not_asked == [e.id for e in entries[1:]]
    assert len(asked) == 2 and len(scripted.calls) == 1
    assert result.cost_usd > 0 and result.metrics["cost_usd"] == result.cost_usd
