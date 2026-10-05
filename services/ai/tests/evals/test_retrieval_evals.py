"""Retrieval eval: golden-dataset checks, metric math, and the CI gate against baseline.yaml."""

from pathlib import Path

import pytest
import yaml

from app.core.config import settings
from app.models.site_chunk import SiteChunkModel
from app.services.guide_doc_ingestion import ingest_guide_docs, load_guide_chunks
from app.services.site_content_ingestion import ingest_site_content, load_site_chunks
from app.services.site_chunk_sync import ChunkInput
from app.services.site_retrieval import RetrievedChunk, retrieve
from tests.evals.retrieval_eval import (
    BASELINE_PATH,
    PERSONAS,
    GoldenEntry,
    compute_report,
    estimate_tokens,
    failures_against_baseline,
    format_report,
    load_dataset,
    validate_dataset,
)
from tests.postgres_schema import postgres_schema_session, requires_postgres


def _corpus() -> list[ChunkInput]:
    site = load_site_chunks(Path(settings.SITE_CONTENT_DIR))
    guides = load_guide_chunks(Path(settings.GUIDE_DOCS_DIR), Path(settings.PRODUCT_DOC_PATH))
    assert site and guides, "site-knowledge sources not found; check the *_DIR settings"
    return site + guides


def _entry(answerable: bool = True, expected: list[str] | None = None, **overrides):
    fields = dict(
        id="e1",
        question="q?",
        expected_content_ids=expected if expected is not None else (["a"] if answerable else []),
        persona=None,
        category="cat",
        answerable=answerable,
    )
    return GoldenEntry(**{**fields, **overrides})


def _hit(content_id: str, score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(content_id, "/u", "T", "H", [], "x" * 40, score)


def test_golden_dataset_is_valid_and_points_at_real_chunks():
    entries = load_dataset()
    validate_dataset(entries, known_ids={c.content_id for c in _corpus()})

    assert len(entries) >= 50
    assert PERSONAS <= {e.persona for e in entries}
    assert None in {e.persona for e in entries}
    assert any(not e.answerable for e in entries)


@pytest.mark.parametrize(
    "entry",
    [
        _entry(answerable=True, expected=[]),
        _entry(answerable=False, expected=["a"]),
        _entry(persona="admin"),
    ],
)
def test_validate_rejects_malformed_entries(entry):
    with pytest.raises(ValueError):
        validate_dataset([entry])


def test_validate_rejects_duplicate_ids():
    with pytest.raises(ValueError):
        validate_dataset([_entry(), _entry()])


def test_recall_and_mrr_use_first_relevant_rank():
    entries = [_entry(id="hit2"), _entry(id="miss")]
    results = {
        "hit2": [_hit("x"), _hit("a"), _hit("y")],
        "miss": [_hit("x")],
    }

    report = compute_report(entries, results, threshold=0.1, corpus_tokens=100)

    assert report.overall["recall_at_1"] == 0.0
    assert report.overall["recall_at_3"] == 0.5
    assert report.overall["mrr"] == pytest.approx(0.25)
    assert report.misses_at_5 == ["miss"]
    assert report.categories["cat"] == {k: report.overall[k] for k in report.categories["cat"]}


def test_unanswerable_accuracy_separates_correct_flags_from_false_positives():
    entries = [
        _entry(id="low", answerable=False),
        _entry(id="empty", answerable=False),
        _entry(id="high", answerable=False),
    ]
    results = {"low": [_hit("x", 0.05)], "empty": [], "high": [_hit("x", 0.1)]}

    report = compute_report(entries, results, threshold=0.1, corpus_tokens=100)

    assert report.overall == {"unanswerable_accuracy": pytest.approx(2 / 3)}
    assert report.unanswerable_false_positives == ["high"]


def test_baseline_gate_flags_metric_below_floor_and_missing_floor():
    report = compute_report([_entry()], {"e1": [_hit("a")]}, threshold=0.1, corpus_tokens=10)
    floors = {"overall": {"recall_at_1": 1.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 1.0}}

    assert failures_against_baseline(report, floors) == [
        "cat.recall_at_1: no floor in baseline.yaml",
        "cat.recall_at_3: no floor in baseline.yaml",
        "cat.recall_at_5: no floor in baseline.yaml",
        "cat.mrr: no floor in baseline.yaml",
    ]
    floors["overall"]["mrr"] = 1.1
    floors["categories"] = {"cat": floors["overall"]}
    assert failures_against_baseline(report, floors) == [
        "overall.mrr: 1.000 < floor 1.1",
        "cat.mrr: 1.000 < floor 1.1",
    ]


@requires_postgres
@pytest.mark.anyio
async def test_retrieval_meets_baseline():
    baseline = yaml.safe_load(BASELINE_PATH.read_text(encoding="utf-8"))
    entries = load_dataset()
    corpus = _corpus()

    async with postgres_schema_session("eval_retrieval", [SiteChunkModel.__table__]) as db:
        await ingest_site_content(db, Path(settings.SITE_CONTENT_DIR))
        await ingest_guide_docs(db, Path(settings.GUIDE_DOCS_DIR), Path(settings.PRODUCT_DOC_PATH))
        results = {
            e.id: await retrieve(db, e.question, top_k=baseline["top_k"], persona=e.persona)
            for e in entries
        }

    report = compute_report(
        entries,
        results,
        threshold=baseline["unanswerable_threshold"],
        corpus_tokens=sum(estimate_tokens(c.text) for c in corpus),
    )
    print("\n" + format_report(report))

    failures = failures_against_baseline(report, baseline["floors"])
    assert not failures, "retrieval regressed below baseline.yaml:\n" + "\n".join(failures)
