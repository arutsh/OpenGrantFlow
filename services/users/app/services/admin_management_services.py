from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.core.logging import get_logger
from app.crud.customer_crud import (
    deactivate_customer,
    get_customer,
    lock_customer_for_update,
    update_customer,
)
from app.crud.sessions_curd import revoke_all_sessions_for_user
from app.crud.user_crud import (
    count_admins,
    create_invited_user,
    get_user,
    soft_delete_user,
    update_user,
)
from shared.security.jwt_utils import REFRESH_TOKEN_EXPIRE_DAYS
from shared.security.session_revocation import mark_session_revoked

logger = get_logger(__name__)

COMPANY_UPDATE_FIELDS = {"name", "country", "currency", "is_ngo", "is_donor"}


def _require_company_admin(valid_user: dict) -> UUID:
    """An admin — real, or a superuser impersonating (impersonation tokens
    always carry role="admin", see design.md decision 2) — may act only
    within the company their token is scoped to. No superuser-specific
    branch exists here on purpose: a superuser must impersonate first."""
    if valid_user.get("role") != "admin":
        raise DomainError("Admin role required", status.HTTP_403_FORBIDDEN)
    customer_id = valid_user.get("customer_id")
    if not customer_id:
        raise DomainError("Admin has no associated company", status.HTTP_403_FORBIDDEN)
    return UUID(str(customer_id))


def _require_same_company(valid_user: dict, target_customer_id) -> UUID:
    own_customer_id = _require_company_admin(valid_user)
    if target_customer_id is None or str(own_customer_id) != str(target_customer_id):
        raise DomainError("Not authorized for this company", status.HTTP_403_FORBIDDEN)
    return own_customer_id


async def _revoke_user_sessions(session: AsyncSession, user_id: UUID) -> None:
    sessions = await revoke_all_sessions_for_user(session, user_id)
    for s in sessions:
        await mark_session_revoked(str(s.id), ttl_seconds=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)


async def invite_user_service(
    session: AsyncSession,
    valid_user: dict,
    *,
    email: str,
    first_name: str | None = "",
    last_name: str | None = "",
    role: str = "user",
):
    customer_id = _require_company_admin(valid_user)
    if role not in ("admin", "user"):
        raise DomainError("Cannot invite a user with that role", status.HTTP_400_BAD_REQUEST)

    try:
        return await create_invited_user(
            session,
            email=email,
            customer_id=customer_id,
            role=role,
            first_name=first_name,
            last_name=last_name,
        )
    except ValueError as e:
        raise DomainError(str(e), status.HTTP_400_BAD_REQUEST) from e


async def _get_active_target_user(session: AsyncSession, target_user_id: UUID):
    target = await get_user(session, target_user_id)
    if not target or target.deleted_at is not None:
        raise DomainError("User not found", status.HTTP_404_NOT_FOUND)
    return target


async def remove_user_service(session: AsyncSession, valid_user: dict, target_user_id: UUID):
    target = await _get_active_target_user(session, target_user_id)
    _require_same_company(valid_user, target.customer_id)

    # Held until this transaction commits/rolls back, so a concurrent
    # remove/demote for this company can't slip past the same check.
    await lock_customer_for_update(session, target.customer_id)
    remaining_admins = await count_admins(session, target.customer_id, exclude_user_id=target.id)
    if target.role == "admin" and remaining_admins == 0:
        raise DomainError("Cannot remove the last admin of a company", status.HTTP_400_BAD_REQUEST)

    await _revoke_user_sessions(session, target.id)
    return await soft_delete_user(session, target)


async def update_user_role_service(
    session: AsyncSession, valid_user: dict, target_user_id: UUID, new_role: str
):
    if new_role == "superuser":
        raise DomainError("Cannot grant superuser role", status.HTTP_400_BAD_REQUEST)
    if new_role not in ("admin", "user"):
        raise DomainError("Invalid role", status.HTTP_400_BAD_REQUEST)

    target = await _get_active_target_user(session, target_user_id)
    _require_same_company(valid_user, target.customer_id)

    await lock_customer_for_update(session, target.customer_id)
    if (
        target.role == "admin"
        and new_role != "admin"
        and await count_admins(session, target.customer_id, exclude_user_id=target.id) == 0
    ):
        raise DomainError("Cannot demote the last admin of a company", status.HTTP_400_BAD_REQUEST)

    # Otherwise a still-live token keeps its stale role claim.
    await _revoke_user_sessions(session, target.id)
    return await update_user(session, target, {"role": new_role})


async def get_company_service(session: AsyncSession, valid_user: dict, customer_id: UUID):
    _require_same_company(valid_user, customer_id)
    customer = await get_customer(session, customer_id)
    if not customer:
        raise DomainError("Customer not found", status.HTTP_404_NOT_FOUND)
    return customer


async def update_company_service(
    session: AsyncSession, valid_user: dict, customer_id: UUID, updates: dict
):
    _require_same_company(valid_user, customer_id)
    customer = await get_customer(session, customer_id)
    if not customer:
        raise DomainError("Customer not found", status.HTTP_404_NOT_FOUND)

    filtered = {k: v for k, v in updates.items() if k in COMPANY_UPDATE_FIELDS and v is not None}
    return await update_customer(session, customer, filtered)


async def deactivate_company_service(session: AsyncSession, valid_user: dict, customer_id: UUID):
    # Impersonation tokens are "admin of X" only; the stored superuser role never widens them.
    if valid_user.get("is_impersonating") is True:
        _require_same_company(valid_user, customer_id)
    elif valid_user.get("role") != "superuser":
        raise DomainError("Superuser role required", status.HTTP_403_FORBIDDEN)

    customer = await get_customer(session, customer_id)
    if not customer:
        raise DomainError("Customer not found", status.HTTP_404_NOT_FOUND)

    logger.info("company_deactivated", customer_id=str(customer_id))
    return await deactivate_customer(session, customer)
