"""Answer-eval library: config, metered models, spend caps and metrics for one configuration.
Pure functions plus one async runner; the CLI lives in scripts/eval_site_assistant.py."""

import hashlib
import json
import math
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import yaml
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services import site_assistant
from app.services.prompt_loader import LoadedPrompt
from app.services.provider import ResolvedModel
from app.services.site_retrieval import retrieve
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
ANSWER_BASELINE_PATH = EVALS_DIR / "answer_baseline.yaml"
_DATED_MODEL_RE = re.compile(r"-\d{8}$")
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
    cited_ids: list[str] = field(default_factory=list)
    model_violations: list[str] = field(default_factory=list)
    served_violations: list[str] = field(default_factory=list)
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


def baseline_generation_tokens(path: Path = ANSWER_BASELINE_PATH) -> TokenUsage | None:
    """Measured tokens per question from the committed answer baseline, if one exists."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tokens = (raw.get("tokens_per_question") or {}).get("generation")
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
) -> QuestionResult:
    """Ask once through the serving pipeline, keeping the raw model output and the served one."""
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
        return result
    chunks = seen["chunks"]
    if not site_assistant.reaches_model(chunks):
        result.short_circuited = True
        return result
    output = seen.get("output")
    if output is None:
        result.model_error = True
        result.provider_error = ledger.request_errors > errors_before
        return result

    result.served = response.answerable
    result.cited_ids = [c.content_id for c in response.citations]
    if q.probe is not None:
        retrieved = {c.content_id for c in chunks}
        result.model_violations = model_violations(
            output.answer, output.cited_chunk_ids, retrieved, q.probe, output.answerable
        )
        result.served_violations = answer_violations(response.answer, q.probe)
    return result


@dataclass
class RunResult:
    configuration: dict[str, str]
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


async def run_answer_eval(
    db: AsyncSession,
    resolved: ResolvedModel,
    prompt: LoadedPrompt,
    config: AnswerEvalConfig,
    *,
    entries: list[GoldenEntry] | None = None,
    probes: list[Probe] | None = None,
    estimate_tokens: TokenUsage | None = None,
) -> RunResult:
    """One pass over golden entries and probes; raises before any call if unpriced or over cap."""
    ledger = CostLedger(config.per_run_cap_usd)
    metered_resolved = metered(resolved, config, ledger, "generation")
    questions = _questions(
        load_dataset() if entries is None else entries, load_probes() if probes is None else probes
    )

    reaching = 0
    for q in questions:
        chunks = await retrieve(db, q.question, settings.SITE_ASSISTANT_TOP_K, q.persona)
        reaching += site_assistant.reaches_model(chunks)
    tokens = estimate_tokens or baseline_generation_tokens() or config.default_generation_tokens
    price = config.price(resolved.model_name, resolved.provider_name)
    estimate = estimate_cost(reaching, tokens, price)
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
                results.append(await _ask_observed(db, q, metered_resolved, ledger))
            except Exception as exc:
                # Stop but keep the result, so money already spent is still reported.
                error = f"{q.id}: {type(exc).__name__}: {exc}"
                results.append(_empty_result(q))
                results[-1].asked = False
                results[-1].calls = ledger.calls[calls_before:]

    measured = tokens_per_question(results)
    return RunResult(
        configuration={
            "provider": resolved.provider_name,
            "model": resolved.model_name,
            "prompt_version": prompt.version,
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
        tokens_per_question={"generation": asdict(measured)},
        questions=results,
    )


def write_result(result: RunResult, path: Path) -> None:
    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")


# Report

_REPORT_COLUMNS = (
    ("answer_rate", "answer"),
    ("refusal_accuracy", "refusal"),
    ("citation_hit_rate", "citation"),
    ("probe_model_violation_rate", "probe_viol"),
    ("probe_served_violations", "served_viol"),
)


def _fmt(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1%}" if isinstance(value, float) else str(value)


def format_answer_report(result: RunResult) -> str:
    cfg = result.configuration
    lines = [
        f"provider={cfg['provider']} model={cfg['model']} prompt={cfg['prompt_version']}",
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
    lines.append(f"model errors={m['model_errors']} (provider errors={m['provider_errors']})")
    if result.error:
        lines.append(f"STOPPED on error: {result.error}")
    if result.provider_errors:
        lines.append(f"INCOMPLETE, provider errors: {', '.join(result.provider_errors)}")
    if result.not_asked:
        lines.append(f"INCOMPLETE, not asked: {', '.join(result.not_asked)}")
    return "\n".join(lines)
