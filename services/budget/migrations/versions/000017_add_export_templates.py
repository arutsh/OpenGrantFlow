"""Add export_templates table + seed system-default template (budget-feat-313-excel-export group 5)

Revision ID: 000017
Revises: 000016
Create Date: 2026-09-25 00:00:00.000000

"""

import json
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import shared.db.type_decorators

revision: str = "000017"
down_revision: Union[str, Sequence[str], None] = "000016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Reproduces group 1's fixed 3-sheet output exactly (design.md Decision 10).
_SYSTEM_DEFAULT_OPTIONS = {
    "sheets": ["original_budget", "dashboard", "expense_list"],
    "show_donor_currency_estimate": True,
    "column_labels": {},
    "show_audit_footer": True,
}
_SYSTEM_DEFAULT_NAME = "GrandFlow Default"


def upgrade() -> None:
    op.create_table(
        "export_templates",
        sa.Column("id", shared.db.type_decorators.GUID(), nullable=False),
        sa.Column("owner_customer_id", shared.db.type_decorators.GUID(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "visibility",
            sa.Enum("private", "shared_with_grantees", name="export_template_visibility"),
            nullable=False,
        ),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", shared.db.type_decorators.GUID(), nullable=True),
        sa.Column("updated_by", shared.db.type_decorators.GUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_customer_id", "name", name="uq_export_templates_owner_customer_id_name"
        ),
    )
    op.create_index(op.f("ix_export_templates_id"), "export_templates", ["id"], unique=False)

    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO export_templates
                (id, owner_customer_id, name, visibility, options, version, created_at)
            VALUES
                (:id, NULL, :name, 'private', :options, 1, :created_at)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "name": _SYSTEM_DEFAULT_NAME,
            "options": json.dumps(_SYSTEM_DEFAULT_OPTIONS),
            "created_at": datetime.now(timezone.utc),
        },
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_export_templates_id"), table_name="export_templates")
    op.drop_table("export_templates")
    sa.Enum(name="export_template_visibility").drop(op.get_bind(), checkfirst=True)
