from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped

from app.models.base import Base
from shared.db.audit_mixin import AuditMixin
import shared.db.type_decorators as t


class AIProviderModel(Base, AuditMixin):
    """Catalog of models valid for a given provider — keeps a model like
    claude-haiku-4-5 from being selectable against provider ollama."""

    __tablename__ = "ai_provider_models"
    __table_args__ = (
        UniqueConstraint("provider_id", "name", name="uq_ai_provider_models_provider_name"),
    )

    provider_id: Mapped[t.GUID] = mapped_column(
        t.GUID(), ForeignKey("ai_providers.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
