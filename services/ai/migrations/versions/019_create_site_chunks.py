"""Create site_chunks — retrievable index of site-content and guide-doc
text, with a generated tsvector column and GIN index for full-text search
(site-assistant-retrieval-evals, group 1)

Revision ID: 019_create_site_chunks
Revises: 018_tier4_audit_columns
Create Date: 2026-10-02 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

from shared.db.type_decorators import GUID

revision: str = "019_create_site_chunks"
down_revision: Union[str, Sequence[str], None] = "018_tier4_audit_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "site_chunks",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("content_id", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("page_title", sa.String(), nullable=False),
        sa.Column("heading", sa.String(), nullable=False),
        sa.Column("personas", sa.JSON(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_version", sa.String(), nullable=False),
        sa.Column(
            "tsvector",
            TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", GUID(), nullable=True),
        sa.Column("updated_by", GUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_id", name="uq_site_chunks_content_id"),
    )
    op.create_index(
        "ix_site_chunks_tsvector",
        "site_chunks",
        ["tsvector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_site_chunks_tsvector", table_name="site_chunks")
    op.drop_table("site_chunks")
