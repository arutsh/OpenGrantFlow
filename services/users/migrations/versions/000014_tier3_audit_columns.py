"""Add created_by/updated_by (audit-mixin-rollout-tier3, group 4)

Revision ID: 000014
Revises: 000013
Create Date: 2026-09-21 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from shared.db.type_decorators import GUID

revision: str = "000014"
down_revision: Union[str, Sequence[str], None] = "000013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# table -> extra AuditMixin/AuditColumnsMixin columns it doesn't already have,
# beyond created_by/updated_by (added to every table below).
_EXTRA_COLUMNS = {
    "privileged_access_logs": ["updated_at"],
}


def _column(name: str) -> sa.Column:
    if name in ("created_at", "updated_at"):
        return sa.Column(name, sa.DateTime(timezone=True), nullable=True)
    return sa.Column(name, GUID(), nullable=True)


def upgrade() -> None:
    for table, extra in _EXTRA_COLUMNS.items():
        op.add_column(table, _column("created_by"))
        op.add_column(table, _column("updated_by"))
        for name in extra:
            op.add_column(table, _column(name))


def downgrade() -> None:
    for table, extra in _EXTRA_COLUMNS.items():
        op.drop_column(table, "created_by")
        op.drop_column(table, "updated_by")
        for name in extra:
            op.drop_column(table, name)
