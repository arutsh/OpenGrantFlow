import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.models.base import Base
from shared.db.audit_mixin import AuditMixin
import shared.db.type_decorators as t


class UserProviderKey(Base, AuditMixin):
    __tablename__ = "user_provider_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        t.GUID(), primary_key=True, default=lambda: uuid.uuid4()
    )
    user_id: Mapped[t.GUID] = mapped_column(t.GUID(), nullable=False, index=True)
    customer_id: Mapped[t.GUID | None] = mapped_column(t.GUID(), nullable=True, index=True)
    provider_id: Mapped[t.GUID] = mapped_column(
        t.GUID(), ForeignKey("ai_providers.id"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    encrypted_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    provider: Mapped["AIProvider"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "AIProvider", lazy="joined"
    )

    @property
    def resolved_model(self) -> str:
        """Return configured model or the enum default for the provider."""
        if self.model_name:
            return self.model_name
        from app.core.config import settings

        return settings.OLLAMA_MODEL
