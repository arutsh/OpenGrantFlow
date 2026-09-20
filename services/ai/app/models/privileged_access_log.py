import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from shared.db.audit_mixin import AuditMixin
import shared.db.type_decorators as t


class PrivilegedAccessLog(Base, AuditMixin):
    """Append-only — no update/delete path exists anywhere in the app."""

    __tablename__ = "privileged_access_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        t.GUID(), primary_key=True, default=lambda: uuid.uuid4()
    )
    actor_user_id: Mapped[t.GUID] = mapped_column(t.GUID(), nullable=False, index=True)
    customer_id: Mapped[t.GUID] = mapped_column(t.GUID(), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
