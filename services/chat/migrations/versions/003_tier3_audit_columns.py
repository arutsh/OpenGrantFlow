"""Add created_by/updated_by (audit-mixin-rollout-tier3, group 2)

Revision ID: 003_tier3_audit_columns
Revises: 002_add_privileged_access_logs
Create Date: 2026-09-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from shared.db.type_decorators import GUID

revision: str = "003_tier3_audit_columns"
down_revision: Union[str, Sequence[str], None] = "002_add_privileged_access_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# None of these tables had updated_at before — every AuditMixin column is new here.
_TABLES = ["conversations", "messages", "privileged_access_logs"]


def _column(name: str) -> sa.Column:
    if name == "updated_at":
        return sa.Column(name, sa.DateTime(timezone=True), nullable=True)
    return sa.Column(name, GUID(), nullable=True)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, _column("created_by"))
        op.add_column(table, _column("updated_by"))
        op.add_column(table, _column("updated_at"))


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "updated_at")
        op.drop_column(table, "updated_by")
        op.drop_column(table, "created_by")
