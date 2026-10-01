"""Convert money and rate columns from double precision to exact numeric

Revision ID: 000019
Revises: 000018
Create Date: 2026-09-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "000019"
down_revision: Union[str, Sequence[str], None] = "000018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, precision, scale)
COLUMNS = [
    ("budgets", "total_amount", 18, 4),
    ("budgets", "donor_total_amount", 18, 4),
    ("budgets", "estimated_exchange_rate", 20, 10),
    ("budget_lines", "amount", 18, 4),
    ("report_lines", "amount", 18, 4),
    ("funding_receipts", "amount", 18, 4),
    ("currency_conversions", "donor_amount", 18, 4),
    ("currency_conversions", "local_amount", 18, 4),
    ("report_line_conversion_allocations", "amount_allocated", 18, 4),
]


def upgrade() -> None:
    for table, column, precision, scale in COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE numeric({precision}, {scale}) USING round({column}::numeric, {scale})"
        )
    # Rounding lines individually can shift their sum, so totals are rebuilt from lines.
    op.execute(
        "UPDATE budgets SET total_amount = ("
        "SELECT COALESCE(SUM(budget_lines.amount), 0) FROM budget_lines "
        "WHERE budget_lines.budget_id = budgets.id)"
    )


def downgrade() -> None:
    for table, column, _precision, _scale in COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE double precision USING {column}::double precision"
        )
