import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import mapped_column, Mapped
from app.models.base import Base
from shared.db.audit_mixin import AuditMixin
import shared.db.type_decorators as t


class AIPrompt(Base, AuditMixin):
    __tablename__ = "ai_prompts"

    id: Mapped[uuid.UUID] = mapped_column(t.GUID(), primary_key=True, default=lambda: uuid.uuid4())
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_template: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
