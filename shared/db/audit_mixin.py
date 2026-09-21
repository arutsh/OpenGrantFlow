# shared/db/audit_mixin.py
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, event, inspect

from shared.db.type_decorators import GUID
from shared.security.current_user_context import get_current_user_id


class AuditColumnsMixin:
    """created_at/updated_at/created_by/updated_by with no primary key —
    for models whose PK isn't named/shaped like AuditMixin's `id`."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), nullable=True)

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), nullable=True)


class AuditMixin(AuditColumnsMixin):
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=lambda: uuid.uuid4())


@event.listens_for(AuditColumnsMixin, "before_insert", propagate=True)
def _set_created_by_and_updated_by_on_insert(mapper, connection, target: AuditColumnsMixin) -> None:
    # updated_by stays NULL here so it can prove append-only rows were never modified.
    user_id = get_current_user_id()
    if user_id is not None:
        target.created_by = user_id


@event.listens_for(AuditColumnsMixin, "before_update", propagate=True)
def _set_updated_at_and_updated_by_on_update(mapper, connection, target: AuditColumnsMixin) -> None:
    # Skip relationship-only dirty state (e.g. a collection append) — only real column edits count.
    state = inspect(target)
    tracked_column_changed = any(
        state.attrs[attr.key].history.has_changes()
        for attr in mapper.column_attrs
        if attr.key not in ("updated_at", "updated_by")
    )
    if not tracked_column_changed:
        return

    target.updated_at = datetime.now(timezone.utc)
    user_id = get_current_user_id()
    if user_id is not None:
        target.updated_by = user_id
