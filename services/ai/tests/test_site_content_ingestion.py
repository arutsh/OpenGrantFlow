"""Unit tests for the site-content ingester: publish/draft/update/delete."""

import gc
import textwrap
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.site_chunk import SiteChunkModel
from app.services.site_content_ingestion import ingest_site_content


def _write_section(directory: Path, filename: str, **frontmatter) -> None:
    body = frontmatter.pop("body", "")
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            rendered = "[" + ", ".join(value) + "]"
        else:
            rendered = value
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    if body:
        lines.append(body)
    (directory / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


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


@pytest.mark.anyio
async def test_published_section_indexed(db_session, tmp_path):
    _write_section(
        tmp_path, "mission.md",
        id="about.mission", page="about", anchor="mission", title="Mission",
        status="published", body="Our mission statement.",
    )

    await ingest_site_content(db_session, tmp_path)

    rows = await _all_chunks(db_session)
    assert len(rows) == 1
    assert rows[0].content_id == "about.mission"
    assert rows[0].url == "/about#mission"
    assert "Our mission statement." in rows[0].text


@pytest.mark.anyio
async def test_draft_section_excluded(db_session, tmp_path):
    _write_section(
        tmp_path, "draft.md",
        id="about.draft", page="about", anchor="draft", title="Draft",
        status="draft", body="Not confirmed yet.",
    )

    await ingest_site_content(db_session, tmp_path)

    assert await _all_chunks(db_session) == []


@pytest.mark.anyio
async def test_unchanged_content_not_rewritten(db_session, tmp_path):
    _write_section(
        tmp_path, "mission.md",
        id="about.mission", page="about", anchor="mission", title="Mission",
        status="published", body="Our mission statement.",
    )

    await ingest_site_content(db_session, tmp_path)
    first_version = (await _all_chunks(db_session))[0].content_version

    await ingest_site_content(db_session, tmp_path)
    second_version = (await _all_chunks(db_session))[0].content_version

    assert first_version == second_version


@pytest.mark.anyio
async def test_changed_wording_rewrites_version(db_session, tmp_path):
    _write_section(
        tmp_path, "mission.md",
        id="about.mission", page="about", anchor="mission", title="Mission",
        status="published", body="Our mission statement.",
    )
    await ingest_site_content(db_session, tmp_path)
    first_version = (await _all_chunks(db_session))[0].content_version

    _write_section(
        tmp_path, "mission.md",
        id="about.mission", page="about", anchor="mission", title="Mission",
        status="published", body="Our updated mission statement.",
    )
    await ingest_site_content(db_session, tmp_path)
    rows = await _all_chunks(db_session)

    assert len(rows) == 1
    assert rows[0].content_version != first_version
    assert "updated" in rows[0].text


@pytest.mark.anyio
async def test_unpublished_section_removed_from_index(db_session, tmp_path):
    _write_section(
        tmp_path, "mission.md",
        id="about.mission", page="about", anchor="mission", title="Mission",
        status="published", body="Our mission statement.",
    )
    await ingest_site_content(db_session, tmp_path)
    assert len(await _all_chunks(db_session)) == 1

    _write_section(
        tmp_path, "mission.md",
        id="about.mission", page="about", anchor="mission", title="Mission",
        status="draft", body="Our mission statement.",
    )
    await ingest_site_content(db_session, tmp_path)

    assert await _all_chunks(db_session) == []


@pytest.mark.anyio
async def test_deleted_file_removes_chunk(db_session, tmp_path):
    _write_section(
        tmp_path, "mission.md",
        id="about.mission", page="about", anchor="mission", title="Mission",
        status="published", body="Our mission statement.",
    )
    _write_section(
        tmp_path, "values.md",
        id="about.values", page="about", anchor="values", title="Values",
        status="published", body="Our values.",
    )
    await ingest_site_content(db_session, tmp_path)
    assert len(await _all_chunks(db_session)) == 2

    (tmp_path / "mission.md").unlink()
    await ingest_site_content(db_session, tmp_path)

    assert [row.content_id for row in await _all_chunks(db_session)] == ["about.values"]


@pytest.mark.anyio
async def test_items_and_personas_rendered(db_session, tmp_path):
    (tmp_path / "steps.md").write_text(
        textwrap.dedent(
            """\
            ---
            id: how-it-works.five-steps
            page: how-it-works
            anchor: five-steps
            title: Five steps
            status: published
            personas: [grantee, funder]
            items:
              - title: Budget
                body: Create a structured project budget.
            ---
            """
        ),
        encoding="utf-8",
    )

    await ingest_site_content(db_session, tmp_path)

    rows = await _all_chunks(db_session)
    assert len(rows) == 1
    assert rows[0].personas == ["grantee", "funder"]
    assert "Create a structured project budget." in rows[0].text


@pytest.mark.anyio
async def test_readme_is_ignored(db_session, tmp_path):
    (tmp_path / "README.md").write_text("# Not a section\n", encoding="utf-8")

    await ingest_site_content(db_session, tmp_path)

    assert await _all_chunks(db_session) == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value", "column", "expected"),
    [
        ("anchor", "our-mission", "url", "/about#our-mission"),
        ("personas", ["donor"], "personas", ["donor"]),
    ],
)
async def test_metadata_only_change_rewrites_row(
    db_session, tmp_path, field, value, column, expected
):
    section = dict(
        id="about.mission", page="about", anchor="mission", title="Mission",
        status="published", personas=["ngo"], body="Our mission statement.",
    )
    _write_section(tmp_path, "mission.md", **section)
    await ingest_site_content(db_session, tmp_path)

    _write_section(tmp_path, "mission.md", **{**section, field: value})
    await ingest_site_content(db_session, tmp_path)

    rows = await _all_chunks(db_session)
    assert len(rows) == 1
    assert getattr(rows[0], column) == expected


@pytest.mark.anyio
async def test_missing_content_dir_keeps_existing_index(db_session, tmp_path):
    _write_section(
        tmp_path, "mission.md",
        id="about.mission", page="about", anchor="mission", title="Mission",
        status="published", body="Our mission statement.",
    )
    await ingest_site_content(db_session, tmp_path)

    await ingest_site_content(db_session, tmp_path / "does-not-exist")

    assert [row.content_id for row in await _all_chunks(db_session)] == ["about.mission"]


@pytest.mark.anyio
async def test_id_not_matching_page_is_skipped(db_session, tmp_path):
    _write_section(
        tmp_path, "faq.md",
        id="faq.pricing", page="contact", anchor="pricing", title="Pricing",
        status="published", body="Free.",
    )

    await ingest_site_content(db_session, tmp_path)

    assert await _all_chunks(db_session) == []


@pytest.mark.anyio
async def test_duplicate_id_keeps_first_section(db_session, tmp_path):
    for filename, body in [("a.md", "First body."), ("b.md", "Second body.")]:
        _write_section(
            tmp_path, filename,
            id="about.mission", page="about", anchor="mission", title="Mission",
            status="published", body=body,
        )

    await ingest_site_content(db_session, tmp_path)

    rows = await _all_chunks(db_session)
    assert len(rows) == 1
    assert "First body." in rows[0].text
