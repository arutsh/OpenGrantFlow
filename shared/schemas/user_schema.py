from pydantic import BaseModel, ConfigDict, EmailStr
from shared.schemas.customer_schema import Customer
import enum
from uuid import UUID


class UserStatus(str, enum.Enum):
    active = "active"
    pending = "pending"
    disabled = "disabled"


class UserRole(str, enum.Enum):
    superuser = "superuser"
    admin = "admin"
    user = "user"


class UserBase(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr
    role: UserRole
    customer_id: UUID | None = None
    status: UserStatus


class UserSelfUpdate(BaseModel):
    # Forbid, not ignore: membership/role/status/email must fail loudly, never be dropped.
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = None
    last_name: str | None = None
    new_customer_name: str | None = None  # founder onboarding only, while pending


class User(UserBase):
    id: UUID
    customer: Customer | None = None
    email_verified: bool = False

    model_config = {"from_attributes": True}
