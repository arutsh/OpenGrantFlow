import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import mapped_column, Mapped
from app.models.base import Base
from shared.db.audit_mixin import AuditMixin
import shared.db.type_decorators as t


class AIAuditLog(Base, AuditMixin):
    __tablename__ = "ai_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        t.GUID(), primary_key=True, default=lambda: uuid.uuid4()
    )
    customer_id: Mapped[t.GUID] = mapped_column(t.GUID(), nullable=False, index=True)
    user_id: Mapped[t.GUID] = mapped_column(t.GUID(), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False, default="")
    # "byok" (organization's own provider key) or "platform" (GrantFlow-funded
    # fallback, e.g. Excel import when no key is configured). Historical BYOK-only
    # rows predate this column and default to "byok" via server_default.
    funding_source: Mapped[str] = mapped_column(String, nullable=False, default="byok")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
