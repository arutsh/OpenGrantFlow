"""Answer-eval library: config, metered models, spend caps and metrics for one configuration.
Pure functions plus one async runner; the CLI lives in scripts/eval_site_assistant.py."""

import hashlib
import json
import math
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import yaml
from jinja2 import Template, TemplateSyntaxError
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services import site_assistant
from app.services.prompt_loader import LoadedPrompt
from app.services.provider import ResolvedModel, build_agent
from app.services.site_retrieval import RetrievedChunk, retrieve
from tests.evals.retrieval_eval import DATASET_PATH, EVALS_DIR, GoldenEntry, load_dataset
from tests.evals.site_assistant_eval import (
    INJECTION_CORPUS_PATH,
    PROBES_PATH,
    Probe,
    answer_violations,
    load_probes,
    model_violations,
)

CONFIG_PATH = EVALS_DIR / "data" / "answer_eval.yaml"
JUDGE_PROMPT_PATH = EVALS_DIR / "data" / "judge_prompt.yaml"
ANSWER_BASELINE_PATH = EVALS_DIR / "answer_baseline.yaml"
_DATED_MODEL_RE = re.compile(r"-\d{8}$")
_JUDGE_MAX_TOKENS = 300
# Self-hosted providers cost nothing per token, so they need no price-table entry.
_FREE_PROVIDERS = ("ollama",)

HIGHER_IS_BETTER = (
    "answer_rate",
    "refusal_accuracy",
    "citation_hit_rate",
    "groundedness_rate",
    "completeness_rate",
)
LOWER_IS_BETTER = ("probe_model_violation_rate",)
TOLERANCE_METRICS = HIGHER_IS_BETTER + LOWER_IS_BETTER


class EvalConfigError(ValueError):
    """answer_eval.yaml is missing a field or names something the runner can't use."""


class UnpricedModel(ValueError):
    """A model has no price-table entry, so its cost can't be capped."""


class EstimateOverCap(Exception):
    def __init__(self, estimate_usd: float, cap_usd: float):
        super().__init__(f"estimated ${estimate_usd:.4f} exceeds the per-run cap ${cap_usd:.2f}")
        self.estimate_usd = estimate_usd
        self.cap_usd = cap_usd


class BaselineRefused(Exception):
    """A baseline can only be written from a complete run."""


class SpendCapReached(Exception):
    """Raised by MeteredModel instead of sending a request once the ledger is at its cap."""


# Config


@dataclass(frozen=True)
class TokenUsage:
    input: int
    output: int


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * self.input_per_mtok + output_tokens * self.output_per_mtok) / 1e6


@dataclass(frozen=True)
class AnswerEvalConfig:
    per_run_cap_usd: float
    monthly_cap_usd: float
    tolerances: dict[str, float]
    judge_model: str
    judge_prompt_version: str
    default_generation_tokens: TokenUsage
    default_judge_tokens: TokenUsage
    prices_as_of: str
    prices: dict[str, Price]

    def price(self, model_name: str, provider_name: str | None = None) -> Price:
        if provider_name in _FREE_PROVIDERS:
            return Price(0.0, 0.0)
        try:
            return self.prices[model_name]
        except KeyError:
            raise UnpricedModel(
                f"model {model_name!r} has no entry in the answer-eval price table"
            ) from None


def _require(raw: Any, dotted: str) -> Any:
    node = raw
    for key in dotted.split("."):
        if not isinstance(node, dict) or node.get(key) is None:
            raise EvalConfigError(f"answer_eval config is missing {dotted!r}")
        node = node[key]
    return node


def _tokens(raw: Any, dotted: str) -> TokenUsage:
    return TokenUsage(int(_require(raw, f"{dotted}.input")), int(_require(raw, f"{dotted}.output")))


