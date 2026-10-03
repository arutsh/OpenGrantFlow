import re
from pathlib import Path

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.site_chunk_sync import ChunkInput, sync_chunks

logger = get_logger(__name__)

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)

PAGE_ROUTES = {
    "home": "/",
    "how-it-works": "/how-it-works",
    "security": "/security",
    "about": "/about",
    "contact": "/contact",
    "legal": "/legal",
}

PAGE_TITLES = {
    "home": "Home",
    "how-it-works": "How it works",
    "security": "Security & data",
    "about": "About",
    "contact": "Contact",
    "legal": "Legal",
}


def _parse_file(path: Path) -> dict | None:
    match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        return None
    frontmatter = yaml.safe_load(match.group(1)) or {}
    frontmatter["body"] = match.group(2).strip()
    return frontmatter


def _render_text(title: str, body: str, items: list[dict] | None) -> str:
    parts = [title]
    if body:
        parts.append(body)
    for item in items or []:
        head = item.get("title") or item.get("quote") or ""
        tail = item.get("body") or item.get("attribution") or ""
        parts.append(f"{head}: {tail}" if tail else head)
    return "\n\n".join(part for part in parts if part)


def _to_chunk(frontmatter: dict) -> ChunkInput | None:
    page = frontmatter.get("page")
    if frontmatter.get("status") != "published" or page not in PAGE_ROUTES:
        return None
    if not str(frontmatter["id"]).startswith(f"{page}."):
        raise ValueError(f"id {frontmatter['id']!r} must start with '{page}.'")
    anchor = frontmatter["anchor"]
    return ChunkInput(
        content_id=frontmatter["id"],
        url=f"{PAGE_ROUTES[page]}#{anchor}",
        page_title=PAGE_TITLES[page],
        heading=frontmatter["title"],
        personas=frontmatter.get("personas") or [],
        text=_render_text(
            frontmatter["title"], frontmatter.get("body", ""), frontmatter.get("items")
        ),
    )


async def ingest_site_content(db: AsyncSession, content_dir: Path) -> None:
    """Index published sections under `content_dir` into site_chunks,
    pruning rows for sections that are no longer published."""
    paths = [p for p in sorted(content_dir.rglob("*.md")) if p.name != "README.md"]
    if not paths:
        logger.error("site_content_dir_empty_skipping_sync", path=str(content_dir))
        return

    chunks = []
    for path in paths:
        try:
            frontmatter = _parse_file(path)
            chunk = _to_chunk(frontmatter) if frontmatter is not None else None
        except Exception as exc:
            logger.warning("site_content_parse_failed", path=str(path), error=str(exc))
            continue
        if chunk is not None:
            chunks.append(chunk)

    await sync_chunks(db, chunks, known_prefixes=list(PAGE_ROUTES))
