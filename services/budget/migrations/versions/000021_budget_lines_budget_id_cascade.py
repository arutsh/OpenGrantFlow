"""Cascade-delete budget lines with their budget

Revision ID: 000021
Revises: 000020
Create Date: 2026-10-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "000021"
down_revision: Union[str, Sequence[str], None] = "000020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("budget_lines_budget_id_fkey", "budget_lines", type_="foreignkey")
    op.create_foreign_key(
        "budget_lines_budget_id_fkey",
        "budget_lines",
        "budgets",
        ["budget_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("budget_lines_budget_id_fkey", "budget_lines", type_="foreignkey")
    op.create_foreign_key(
        "budget_lines_budget_id_fkey", "budget_lines", "budgets", ["budget_id"], ["id"]
    )
