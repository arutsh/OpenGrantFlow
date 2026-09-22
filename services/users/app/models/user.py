# /services/users/app/models/user.py
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum, text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.models.base import Base

# import enum
import uuid
from datetime import datetime
from app.utils.db import GUID
from shared.db.audit_mixin import AuditMixin
from shared.schemas.user_schema import UserStatus, UserRole


class UserModel(Base, AuditMixin):
    __tablename__ = "users"
    __audit_actor_table__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=lambda: uuid.uuid4(), nullable=False, index=True
    )

    # Name fields with default empty string
    first_name: Mapped[str] = mapped_column(String, nullable=False, server_default=text("''"))
    last_name: Mapped[str] = mapped_column(String, nullable=False, server_default=text("''"))

    # Email and role
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(String, nullable=False)

    # Password hash
    hashed_password: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # can be changed to nullable=False later

    # Foreign key to customers
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("customers.id"), nullable=True  # or UUID type if PostgreSQL
    )

    # Enum status with default
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus),
        nullable=False,
        default=UserStatus.pending,
        server_default=text(f"'{UserStatus.pending.value}'"),
    )
    # Email verification
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    email_verification_token_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Password reset (password-reset): dedicated pair, separate from email verification above.
    password_reset_token_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Rectification (data-subject-rights): a changed email is stored here,
    # unverified, until the verification link is followed — the old `email`
    # stays the account's active/login address until then (reuses the same
    # email_verification_token_hash/expires_at pair above).
    pending_email: Mapped[str | None] = mapped_column(String, nullable=True)

    # Consent (consent-management): nullable timestamp — presence = granted,
    # null = not granted/withdrawn. Current/last-known state only, no
    # separate history table (design.md decision 1).
    consent_data_processing_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_marketing_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Erasure (data-subject-rights): soft-delete + anonymization, not a hard
    # delete (design.md decision 2) — financial records' created_by/
    # updated_by references must not dangle.
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer = relationship("CustomerModel", lazy="joined", foreign_keys=[customer_id])
    sessions = relationship("SessionModel", back_populates="user", cascade="all, delete-orphan")
