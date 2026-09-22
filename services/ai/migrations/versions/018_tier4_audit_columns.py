"""Add created_at/updated_at/created_by/updated_by (audit-mixin-rollout-tier4, group 1)

Revision ID: 018_tier4_audit_columns
Revises: 017_tier3_audit_columns
Create Date: 2026-09-21 00:00:00.000000

"""

from typing import Sequence, Union

from shared.db.migration_helpers import add_audit_columns, drop_audit_columns

revision: str = "018_tier4_audit_columns"
down_revision: Union[str, Sequence[str], None] = "017_tier3_audit_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# None of these tables had any audit columns before — every AuditMixin column is new here.
_TABLES = ["ai_providers", "ai_provider_models"]


def upgrade() -> None:
    for table in _TABLES:
        add_audit_columns(table)


def downgrade() -> None:
    for table in _TABLES:
        drop_audit_columns(table)
