"""Golden-dataset loading, retrieval metrics and the per-category report for the retrieval eval."""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import get_args

import yaml

from app.services.site_retrieval import Persona, RetrievedChunk

EVALS_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVALS_DIR / "data" / "golden_dataset.yaml"
BASELINE_PATH = EVALS_DIR / "baseline.yaml"

PERSONAS = set(get_args(Persona))
RANKED_METRICS = ("recall_at_1", "recall_at_3", "recall_at_5", "mrr")
UNANSWERABLE_METRIC = "unanswerable_accuracy"


@dataclass(frozen=True)
class GoldenEntry:
    id: str
    question: str
    expected_content_ids: list[str]
    persona: str | None
    category: str
    answerable: bool


@dataclass
class EvalReport:
    overall: dict[str, float]
    categories: dict[str, dict[str, float]]
    corpus_tokens: int
    avg_top_k_tokens: float
    unanswerable_false_positives: list[str] = field(default_factory=list)
    misses_at_5: list[str] = field(default_factory=list)
    top_scores: dict[str, tuple[bool, float]] = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    # ~4 chars/token: a tokenizer-free estimate so the eval stays offline and dependency-free.
    return math.ceil(len(text) / 4)


def load_dataset(path: Path = DATASET_PATH) -> list[GoldenEntry]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = [GoldenEntry(**item) for item in raw["entries"]]
    validate_dataset(entries)
    return entries


def validate_dataset(entries: list[GoldenEntry], known_ids: set[str] | None = None) -> None:
    """Raise ValueError on any entry violating the golden-dataset format."""
    seen: set[str] = set()
    for entry in entries:
        if entry.id in seen:
            raise ValueError(f"duplicate entry id {entry.id!r}")
        seen.add(entry.id)
        if not entry.question.strip():
            raise ValueError(f"{entry.id}: empty question")
        if entry.persona is not None and entry.persona not in PERSONAS:
            raise ValueError(f"{entry.id}: unknown persona {entry.persona!r}")
        if entry.answerable and not entry.expected_content_ids:
            raise ValueError(f"{entry.id}: answerable entry needs expected_content_ids")
        if not entry.answerable and entry.expected_content_ids:
            raise ValueError(f"{entry.id}: unanswerable entry must have no expected_content_ids")
        if known_ids is not None:
            unknown = set(entry.expected_content_ids) - known_ids
            if unknown:
                raise ValueError(f"{entry.id}: content_ids not in corpus: {sorted(unknown)}")


def _first_relevant_rank(entry: GoldenEntry, results: list[RetrievedChunk]) -> int | None:
    for rank, result in enumerate(results, start=1):
        if result.content_id in entry.expected_content_ids:
            return rank
    return None


def _ranked_metrics(ranks: list[int | None]) -> dict[str, float]:
    count = len(ranks)
    return {
        "recall_at_1": sum(r is not None and r <= 1 for r in ranks) / count,
        "recall_at_3": sum(r is not None and r <= 3 for r in ranks) / count,
        "recall_at_5": sum(r is not None and r <= 5 for r in ranks) / count,
        "mrr": sum(1 / r for r in ranks if r is not None) / count,
    }


def compute_report(
    entries: list[GoldenEntry],
    results: dict[str, list[RetrievedChunk]],
    threshold: float,
    corpus_tokens: int,
) -> EvalReport:
    """Score each entry's ranked `results`; Recall/MRR over answerable entries only."""
    ranks_by_category: dict[str, list[int | None]] = defaultdict(list)
    all_ranks: list[int | None] = []
    misses: list[str] = []
    flags: list[bool] = []
    false_positives: list[str] = []

    top_scores: dict[str, tuple[bool, float]] = {}
    for entry in entries:
        entry_results = results[entry.id]
        top_scores[entry.id] = (entry.answerable, entry_results[0].score if entry_results else 0.0)
        if entry.answerable:
            rank = _first_relevant_rank(entry, entry_results)
            ranks_by_category[entry.category].append(rank)
            all_ranks.append(rank)
            if rank is None:
                misses.append(entry.id)
        else:
            flagged = not entry_results or entry_results[0].score < threshold
            flags.append(flagged)
            if not flagged:
                false_positives.append(entry.id)

    overall = _ranked_metrics(all_ranks) if all_ranks else {}
    if flags:
        overall[UNANSWERABLE_METRIC] = sum(flags) / len(flags)

    top_k_tokens = [sum(estimate_tokens(r.text) for r in rs) for rs in results.values()]
    return EvalReport(
        overall=overall,
        categories={c: _ranked_metrics(ranks) for c, ranks in sorted(ranks_by_category.items())},
        corpus_tokens=corpus_tokens,
        avg_top_k_tokens=sum(top_k_tokens) / len(top_k_tokens) if top_k_tokens else 0.0,
        unanswerable_false_positives=false_positives,
        misses_at_5=misses,
        top_scores=top_scores,
    )


def format_report(report: EvalReport) -> str:
    header = f"{'category':<18}" + "".join(f"{m:>13}" for m in RANKED_METRICS)
    lines = [header, "-" * len(header)]
    rows = [*report.categories.items(), ("OVERALL", report.overall)]
    for name, metrics in rows:
        lines.append(f"{name:<18}" + "".join(f"{metrics[m]:>13.3f}" for m in RANKED_METRICS))
    if UNANSWERABLE_METRIC in report.overall:
        lines.append(f"\nunanswerable accuracy: {report.overall[UNANSWERABLE_METRIC]:.3f}")
    lines.append(f"unanswerable false positives: {report.unanswerable_false_positives or 'none'}")
    lines.append(f"answerable misses (not in top 5): {report.misses_at_5 or 'none'}")
    # Top-1 score spread, for (re)tuning baseline.yaml's unanswerable_threshold.
    for answerable, label in ((False, "unanswerable"), (True, "answerable (lowest 10)")):
        scores = sorted((s, i) for i, (a, s) in report.top_scores.items() if a is answerable)
        shown = ", ".join(f"{i}={s:.4f}" for s, i in scores[:10])
        lines.append(f"top-1 scores, {label}: {shown or 'none'}")
    lines.append(
        f"tokens (~chars/4): full corpus {report.corpus_tokens}, "
        f"avg top-k {report.avg_top_k_tokens:.0f} "
        f"({report.avg_top_k_tokens / max(report.corpus_tokens, 1):.1%} of corpus)"
    )
    return "\n".join(lines)


def failures_against_baseline(report: EvalReport, floors: dict) -> list[str]:
    """List every metric below its floor, plus any reported metric that has no floor."""
    failures = []
    scopes = [("overall", report.overall, floors.get("overall", {}))]
    category_floors = floors.get("categories", {})
    scopes += [(c, m, category_floors.get(c, {})) for c, m in report.categories.items()]
    for scope, metrics, scope_floors in scopes:
        for metric, value in metrics.items():
            if metric not in scope_floors:
                failures.append(f"{scope}.{metric}: no floor in baseline.yaml")
            elif value < scope_floors[metric]:
                failures.append(f"{scope}.{metric}: {value:.3f} < floor {scope_floors[metric]}")
    return failures
