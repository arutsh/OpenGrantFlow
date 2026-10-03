"""Unit tests for the guide-doc ingester: H2 chunking, slugs, and the
shared upsert/delete behaviour it feeds through sync_chunks."""

import gc
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.site_chunk import SiteChunkModel
from app.services.guide_doc_ingestion import ingest_guide_docs

NGO_GUIDE = """\
# For NGOs & Grantees

Intro paragraph, not its own chunk.

## 1. Your dashboard

Dashboard body text.

## 2. Creating a budget

Budget body text.
"""

DONOR_GUIDE = """\
# For Donors & Funders

## 1. Approving grantees

Approval body text.
"""


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[SiteChunkModel.__table__])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()
    # Forces a stale aiosqlite transport's finalizer to run now, on this
    # still-open loop, instead of later on a closed one from another test.
    gc.collect()


async def _all_chunks(db_session) -> list[SiteChunkModel]:
    result = await db_session.execute(select(SiteChunkModel))
    return list(result.scalars())


def _setup_docs(tmp_path: Path, product_body: str | None = None) -> tuple[Path, Path]:
    guide_dir = tmp_path / "user-guide"
    guide_dir.mkdir()
    (guide_dir / "ngo-guide.md").write_text(NGO_GUIDE, encoding="utf-8")
    (guide_dir / "donor-guide.md").write_text(DONOR_GUIDE, encoding="utf-8")
    (guide_dir / "README.md").write_text("# User guide index\n", encoding="utf-8")
    product_path = tmp_path / "PRODUCT.md"
    if product_body is not None:
        product_path.write_text(product_body, encoding="utf-8")
    return guide_dir, product_path


@pytest.mark.anyio
async def test_guide_doc_split_into_h2_chunks(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(tmp_path)

    await ingest_guide_docs(db_session, guide_dir, product_path)

    rows = {row.content_id: row for row in await _all_chunks(db_session)}
    assert rows.keys() == {
        "ngo-guide.1-your-dashboard",
        "ngo-guide.2-creating-a-budget",
        "donor-guide.1-approving-grantees",
    }
    dashboard = rows["ngo-guide.1-your-dashboard"]
    assert dashboard.url == "/guides/ngo-guide#1-your-dashboard"
    assert dashboard.page_title == "For NGOs & Grantees"
    assert dashboard.heading == "1. Your dashboard"
    assert "Dashboard body text." in dashboard.text
    assert dashboard.personas == []


@pytest.mark.anyio
async def test_intro_before_first_h2_is_not_its_own_chunk(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(tmp_path)

    await ingest_guide_docs(db_session, guide_dir, product_path)

    texts = [row.text for row in await _all_chunks(db_session)]
    assert not any("Intro paragraph, not its own chunk." in text for text in texts)


@pytest.mark.anyio
async def test_readme_in_guide_dir_is_ignored(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(tmp_path)

    await ingest_guide_docs(db_session, guide_dir, product_path)

    assert all(not row.content_id.startswith("readme.") for row in await _all_chunks(db_session))


@pytest.mark.anyio
async def test_missing_product_doc_is_skipped(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(tmp_path, product_body=None)
    assert not product_path.exists()

    await ingest_guide_docs(db_session, guide_dir, product_path)

    assert all(not row.content_id.startswith("product.") for row in await _all_chunks(db_session))


@pytest.mark.anyio
async def test_product_doc_indexed_when_present(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(
        tmp_path,
        product_body="# GrantFlow — Product Overview\n\n## The Problem\n\nProblem body.\n",
    )

    await ingest_guide_docs(db_session, guide_dir, product_path)

    rows = {row.content_id: row for row in await _all_chunks(db_session)}
    assert "product.the-problem" in rows
    assert rows["product.the-problem"].url == "/guides/product#the-problem"


@pytest.mark.anyio
async def test_unchanged_content_not_rewritten(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(tmp_path)

    await ingest_guide_docs(db_session, guide_dir, product_path)
    first = {r.content_id: r.content_version for r in await _all_chunks(db_session)}

    await ingest_guide_docs(db_session, guide_dir, product_path)
    second = {r.content_id: r.content_version for r in await _all_chunks(db_session)}

    assert first == second


@pytest.mark.anyio
async def test_removed_section_is_deleted(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(tmp_path)
    await ingest_guide_docs(db_session, guide_dir, product_path)
    assert len(await _all_chunks(db_session)) == 3

    (guide_dir / "ngo-guide.md").write_text(
        "# For NGOs & Grantees\n\n## 1. Your dashboard\n\nDashboard body text.\n",
        encoding="utf-8",
    )
    await ingest_guide_docs(db_session, guide_dir, product_path)

    rows = {row.content_id for row in await _all_chunks(db_session)}
    assert "ngo-guide.2-creating-a-budget" not in rows
    assert "ngo-guide.1-your-dashboard" in rows
    assert "donor-guide.1-approving-grantees" in rows


@pytest.mark.anyio
async def test_removed_section_in_new_guide_doc_is_deleted(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(tmp_path)
    admin_guide = guide_dir / "admin-guide.md"
    admin_guide.write_text("# Admins\n\n## Users\n\nA.\n\n## Roles\n\nB.\n", encoding="utf-8")
    await ingest_guide_docs(db_session, guide_dir, product_path)

    admin_guide.write_text("# Admins\n\n## Users\n\nA.\n", encoding="utf-8")
    await ingest_guide_docs(db_session, guide_dir, product_path)

    rows = {row.content_id for row in await _all_chunks(db_session)}
    assert "admin-guide.roles" not in rows
    assert "admin-guide.users" in rows


@pytest.mark.anyio
async def test_deleted_guide_doc_rows_are_deleted(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(tmp_path)
    admin_guide = guide_dir / "admin-guide.md"
    admin_guide.write_text("# Admins\n\n## Users\n\nA.\n", encoding="utf-8")
    await ingest_guide_docs(db_session, guide_dir, product_path)

    admin_guide.unlink()
    await ingest_guide_docs(db_session, guide_dir, product_path)

    rows = {row.content_id for row in await _all_chunks(db_session)}
    assert not any(content_id.startswith("admin-guide.") for content_id in rows)
    assert "ngo-guide.1-your-dashboard" in rows


@pytest.mark.anyio
async def test_missing_guide_dir_keeps_existing_index(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(tmp_path)
    await ingest_guide_docs(db_session, guide_dir, product_path)

    await ingest_guide_docs(db_session, tmp_path / "does-not-exist", product_path)

    assert len(await _all_chunks(db_session)) == 3


@pytest.mark.anyio
async def test_unsluggable_heading_is_skipped(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(tmp_path)
    (guide_dir / "ngo-guide.md").write_text("# NGOs\n\n## !!!\n\nBody.\n", encoding="utf-8")

    await ingest_guide_docs(db_session, guide_dir, product_path)

    rows = {row.content_id for row in await _all_chunks(db_session)}
    assert not any(content_id.startswith("ngo-guide.") for content_id in rows)


@pytest.mark.anyio
async def test_colliding_heading_slugs_keep_first_section(db_session, tmp_path):
    guide_dir, product_path = _setup_docs(tmp_path)
    (guide_dir / "ngo-guide.md").write_text(
        "# NGOs\n\n## Budgets\n\nFirst.\n\n## Budgets!\n\nSecond.\n", encoding="utf-8"
    )

    await ingest_guide_docs(db_session, guide_dir, product_path)

    rows = {row.content_id: row for row in await _all_chunks(db_session)}
    assert "First." in rows["ngo-guide.budgets"].text
