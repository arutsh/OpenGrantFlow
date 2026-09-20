from datetime import datetime

from sqlalchemy import Boolean, DateTime
from sqlalchemy.orm import mapped_column, Mapped

from app.models.base import Base
from shared.db.audit_mixin import AuditColumnsMixin
import shared.db.type_decorators as t


class CustomerAiDefaults(Base, AuditColumnsMixin):
    __tablename__ = "customer_ai_defaults"

    customer_id: Mapped[t.GUID] = mapped_column(t.GUID(), primary_key=True)
    platform_fallback_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
