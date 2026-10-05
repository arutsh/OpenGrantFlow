"""Real-Postgres tests for site retrieval: ts_rank_cd ranking, top_k bound, persona boost."""

import pytest

from app.models.site_chunk import SiteChunkModel
from app.services.site_retrieval import retrieve
from tests.postgres_schema import postgres_schema_session, requires_postgres

pytestmark = requires_postgres


@pytest.fixture
async def db_session():
    async with postgres_schema_session(
        "test_site_retrieval", [SiteChunkModel.__table__]
    ) as session:
        yield session


def _chunk(content_id: str, body: str, personas: list[str] | None = None) -> SiteChunkModel:
    return SiteChunkModel(
        content_id=content_id,
        url=f"/test#{content_id}",
        page_title="Test",
        heading=content_id,
        personas=personas or [],
        text=body,
        content_version="v1",
    )


async def _seed(db_session, *chunks: SiteChunkModel) -> None:
    db_session.add_all(chunks)
    await db_session.commit()


@pytest.mark.anyio
async def test_matching_chunk_ranks_above_non_matching(db_session):
    await _seed(
        db_session,
        _chunk("a.export", "Export your budget to an Excel spreadsheet."),
        _chunk("b.security", "Data is encrypted at rest and in transit."),
    )

    results = await retrieve(db_session, "How do I export a budget to Excel?")

    assert [r.content_id for r in results] == ["a.export"]


@pytest.mark.anyio
async def test_denser_match_ranks_first(db_session):
    await _seed(
        db_session,
        _chunk("a.partial", "Budgets can be shared with colleagues."),
        _chunk("b.full", "Export a budget to Excel: the budget export keeps every line."),
    )

    results = await retrieve(db_session, "export budget excel")

    assert [r.content_id for r in results] == ["b.full", "a.partial"]
    assert results[0].score > results[1].score


@pytest.mark.anyio
async def test_question_need_not_contain_every_word(db_session):
    await _seed(db_session, _chunk("a.reports", "Submit a financial report to your funder."))

    results = await retrieve(db_session, "Where do I submit quarterly financial reports?")

    assert [r.content_id for r in results] == ["a.reports"]


@pytest.mark.anyio
async def test_no_matching_chunks_returns_empty(db_session):
    await _seed(db_session, _chunk("a.export", "Export your budget to Excel."))

    assert await retrieve(db_session, "kangaroo telescope") == []


@pytest.mark.anyio
async def test_stopword_only_query_returns_empty(db_session):
    await _seed(db_session, _chunk("a.export", "Export your budget to Excel."))

    assert await retrieve(db_session, "how do I") == []


@pytest.mark.anyio
async def test_top_k_bounds_results(db_session):
    await _seed(db_session, *(_chunk(f"c.{i}", f"Budget line number {i}.") for i in range(6)))

    results = await retrieve(db_session, "budget", top_k=3)

    assert len(results) == 3


@pytest.mark.anyio
async def test_top_k_below_one_rejected(db_session):
    with pytest.raises(ValueError):
        await retrieve(db_session, "budget", top_k=0)


@pytest.mark.anyio
async def test_result_carries_provenance(db_session):
    await _seed(db_session, _chunk("a.export", "Export your budget to Excel.", ["grantee"]))

    [result] = await retrieve(db_session, "export")

    assert result.url == "/test#a.export"
    assert result.personas == ["grantee"]
    assert "Excel" in result.text


@pytest.mark.anyio
async def test_persona_matching_chunk_outranks_equal_untagged_chunk(db_session):
    body = "Track spending against each budget line."
    await _seed(
        db_session,
        _chunk("a.untagged", body),
        _chunk("z.grantee", body, ["grantee"]),
    )

    results = await retrieve(db_session, "track budget spending", persona="grantee")

    assert [r.content_id for r in results] == ["z.grantee", "a.untagged"]
    assert results[0].score == pytest.approx(results[1].score * 1.2)


@pytest.mark.anyio
async def test_persona_boost_does_not_exclude_other_chunks(db_session):
    body = "Track spending against each budget line."
    await _seed(
        db_session,
        _chunk("a.funder", body, ["funder"]),
        _chunk("b.untagged", body),
    )

    results = await retrieve(db_session, "track budget spending", persona="grantee")

    assert {r.content_id for r in results} == {"a.funder", "b.untagged"}
    assert results[0].score == results[1].score


@pytest.mark.anyio
async def test_no_persona_applies_no_boost(db_session):
    body = "Track spending against each budget line."
    await _seed(
        db_session,
        _chunk("a.untagged", body),
        _chunk("z.grantee", body, ["grantee"]),
    )

    results = await retrieve(db_session, "track budget spending")

    assert [r.content_id for r in results] == ["a.untagged", "z.grantee"]
    assert results[0].score == results[1].score