def load_config(path: Path = CONFIG_PATH) -> AnswerEvalConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    judge_model = str(_require(raw, "judge.model"))
    if not _DATED_MODEL_RE.search(judge_model):
        raise EvalConfigError(f"judge model {judge_model!r} must be a dated version (-YYYYMMDD)")
    tolerances = {m: float(_require(raw, f"tolerances.{m}")) for m in TOLERANCE_METRICS}
    prices = {
        name: Price(float(_require(entry, "input")), float(_require(entry, "output")))
        for name, entry in _require(raw, "prices.usd_per_mtok").items()
    }
    return AnswerEvalConfig(
        per_run_cap_usd=float(_require(raw, "caps.per_run_usd")),
        monthly_cap_usd=float(_require(raw, "caps.monthly_usd")),
        tolerances=tolerances,
        judge_model=judge_model,
        judge_prompt_version=str(_require(raw, "judge.prompt_version")),
        default_generation_tokens=_tokens(raw, "default_tokens_per_question.generation"),
        default_judge_tokens=_tokens(raw, "default_tokens_per_question.judge"),
        prices_as_of=str(_require(raw, "prices.as_of")),
        prices=prices,
    )


def load_judge_prompt(version: str, path: Path = JUDGE_PROMPT_PATH) -> LoadedPrompt:
    """The committed judge prompt; refuses when it isn't the version answer_eval.yaml pins."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("version", "system_prompt", "user_template"):
        if not raw.get(key):
            raise EvalConfigError(f"judge prompt is missing {key!r}")
    if str(raw["version"]) != version:
        raise EvalConfigError(f"judge prompt is {raw['version']!r}, config pins {version!r}")
    try:
        Template(raw["user_template"])
    except TemplateSyntaxError as exc:
        raise EvalConfigError(f"judge prompt template is invalid: {exc}") from exc
    return LoadedPrompt(
        name="answer_judge",
        version=str(raw["version"]),
        system_prompt=raw["system_prompt"],
        user_template=raw["user_template"],
    )


def render_judge_message(
    template: Template, question: str, answer: str, chunks: list[RetrievedChunk]
) -> str:
    return template.render(question=question, answer=answer, chunks=chunks)


def dataset_fingerprint(
    paths: tuple[Path, ...] = (DATASET_PATH, PROBES_PATH, INJECTION_CORPUS_PATH),
) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


# Metering


@dataclass(frozen=True)
class CallRecord:
    role: str
    model_name: str
    input_tokens: int
    output_tokens: int
    duration_s: float
    cost_usd: float


@dataclass
class CostLedger:
    cap_usd: float
    calls: list[CallRecord] = field(default_factory=list)
    blocked: int = 0
    request_errors: int = 0

    @property
    def total_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def cap_reached(self) -> bool:
        return self.total_usd >= self.cap_usd


class MeteredModel(WrapperModel):
    """Records each request's usage, duration and cost, and refuses requests once at the cap."""

    def __init__(
        self, wrapped: Model, model_name: str, price: Price, ledger: CostLedger, role: str
    ):
        super().__init__(wrapped)
        self.priced_name = model_name
        self.price = price
        self.ledger = ledger
        self.role = role

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        if self.ledger.cap_reached:
            self.ledger.blocked += 1
            raise SpendCapReached(f"per-run cap ${self.ledger.cap_usd:.2f} reached")
        start = time.perf_counter()
        try:
            response = await super().request(messages, model_settings, model_request_parameters)
        except Exception:
            # Provider failures (429, 5xx, timeouts); malformed output fails later, in the agent.
            self.ledger.request_errors += 1
            raise
        duration = time.perf_counter() - start
        usage = response.usage
        tokens_in, tokens_out = usage.input_tokens or 0, usage.output_tokens or 0
        self.ledger.calls.append(
            CallRecord(
                self.role,
                self.priced_name,
                tokens_in,
                tokens_out,
                duration,
                self.price.cost(tokens_in, tokens_out),
            )
        )
        return response

    def request_stream(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("streaming would bypass usage metering")


def metered(
    resolved: ResolvedModel, config: AnswerEvalConfig, ledger: CostLedger, role: str
) -> ResolvedModel:
    """Wrap a resolved model for the eval; raises UnpricedModel before any request can be made."""
    price = config.price(resolved.model_name, resolved.provider_name)
    model = MeteredModel(resolved.model, resolved.model_name, price, ledger, role)
    return ResolvedModel(model, resolved.provider_name, resolved.model_name)


# Per-question results and metrics


@dataclass
class QuestionResult:
    id: str
    kind: str  # "golden" or "probe"
    category: str
    answerable: bool | None = None
    expected_content_ids: list[str] = field(default_factory=list)
    asked: bool = True
    short_circuited: bool = False
    model_error: bool = False
    provider_error: bool = False
    served: bool = False
    answer: str = ""
    cited_ids: list[str] = field(default_factory=list)
    model_violations: list[str] = field(default_factory=list)
    served_violations: list[str] = field(default_factory=list)
    judge_grounded: bool | None = None
    judge_complete: bool | None = None
    judge_reason: str | None = None
    judge_error: bool = False
    calls: list[CallRecord] = field(default_factory=list)


def _rate(hits: int, total: int) -> float | None:
    return hits / total if total else None


def p95(values: list[float]) -> float | None:
    """Nearest-rank 95th percentile."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(math.ceil(0.95 * len(ordered)) - 1, 0)]


def _generation_seconds(result: QuestionResult) -> float:
    return sum(c.duration_s for c in result.calls if c.role == "generation")


def compute_metrics(results: list[QuestionResult]) -> dict[str, float | int | None]:
    """Deterministic metrics over asked questions; a rate is None when nothing qualifies."""
    asked = [r for r in results if r.asked]
    answerable = [r for r in asked if r.kind == "golden" and r.answerable]
    unanswerable = [r for r in asked if r.kind == "golden" and r.answerable is False]
    served_answerable = [r for r in answerable if r.served]
    judged = [r for r in served_answerable if r.judge_grounded is not None]
    probes = [r for r in asked if r.kind == "probe"]
    probes_reached = [r for r in probes if not r.short_circuited and not r.model_error]
    # Spend includes calls made by a question the cap then cut short.
    calls = [c for r in results for c in r.calls]
    return {
        "answer_rate": _rate(len(served_answerable), len(answerable)),
        "refusal_accuracy": _rate(
            sum(not r.served and not r.model_error for r in unanswerable), len(unanswerable)
        ),
        "citation_hit_rate": _rate(
            sum(bool(set(r.cited_ids) & set(r.expected_content_ids)) for r in served_answerable),
            len(served_answerable),
        ),
        "groundedness_rate": _rate(sum(bool(r.judge_grounded) for r in judged), len(judged)),
        "completeness_rate": _rate(sum(bool(r.judge_complete) for r in judged), len(judged)),
        "judge_errors": sum(r.judge_error for r in served_answerable),
        "probe_model_violation_rate": _rate(
            sum(bool(r.model_violations) for r in probes_reached), len(probes_reached)
        ),
        "probe_served_violations": sum(bool(r.served_violations) for r in probes),
        "model_errors": sum(r.model_error for r in asked),
        "provider_errors": sum(r.provider_error for r in asked),
        "p95_latency_s": p95(
            [
                _generation_seconds(r)
                for r in results
                if any(c.role == "generation" for c in r.calls)
            ]
        ),
        "input_tokens": sum(c.input_tokens for c in calls),
        "output_tokens": sum(c.output_tokens for c in calls),
        "cost_usd": sum(c.cost_usd for c in calls),
    }


def metrics_by_category(results: list[QuestionResult]) -> dict[str, dict[str, float | int | None]]:
    grouped: dict[str, list[QuestionResult]] = defaultdict(list)
    for result in results:
        grouped[result.category].append(result)
    return {category: compute_metrics(grouped[category]) for category in sorted(grouped)}


def tokens_per_question(results: list[QuestionResult], role: str = "generation") -> TokenUsage:
    """Average tokens per model-reaching question, as the next run's estimate input."""
    per_question = [
        [c for c in r.calls if c.role == role] for r in results if r.asked and not r.short_circuited
    ]
    per_question = [calls for calls in per_question if calls]
    if not per_question:
        return TokenUsage(0, 0)
    n = len(per_question)
    return TokenUsage(
        round(sum(c.input_tokens for calls in per_question for c in calls) / n),
        round(sum(c.output_tokens for calls in per_question for c in calls) / n),
    )


# Estimate and cap


def estimate_cost(model_questions: int, tokens: TokenUsage, price: Price) -> float:
    return model_questions * price.cost(tokens.input, tokens.output)


def estimate_run_cost(
    *,
    model_questions: int,
    generation_tokens: TokenUsage,
    generation_price: Price,
    judged_questions: int,
    judge_tokens: TokenUsage,
    judge_price: Price,
) -> float:
    """Generation for every model-reaching question plus a judge call per expected answer."""
    return estimate_cost(model_questions, generation_tokens, generation_price) + estimate_cost(
        judged_questions, judge_tokens, judge_price
    )


def baseline_tokens(role: str, path: Path = ANSWER_BASELINE_PATH) -> TokenUsage | None:
    """Measured tokens per question for a role from the committed answer baseline, if any."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tokens = (raw.get("tokens_per_question") or {}).get(role)
    return TokenUsage(int(tokens["input"]), int(tokens["output"])) if tokens else None


def check_estimate(estimate_usd: float, cap_usd: float) -> None:
    if estimate_usd > cap_usd:
        raise EstimateOverCap(estimate_usd, cap_usd)


# Runner


@dataclass(frozen=True)
class _Question:
    id: str
    kind: str
    category: str
    question: str
    persona: Any
    entry: GoldenEntry | None = None
    probe: Probe | None = None


def _questions(entries: list[GoldenEntry], probes: list[Probe]) -> list[_Question]:
    golden = [
        _Question(e.id, "golden", e.category, e.question, e.persona, entry=e) for e in entries
    ]
    return golden + [
        _Question(p.id, "probe", p.category, p.question, p.persona, probe=p) for p in probes
    ]


def _empty_result(q: _Question) -> QuestionResult:
    entry = q.entry
    return QuestionResult(
        id=q.id,
        kind=q.kind,
        category=q.category,
        answerable=entry.answerable if entry else None,
        expected_content_ids=list(entry.expected_content_ids) if entry else [],
    )


async def _ask_observed(
    db: AsyncSession, q: _Question, resolved: ResolvedModel, ledger: CostLedger
) -> tuple[QuestionResult, list[RetrievedChunk]]:
    """Ask once through the serving pipeline; returns the result and the cited chunks."""
    result = _empty_result(q)
    seen: dict = {}
    real_retrieve, real_resolve = site_assistant.retrieve, site_assistant.resolve_citations

    async def _retrieve(*args, **kwargs):
        seen["chunks"] = await real_retrieve(*args, **kwargs)
        return seen["chunks"]

    def _resolve(output, chunks):
        seen["output"] = output
        return real_resolve(output, chunks)

    calls_before, blocked_before = len(ledger.calls), ledger.blocked
    errors_before = ledger.request_errors
    with (
        patch.object(site_assistant, "retrieve", _retrieve),
        patch.object(site_assistant, "resolve_citations", _resolve),
    ):
        response = await site_assistant.ask(db, q.question, q.persona, resolved)
    result.calls = ledger.calls[calls_before:]

    if ledger.blocked > blocked_before:
        result.asked = False
        return result, []
    chunks = seen["chunks"]
    if not site_assistant.reaches_model(chunks):
        result.short_circuited = True
        return result, []
    output = seen.get("output")
    if output is None:
        result.model_error = True
        result.provider_error = ledger.request_errors > errors_before
        return result, []

    result.served = response.answerable
    result.answer = response.answer if response.answerable else ""
    result.cited_ids = [c.content_id for c in response.citations]
    if q.probe is not None:
        retrieved = {c.content_id for c in chunks}
        result.model_violations = model_violations(
            output.answer, output.cited_chunk_ids, retrieved, q.probe, output.answerable
        )
        result.served_violations = answer_violations(response.answer, q.probe)
    cited = set(result.cited_ids)
    return result, [c for c in chunks if c.content_id in cited]


class JudgeVerdict(BaseModel):
    grounded: bool
    complete: bool
    reason: str


def _needs_judge(q: _Question) -> bool:
    return q.entry is not None and q.entry.answerable


def build_judge_agent(judge: ResolvedModel, prompt: LoadedPrompt) -> Agent[None, JudgeVerdict]:
    return build_agent(
        judge.model,
        output_type=JudgeVerdict,
        system_prompt=prompt.system_prompt,
        model_settings={"temperature": 0.0, "max_tokens": _JUDGE_MAX_TOKENS},
        instrument=False,
    )


async def _judge(
    agent: Agent[None, JudgeVerdict],
    template: Template,
    q: _Question,
    result: QuestionResult,
    chunks: list[RetrievedChunk],
    ledger: CostLedger,
) -> None:
    """Grade one served answer in place; a cap block un-asks it, a failed call is a judge error."""
    message = render_judge_message(template, q.question, result.answer, chunks)
    calls_before, blocked_before = len(ledger.calls), ledger.blocked
    errors_before = ledger.request_errors
    try:
        run = await agent.run(message)
    except Exception as exc:
        if ledger.blocked > blocked_before:
            result.asked = False
        else:
            result.judge_error = True
            result.judge_reason = type(exc).__name__
            # An unreachable judge leaves the verdict unmeasured, so it can't be a baseline.
            result.provider_error = ledger.request_errors > errors_before
    else:
        result.judge_grounded = run.output.grounded
        result.judge_complete = run.output.complete
        result.judge_reason = run.output.reason
    result.calls = result.calls + ledger.calls[calls_before:]


@dataclass
class RunResult:
    configuration: dict[str, str]
    judge: dict[str, str]
    dataset_fingerprint: str
    complete: bool
    estimate_usd: float
    cost_usd: float
    cap_usd: float
    not_asked: list[str]
    provider_errors: list[str]
    error: str | None
    metrics: dict[str, float | int | None]
    categories: dict[str, dict[str, float | int | None]]
    tokens_per_question: dict[str, dict[str, int]]
    questions: list[QuestionResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def _estimate_questions(
    db: AsyncSession,
    questions: list[_Question],
    resolved: ResolvedModel,
    judge: ResolvedModel,
    config: AnswerEvalConfig,
    *,
    estimate_tokens: TokenUsage | None = None,
    estimate_judge_tokens: TokenUsage | None = None,
) -> float:
    """Free retrieval pass that counts the questions reaching the model, then prices them."""
    reaching = judged = 0
    for q in questions:
        chunks = await retrieve(db, q.question, settings.SITE_ASSISTANT_TOP_K, q.persona)
        reaches = site_assistant.reaches_model(chunks)
        reaching += reaches
        judged += reaches and _needs_judge(q)
    return estimate_run_cost(
        model_questions=reaching,
        generation_tokens=(
            estimate_tokens or baseline_tokens("generation") or config.default_generation_tokens
        ),
        generation_price=config.price(resolved.model_name, resolved.provider_name),
        judged_questions=judged,
        judge_tokens=(
            estimate_judge_tokens or baseline_tokens("judge") or config.default_judge_tokens
        ),
        judge_price=config.price(judge.model_name, judge.provider_name),
    )


async def run_answer_eval(
    db: AsyncSession,
    resolved: ResolvedModel,
    prompt: LoadedPrompt,
    config: AnswerEvalConfig,
    judge: ResolvedModel,
    judge_prompt: LoadedPrompt,
    *,
    entries: list[GoldenEntry] | None = None,
    probes: list[Probe] | None = None,
    estimate_tokens: TokenUsage | None = None,
    estimate_judge_tokens: TokenUsage | None = None,
    enforce_estimate: bool = True,
) -> RunResult:
    """One pass over golden entries and probes; raises before any call if unpriced or over cap."""
    ledger = CostLedger(config.per_run_cap_usd)
    metered_resolved = metered(resolved, config, ledger, "generation")
    judge_agent = build_judge_agent(metered(judge, config, ledger, "judge"), judge_prompt)
    judge_template = Template(judge_prompt.user_template)
    questions = _questions(
        load_dataset() if entries is None else entries, load_probes() if probes is None else probes
    )

    estimate = await _estimate_questions(
        db,
        questions,
        resolved,
        judge,
        config,
        estimate_tokens=estimate_tokens,
        estimate_judge_tokens=estimate_judge_tokens,
    )
    if enforce_estimate:
        check_estimate(estimate, config.per_run_cap_usd)

    results: list[QuestionResult] = []
    error: str | None = None
    with patch.object(site_assistant, "load_prompt", AsyncMock(return_value=prompt)):
        for q in questions:
            if ledger.cap_reached or error is not None:
                results.append(_empty_result(q))
                results[-1].asked = False
                continue
            calls_before = len(ledger.calls)
            try:
                result, cited = await _ask_observed(db, q, metered_resolved, ledger)
                if result.served and _needs_judge(q):
                    await _judge(judge_agent, judge_template, q, result, cited, ledger)
                results.append(result)
            except Exception as exc:
                # Stop but keep the result, so money already spent is still reported.
                error = f"{q.id}: {type(exc).__name__}: {exc}"
                results.append(_empty_result(q))
                results[-1].asked = False
                results[-1].calls = ledger.calls[calls_before:]

    return RunResult(
        configuration={
            "provider": resolved.provider_name,
            "model": resolved.model_name,
            "prompt_version": prompt.version,
        },
        judge={
            "provider": judge.provider_name,
            "model": judge.model_name,
            "prompt_version": judge_prompt.version,
        },
        dataset_fingerprint=dataset_fingerprint(),
        complete=all(r.asked and not r.provider_error for r in results),
        estimate_usd=estimate,
        cost_usd=ledger.total_usd,
        cap_usd=config.per_run_cap_usd,
        not_asked=[r.id for r in results if not r.asked],
        provider_errors=[r.id for r in results if r.provider_error],
        error=error,
        metrics=compute_metrics(results),
        categories=metrics_by_category(results),
        tokens_per_question={
            role: asdict(tokens_per_question(results, role)) for role in ("generation", "judge")
        },
        questions=results,
    )


def write_result(result: RunResult, path: Path) -> None:
    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")


# Baseline


def write_baseline(result: RunResult, path: Path = ANSWER_BASELINE_PATH) -> None:
    """Record a complete run as the new baseline; leaves the file untouched otherwise."""
    if not result.complete or result.error:
        raise BaselineRefused("only a complete run can be written as the baseline")
    baseline = {
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "configuration": result.configuration,
        "judge": result.judge,
        "dataset_fingerprint": result.dataset_fingerprint,
        "metrics": result.metrics,
        "categories": result.categories,
        "tokens_per_question": result.tokens_per_question,
    }
    header = "# Written by `eval_site_assistant.py run --write-baseline`; do not hand-edit.\n"
    path.write_text(header + yaml.safe_dump(baseline, sort_keys=False), encoding="utf-8")


def load_baseline(path: Path = ANSWER_BASELINE_PATH) -> dict[str, Any]:
    if not path.exists():
        raise EvalConfigError(f"no answer baseline at {path}; run with --write-baseline first")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# Gate

_REPORT_ONLY = ("p95_latency_s", "input_tokens", "output_tokens", "cost_usd")
_EPSILON = 1e-9


@dataclass(frozen=True)
class GateRow:
    metric: str
    baseline: float | int | None
    value: float | int | None
    tolerance: float | None
    status: str  # "pass", "fail" or "report" (shown, never failing)


@dataclass(frozen=True)
class GateReport:
    rows: list[GateRow]
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def _fmt_metric(metric: str, value: float | int | None) -> str:
    if value is None:
        return "-"
    if metric in TOLERANCE_METRICS:
        return f"{value:.1%}"
    return f"{value:.4g}" if isinstance(value, float) else str(value)


def _judge_row(metric: str, base: Any, value: Any, tolerance: float) -> GateRow:
    if base is None:
        status = "pass"
    elif value is None:
        status = "fail"
    elif metric in LOWER_IS_BETTER:
        status = "pass" if value <= base + tolerance + _EPSILON else "fail"
    else:
        status = "pass" if value >= base - tolerance - _EPSILON else "fail"
    return GateRow(metric, base, value, tolerance, status)


def evaluate_gate(
    result: RunResult, baseline: dict[str, Any], config: AnswerEvalConfig
) -> GateReport:
    """Compare a run to the committed baseline; served violations get no tolerance."""
    base_metrics = baseline["metrics"]
    failures: list[str] = []
    if not result.complete:
        failures.append("run is incomplete (spend cap reached or provider errors)")
    if result.dataset_fingerprint != baseline["dataset_fingerprint"]:
        failures.append(
            "dataset, probe or injection files changed since the baseline: "
            "a new baseline is needed (run --write-baseline)"
        )

    served = result.metrics["probe_served_violations"]
    rows = [
        GateRow(
            "probe_served_violations",
            base_metrics["probe_served_violations"],
            served,
            0,
            "fail" if served else "pass",
        )
    ]
    if served:
        failures.append(f"probe_served_violations: {served} (zero tolerance)")
    for metric in TOLERANCE_METRICS:
        row = _judge_row(
            metric, base_metrics[metric], result.metrics[metric], config.tolerances[metric]
        )
        rows.append(row)
        if row.status == "fail":
            failures.append(
                f"{metric}: {_fmt_metric(metric, row.value)} vs baseline "
                f"{_fmt_metric(metric, row.baseline)} "
                f"(tolerance {row.tolerance:.2f})"
            )
    rows += [GateRow(m, base_metrics[m], result.metrics[m], None, "report") for m in _REPORT_ONLY]
    return GateReport(rows, failures)


def format_gate_report(report: GateReport) -> str:
    header = f"{'metric':<28}{'baseline':>12}{'run':>12}{'tolerance':>11}  status"
    lines = [header, "-" * len(header)]
    for row in report.rows:
        tolerance = "-" if row.tolerance is None else f"{row.tolerance:.2f}"
        lines.append(
            f"{row.metric:<28}{_fmt_metric(row.metric, row.baseline):>12}"
            f"{_fmt_metric(row.metric, row.value):>12}"
            f"{tolerance:>11}  {row.status}"
        )
    lines.append("")
    lines.append("GATE PASSED" if report.passed else "GATE FAILED")
    lines += [f"  - {failure}" for failure in report.failures]
    return "\n".join(lines)


# Comparison

_COMPARE_METRICS = TOLERANCE_METRICS + ("probe_served_violations", "judge_errors") + _REPORT_ONLY


async def run_comparison(
    db: AsyncSession,
    production: tuple[ResolvedModel, LoadedPrompt],
    candidate: tuple[ResolvedModel, LoadedPrompt],
    config: AnswerEvalConfig,
    judge: ResolvedModel,
    judge_prompt: LoadedPrompt,
    **kwargs: Any,
) -> tuple[RunResult, RunResult]:
    """Run both configurations under one per-run cap: combined estimate, then shared spend."""
    entries, probes = kwargs.get("entries"), kwargs.get("probes")
    questions = _questions(
        load_dataset() if entries is None else entries, load_probes() if probes is None else probes
    )
    estimate = 0.0
    for resolved, _ in (production, candidate):
        estimate += await _estimate_questions(
            db,
            questions,
            resolved,
            judge,
            config,
            estimate_tokens=kwargs.get("estimate_tokens"),
            estimate_judge_tokens=kwargs.get("estimate_judge_tokens"),
        )
    check_estimate(estimate, config.per_run_cap_usd)

    prod_result = await run_answer_eval(
        db, *production, config, judge, judge_prompt, enforce_estimate=False, **kwargs
    )
    remaining = max(config.per_run_cap_usd - prod_result.cost_usd, 0.0)
    cand_result = await run_answer_eval(
        db,
        *candidate,
        replace(config, per_run_cap_usd=remaining),
        judge,
        judge_prompt,
        enforce_estimate=False,
        **kwargs,
    )
    return prod_result, cand_result


def _diff(metric: str, a: float | int | None, b: float | int | None) -> str:
    if a is None or b is None:
        return "-"
    delta = b - a
    return f"{delta * 100:+.1f}pt" if metric in TOLERANCE_METRICS else f"{delta:+.4g}"


def format_comparison(production: RunResult, candidate: RunResult) -> str:
    def describe(label: str, r: RunResult) -> str:
        cfg = r.configuration
        return (
            f"{label}: {cfg['provider']}/{cfg['model']} prompt={cfg['prompt_version']} "
            f"complete={r.complete} cost=${r.cost_usd:.4f}"
        )

    lines = [
        describe("production", production),
        describe("candidate ", candidate),
        f"judge={production.judge['model']} judge_prompt={production.judge['prompt_version']}",
        "",
    ]
    header = f"{'metric':<28}{'production':>12}{'candidate':>12}{'diff':>12}"
    lines += [header, "-" * len(header)]
    for metric in _COMPARE_METRICS:
        a, b = production.metrics[metric], candidate.metrics[metric]
        lines.append(
            f"{metric:<28}{_fmt_metric(metric, a):>12}{_fmt_metric(metric, b):>12}"
            f"{_diff(metric, a, b):>12}"
        )
    for label, r in (("production", production), ("candidate", candidate)):
        if not r.complete:
            lines.append(f"{label.upper()} INCOMPLETE, not asked: {', '.join(r.not_asked) or '-'}")
    return "\n".join(lines)


# Report

_REPORT_COLUMNS = (
    ("answer_rate", "answer"),
    ("refusal_accuracy", "refusal"),
    ("citation_hit_rate", "citation"),
    ("groundedness_rate", "grounded"),
    ("completeness_rate", "complete"),
    ("probe_model_violation_rate", "probe_viol"),
    ("probe_served_violations", "served_viol"),
)


def _fmt(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1%}" if isinstance(value, float) else str(value)


def format_answer_report(result: RunResult) -> str:
    cfg, judge = result.configuration, result.judge
    lines = [
        f"provider={cfg['provider']} model={cfg['model']} prompt={cfg['prompt_version']}",
        f"judge={judge['provider']}/{judge['model']} judge_prompt={judge['prompt_version']}",
        f"dataset={result.dataset_fingerprint[:12]} complete={result.complete} "
        f"cost=${result.cost_usd:.4f} (estimate ${result.estimate_usd:.4f}, "
        f"cap ${result.cap_usd:.2f})",
        "",
    ]
    header = f"{'category':<20}" + "".join(f"{label:>12}" for _, label in _REPORT_COLUMNS)
    lines += [header, "-" * len(header)]
    rows = list(result.categories.items()) + [("OVERALL", result.metrics)]
    for name, metrics in rows:
        lines.append(f"{name:<20}" + "".join(f"{_fmt(metrics[k]):>12}" for k, _ in _REPORT_COLUMNS))

    m = result.metrics
    latency = "-" if m["p95_latency_s"] is None else f"{m['p95_latency_s']:.2f}s"
    lines += [
        "",
        f"p95 latency={latency} input_tokens={m['input_tokens']} "
        f"output_tokens={m['output_tokens']}",
    ]
    failing = [
        f"{r.id} ({'/'.join(sorted(set(r.model_violations + r.served_violations)))})"
        for r in result.questions
        if r.model_violations or r.served_violations
    ]
    lines.append("probe violations: " + (", ".join(failing) or "none"))
    lines.append(
        f"model errors={m['model_errors']} "
        f"provider errors (generation or judge)={m['provider_errors']}"
    )
    for label, failed in (
        ("ungrounded", [r.id for r in result.questions if r.judge_grounded is False]),
        ("incomplete", [r.id for r in result.questions if r.judge_complete is False]),
        ("judge errors", [r.id for r in result.questions if r.judge_error]),
    ):
        lines.append(f"{label} ({len(failed)}): {', '.join(failed) or 'none'}")
    if result.error:
        lines.append(f"STOPPED on error: {result.error}")
    if result.provider_errors:
        lines.append(f"INCOMPLETE, provider errors: {', '.join(result.provider_errors)}")
    if result.not_asked:
        lines.append(f"INCOMPLETE, not asked: {', '.join(result.not_asked)}")
    return "\n".join(lines)
