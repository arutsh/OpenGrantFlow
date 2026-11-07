"""Derive budgets.total_amount from its lines instead of storing it

Revision ID: 000022
Revises: 000021
Create Date: 2026-11-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "000022"
down_revision: Union[str, Sequence[str], None] = "000021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_budget_lines_budget_id", "budget_lines", ["budget_id"])
    op.drop_column("budgets", "total_amount")


def downgrade() -> None:
    op.add_column(
        "budgets",
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=True, server_default=sa.text("0")),
    )
    op.execute(
        "UPDATE budgets SET total_amount = COALESCE("
        "(SELECT SUM(amount) FROM budget_lines WHERE budget_lines.budget_id = budgets.id), 0)"
    )
    op.drop_index("ix_budget_lines_budget_id", table_name="budget_lines")
