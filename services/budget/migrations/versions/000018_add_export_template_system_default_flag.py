"""Add export_templates.is_system_default with single-default and owner constraints

Revision ID: 000018
Revises: 000017
Create Date: 2026-09-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "000018"
down_revision: Union[str, Sequence[str], None] = "000017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "export_templates",
        sa.Column(
            "is_system_default", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.execute(
        "UPDATE export_templates SET is_system_default = true WHERE owner_customer_id IS NULL"
    )
    op.create_check_constraint(
        "ck_export_templates_system_default_has_no_owner",
        "export_templates",
        "is_system_default = (owner_customer_id IS NULL)",
    )
    op.create_index(
        "uq_export_templates_single_system_default",
        "export_templates",
        ["is_system_default"],
        unique=True,
        postgresql_where=sa.text("is_system_default"),
    )


def downgrade() -> None:
    op.drop_index("uq_export_templates_single_system_default", table_name="export_templates")
    op.drop_constraint(
        "ck_export_templates_system_default_has_no_owner", "export_templates", type_="check"
    )
    op.drop_column("export_templates", "is_system_default")
