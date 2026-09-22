"""Add created_at/updated_at/created_by/updated_by (audit-mixin-rollout-tier4, group 2)

Revision ID: 000016
Revises: 000015
Create Date: 2026-09-21 00:00:00.000000

"""

from typing import Sequence, Union

from shared.db.migration_helpers import add_audit_columns, drop_audit_columns

revision: str = "000016"
down_revision: Union[str, Sequence[str], None] = "000015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# donor_templates had no audit columns before — every AuditMixin column is new here.
_TABLES = ["donor_templates"]


def upgrade() -> None:
    for table in _TABLES:
        add_audit_columns(table)


def downgrade() -> None:
    for table in _TABLES:
        drop_audit_columns(table)
