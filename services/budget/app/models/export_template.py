from __future__ import annotations
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SQLEnum,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.schemas.export_template_schema import TemplateVisibility
from app.utils.db import GUID
from shared.db.audit_mixin import AuditMixin


class ExportTemplateModel(Base, AuditMixin):
    __tablename__ = "export_templates"
    __table_args__ = (
        UniqueConstraint("owner_customer_id", "name"),
        Index(
            "uq_export_templates_single_system_default",
            "is_system_default",
            unique=True,
            postgresql_where=text("is_system_default"),
            sqlite_where=text("is_system_default"),
        ),
        CheckConstraint(
            "is_system_default = (owner_customer_id IS NULL)",
            name="ck_export_templates_system_default_has_no_owner",
        ),
    )

    is_system_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    owner_customer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    visibility: Mapped[TemplateVisibility] = mapped_column(
        SQLEnum(TemplateVisibility, name="export_template_visibility"),
        nullable=False,
        default=TemplateVisibility.private,
    )
    options: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
