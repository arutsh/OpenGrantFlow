import uuid
from datetime import datetime
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import mapped_column, Mapped
from app.models.base import Base
from shared.db.audit_mixin import AuditMixin
import shared.db.type_decorators as t


class Conversation(Base, AuditMixin):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(t.GUID(), primary_key=True, default=lambda: uuid.uuid4())
    customer_id: Mapped[t.GUID] = mapped_column(t.GUID(), nullable=False, index=True)
    user_id: Mapped[t.GUID] = mapped_column(t.GUID(), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
