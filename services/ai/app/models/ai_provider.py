from sqlalchemy import Boolean, String
from sqlalchemy.orm import mapped_column, Mapped

from app.models.base import Base
from shared.db.audit_mixin import AuditMixin


class AIProvider(Base, AuditMixin):
    __tablename__ = "ai_providers"

    name: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    key_prefix: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
