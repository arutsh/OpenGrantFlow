from sqlalchemy import Computed, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.sql.expression import FunctionElement
from sqlalchemy.types import TypeDecorator

from app.models.base import Base
from shared.db.audit_mixin import AuditMixin


class TSVectorType(TypeDecorator):
    """TSVECTOR on Postgres; plain TEXT elsewhere so sqlite-backed tests can
    create this table without a real full-text engine."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(TSVECTOR())
        return dialect.type_descriptor(Text())


class _SiteChunkTsvector(FunctionElement):
    name = "site_chunk_tsvector"
    inherit_cache = True


@compiles(_SiteChunkTsvector, "postgresql")
def _compile_tsvector_postgresql(element, compiler, **kw):
    return "to_tsvector('english', text)"


@compiles(_SiteChunkTsvector)
def _compile_tsvector_fallback(element, compiler, **kw):
    # Non-Postgres dialects (sqlite in tests) have no to_tsvector(); the
    # retriever only ever runs against Postgres, so this value is unused.
    return "text"


class SiteChunkModel(Base, AuditMixin):
    """One row per retrievable section of site-content or guide-doc text,
    keyed by content_id — see site-knowledge-index spec."""

    __tablename__ = "site_chunks"
    __table_args__ = (UniqueConstraint("content_id", name="uq_site_chunks_content_id"),)

    content_id: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    page_title: Mapped[str] = mapped_column(String, nullable=False)
    heading: Mapped[str] = mapped_column(String, nullable=False)
    personas: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_version: Mapped[str] = mapped_column(String, nullable=False)
    tsvector: Mapped[str | None] = mapped_column(
        TSVectorType(), Computed(_SiteChunkTsvector(), persisted=True)
    )
