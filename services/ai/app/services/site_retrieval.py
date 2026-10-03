from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Text, case, cast, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB, TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site_chunk import SiteChunkModel

Persona = Literal["grantee", "funder", "technical"]

TS_CONFIG = "english"
PERSONA_BOOST = 1.2


@dataclass
class RetrievedChunk:
    content_id: str
    url: str
    page_title: str
    heading: str
    personas: list[str]
    text: str
    score: float


def _any_term_query(query: str):
    # plainto_tsquery ANDs every lexeme; OR them so a question needn't contain all its words.
    and_query = cast(func.plainto_tsquery(TS_CONFIG, query), Text)
    return cast(func.replace(and_query, "&", "|"), TSQUERY)


async def retrieve(
    db: AsyncSession, query: str, top_k: int = 5, persona: Persona | None = None
) -> list[RetrievedChunk]:
    """Return up to `top_k` site chunks ranked by ts_rank_cd, persona-boosted when given."""
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    ts_query = _any_term_query(query)
    boost = (
        case(
            (cast(SiteChunkModel.personas, JSONB).contains([persona]), PERSONA_BOOST),
            else_=1.0,
        )
        if persona
        else literal(1.0)
    )
    score = (func.ts_rank_cd(SiteChunkModel.tsvector, ts_query) * boost).label("score")

    stmt = (
        select(SiteChunkModel, score)
        .where(SiteChunkModel.tsvector.op("@@")(ts_query))
        .order_by(score.desc(), SiteChunkModel.content_id)
        .limit(top_k)
    )
    rows = (await db.execute(stmt)).all()
    return [
        RetrievedChunk(
            content_id=chunk.content_id,
            url=chunk.url,
            page_title=chunk.page_title,
            heading=chunk.heading,
            personas=list(chunk.personas or []),
            text=chunk.text,
            score=float(row_score),
        )
        for chunk, row_score in rows
    ]
