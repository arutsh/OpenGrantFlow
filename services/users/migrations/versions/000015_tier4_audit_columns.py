"""Add created_at/updated_at/created_by/updated_by (audit-mixin-rollout-tier4, group 3)

Revision ID: 000015
Revises: 000014
Create Date: 2026-09-21 00:00:00.000000

"""

from typing import Sequence, Union

from shared.db.migration_helpers import add_audit_columns, drop_audit_columns

revision: str = "000015"
down_revision: Union[str, Sequence[str], None] = "000014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# customers/users had no audit columns before — every AuditMixin column is new here.
_TABLES = ["customers", "users"]


def upgrade() -> None:
    # ai/budget/chat reference users cross-database and stay unconstrained.
    for table in _TABLES:
        add_audit_columns(table, actor_table="users")


def downgrade() -> None:
    for table in _TABLES:
        drop_audit_columns(table)
