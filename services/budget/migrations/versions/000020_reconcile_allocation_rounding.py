"""Reconcile report-line-conversion allocations that rounding pushed over
their report-line or currency-conversion cap

Revision ID: 000020
Revises: 000019
Create Date: 2026-09-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "000020"
down_revision: Union[str, Sequence[str], None] = "000019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Independent rounding in 000019 can push an allocation group's sum past its cap; claw the
    # excess back from each group's largest row so it never exceeds the expense or the lot.
    for group_column, cap_table, cap_column in (
        ("report_line_id", "report_lines", "amount"),
        ("conversion_id", "currency_conversions", "local_amount"),
    ):
        op.execute(
            f"""
            WITH totals AS (
                SELECT a.{group_column} AS group_id, SUM(a.amount_allocated) AS allocated_total
                FROM report_line_conversion_allocations a
                GROUP BY a.{group_column}
            ),
            overage AS (
                SELECT t.group_id, t.allocated_total - cap.{cap_column} AS excess
                FROM totals t
                JOIN {cap_table} cap ON cap.id = t.group_id
                WHERE t.allocated_total > cap.{cap_column}
            ),
            target AS (
                SELECT DISTINCT ON (a.{group_column}) a.id, o.excess
                FROM report_line_conversion_allocations a
                JOIN overage o ON o.group_id = a.{group_column}
                ORDER BY a.{group_column}, a.amount_allocated DESC, a.id
            )
            UPDATE report_line_conversion_allocations a
            SET amount_allocated = a.amount_allocated - target.excess
            FROM target
            WHERE a.id = target.id
            """
        )


def downgrade() -> None:
    # Data reconciliation only; the pre-images of the adjusted rows aren't retained.
    pass
