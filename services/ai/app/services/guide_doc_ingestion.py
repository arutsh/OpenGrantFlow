import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.site_chunk import SiteChunkModel
from app.services.site_chunk_sync import ChunkInput, sync_chunks

logger = get_logger(__name__)

H1_RE = re.compile(r"(?m)^# (?!#)(.+)$")
H2_RE = re.compile(r"(?m)^## (?!#)(.+)$")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9\s-]", "", text.lower())
    return re.sub(r"-+", "-", re.sub(r"\s+", "-", slug.strip())).strip("-")


def _split_h2(markdown: str) -> list[tuple[str, str]]:
    matches = list(H2_RE.finditer(markdown))
    sections = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections.append((match.group(1).strip(), markdown[start:end].strip()))
    return sections


def _chunks_for_doc(doc_slug: str, markdown: str) -> list[ChunkInput]:
    h1_match = H1_RE.search(markdown)
    page_title = h1_match.group(1).strip() if h1_match else doc_slug

    chunks = []
    for heading, body in _split_h2(markdown):
        heading_slug = _slugify(heading)
        if not heading_slug:
            logger.warning("guide_doc_heading_unsluggable", doc=doc_slug, heading=heading)
            continue
        chunks.append(
            ChunkInput(
                content_id=f"{doc_slug}.{heading_slug}",
                url=f"/guides/{doc_slug}#{heading_slug}",
                page_title=page_title,
                heading=heading,
                personas=[],
                text=f"{heading}\n\n{body}" if body else heading,
            )
        )
    return chunks


async def _indexed_doc_slugs(db: AsyncSession) -> set[str]:
    result = await db.execute(
        select(SiteChunkModel.content_id).where(SiteChunkModel.url.like("/guides/%"))
    )
    return {content_id.split(".", 1)[0] for content_id in result.scalars()}


async def ingest_guide_docs(db: AsyncSession, guide_docs_dir: Path, product_doc_path: Path) -> None:
    """Index docs/user-guide/*.md and docs/PRODUCT.md into site_chunks, one
    row per H2 section, pruning rows for sections no longer present."""
    paths = [p for p in sorted(guide_docs_dir.glob("*.md")) if p.name != "README.md"]
    if not paths:
        logger.error("guide_docs_dir_empty_skipping_sync", path=str(guide_docs_dir))
        return
    if product_doc_path.exists():
        paths.append(product_doc_path)

    chunks = []
    for path in paths:
        doc_slug = path.stem.lower()
        try:
            chunks.extend(_chunks_for_doc(doc_slug, path.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("guide_doc_parse_failed", path=str(path), error=str(exc))

    doc_slugs = {path.stem.lower() for path in paths} | await _indexed_doc_slugs(db)
    await sync_chunks(db, chunks, known_prefixes=sorted(doc_slugs))
