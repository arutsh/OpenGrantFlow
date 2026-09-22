"""Reusable Alembic ops for adding AuditColumnsMixin's columns to a table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from shared.db.type_decorators import GUID


def add_audit_columns(table: str, *, actor_table: str | None = None) -> None:
    """Add created_at/updated_at/created_by/updated_by, matching AuditColumnsMixin's
    typing. Pass actor_table to FK created_by/updated_by to it — same-database only."""
    op.add_column(
        table,
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(table, sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("created_by", GUID(), nullable=True))
    op.add_column(table, sa.Column("updated_by", GUID(), nullable=True))
    if actor_table:
        op.create_foreign_key(
            f"fk_{table}_created_by_{actor_table}",
            table,
            actor_table,
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            f"fk_{table}_updated_by_{actor_table}",
            table,
            actor_table,
            ["updated_by"],
            ["id"],
            ondelete="SET NULL",
        )


def drop_audit_columns(table: str) -> None:
    """Drop created_at/updated_at/created_by/updated_by, discovering any FK
    constraints on created_by/updated_by via inspection instead of an actor_table arg."""
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(table):
        if set(fk["constrained_columns"]) & {"created_by", "updated_by"}:
            op.drop_constraint(fk["name"], table, type_="foreignkey")
    op.drop_column(table, "updated_by")
    op.drop_column(table, "created_by")
    op.drop_column(table, "updated_at")
    op.drop_column(table, "created_at")
