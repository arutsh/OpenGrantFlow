import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column, validates
from app.models.base import Base
from app.utils.db import GUID
from shared.db.audit_mixin import AuditMixin


class CustomerModel(Base, AuditMixin):
    __tablename__ = "customers"
    __audit_actor_table__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        index=True,
        default=lambda: uuid.uuid4(),
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    is_ngo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_donor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    currency = mapped_column(String, nullable=False)
    # Deactivation (admin-management-page design.md decision 5): blocks
    # login/token-issuance for this company's users. Not a hard delete —
    # cross-service enforcement in budget/reports is a follow-on.
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    users = relationship(
        "UserModel", back_populates="customer", foreign_keys="UserModel.customer_id"
    )


class DonorGranteeModel(Base, AuditMixin):
    __tablename__ = "donor_grantees"

    __table_args__ = (
        UniqueConstraint("donor_id", "grantee_id", name="uq_donor_grantees_donor_id_grantee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        index=True,
        default=lambda: uuid.uuid4(),
    )
    donor_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("customers.id"), index=True)

    grantee_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("customers.id"), index=True)

    donor = relationship("CustomerModel", foreign_keys=[donor_id])
    grantee = relationship("CustomerModel", foreign_keys=[grantee_id])

    @validates("donor")
    def validate_donor(self, key, donor):
        if not donor.is_donor:
            raise ValueError("Customer has to be a donor")
        return donor

    @validates("grantee")
    def validate_grantee(self, key, grantee):
        if not grantee.is_ngo:
            raise ValueError("Customer has to be a grantee")
        return grantee
