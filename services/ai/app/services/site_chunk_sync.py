import hashlib
import json
from dataclasses import asdict, dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.site_chunk import SiteChunkModel

logger = get_logger(__name__)


@dataclass
class ChunkInput:
    content_id: str
    url: str
    page_title: str
    heading: str
    personas: list[str]
    text: str


def _content_version(chunk: ChunkInput) -> str:
    payload = json.dumps(asdict(chunk), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def sync_chunks(
    db: AsyncSession, chunks: list[ChunkInput], known_prefixes: list[str]
) -> None:
    """Upsert `chunks` by content_id (rewriting only when any field changes),
    then delete stale rows whose content_id starts with `known_prefixes`."""
    unique: dict[str, ChunkInput] = {}
    for chunk in chunks:
        if chunk.content_id in unique:
            logger.error("site_chunk_duplicate_content_id", content_id=chunk.content_id)
            continue
        unique[chunk.content_id] = chunk
    valid_ids = set(unique)

    for chunk in unique.values():
        version = _content_version(chunk)
        existing = (
            await db.execute(
                select(SiteChunkModel).where(SiteChunkModel.content_id == chunk.content_id)
            )
        ).scalar_one_or_none()

        if existing is None:
            db.add(
                SiteChunkModel(
                    content_id=chunk.content_id,
                    url=chunk.url,
                    page_title=chunk.page_title,
                    heading=chunk.heading,
                    personas=chunk.personas,
                    text=chunk.text,
                    content_version=version,
                )
            )
        elif existing.content_version != version:
            existing.url = chunk.url
            existing.page_title = chunk.page_title
            existing.heading = chunk.heading
            existing.personas = chunk.personas
            existing.text = chunk.text
            existing.content_version = version

    if known_prefixes:
        candidates = (
            await db.execute(
                select(SiteChunkModel).where(
                    or_(*(SiteChunkModel.content_id.like(f"{p}.%") for p in known_prefixes))
                )
            )
        ).scalars()
        for row in candidates:
            if row.content_id not in valid_ids:
                await db.delete(row)

    await db.commit()
