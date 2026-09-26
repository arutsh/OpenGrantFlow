from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.schemas.user_schema import User, UserSelfUpdate
from app.schemas.consent_schema import ConsentState, ConsentUpdateRequest, EmailChangeRequest
from app.schemas.admin_management_schema import (
    AcceptInviteRequest,
    AcceptInviteResponse,
    InviteUserRequest,
    InviteUserResponse,
    RoleUpdateRequest,
)
from app.models.user import UserModel
from app.db.session import get_db
from app.crud.user_crud import (
    build_users_select,
    update_user,
    get_user,
    get_consent_state,
    set_marketing_consent,
    soft_delete_user,
    set_pending_email_verification_token,
    get_user_by_verification_token,
    accept_invite,
)
from app.crud.customer_crud import create_customer, get_customer
from app.crud.sessions_curd import revoke_all_sessions_for_user
from app.services.admin_management_services import (
    invite_user_service,
    remove_user_service,
    update_user_role_service,
)
from app.services.budget_client import get_financial_record_refs
from app.services.celery_client import enqueue_verification_email, enqueue_invite_email
from shared.security.dependencies import get_validated_user
from shared.security.jwt_utils import REFRESH_TOKEN_EXPIRE_DAYS
from shared.security.session_revocation import mark_session_revoked
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

router = APIRouter()


@router.get("/users/{user_id}", response_model=User)
async def get_user_endpoint(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/", response_model=list[User])
async def list_users_endpoint(
    db: AsyncSession = Depends(get_db), valid_user: dict = Depends(get_validated_user)
):
    # Superuser (not impersonating) lists everyone; an admin — real, or a
    # superuser impersonating (impersonation tokens carry role="admin" plus
    # the target customer_id, see design.md decision 2) — lists their own
    # company's users only, for the Company Management page. Trusting the
    # JWT claims here (not a DB self-lookup) is what makes this scope
    # correctly under impersonation: the real superuser's own DB row has no
    # bearing on which company they're currently acting as.
    stmt = build_users_select()
    if valid_user.get("role") == "superuser":
        result = await db.execute(stmt.where(UserModel.deleted_at.is_(None)))
        return list(result.scalars().all())
    if valid_user.get("role") == "admin" and valid_user.get("customer_id"):
        result = await db.execute(
            stmt.where(UserModel.customer_id == valid_user["customer_id"]).where(
                UserModel.deleted_at.is_(None)
            )
        )
        return list(result.scalars().all())
    raise HTTPException(status_code=403, detail="Not authorized to list users")


@router.post("/users/by_ids/", response_model=list[User])
async def get_users_by_ids_endpoint(
    user_ids: list[UUID],
    db: AsyncSession = Depends(get_db),
):
    # NOTE: this end point is for internal service use only,
    # hence no need to check current_user permissions
    # calling service should ensure proper authorization

    result = await db.execute(build_users_select(user_ids))
    return list(result.scalars().all())


@router.patch("/users/{user_id}/", response_model=User)
async def update_user_endpoint(
    user_id: UUID,
    user_update: UserSelfUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_validated_user),
):
    # Self-only, even for superusers: cross-user edits belong to audited superuser endpoints.
    if str(current_user["user_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to update this user")

    db_user = await get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # exclude_unset: an omitted field must never overwrite (e.g. wipe customer_id).
    update_data = user_update.model_dump(exclude_unset=True, exclude={"new_customer_name"})
    customer = None
    if (
        user_update.new_customer_name
        and db_user.status == "pending"
        and db_user.customer_id is None
    ):
        customer = await create_customer(db, user_update.new_customer_name)
        update_data.update(status="active", role="admin", customer_id=customer.id)

    await update_user(db, db_user, update_data)
    if customer is not None:
        # expire_on_commit=False keeps the pre-commit relationship; sync it explicitly.
        db_user.customer = customer

    return db_user


@router.get("/users/me/consent", response_model=ConsentState)
async def get_my_consent(
    current_user: dict = Depends(get_validated_user), db: AsyncSession = Depends(get_db)
):
    user = await get_user(db, current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return ConsentState(**get_consent_state(user))


@router.patch("/users/me/consent", response_model=ConsentState)
async def update_my_consent(
    req: ConsentUpdateRequest,
    current_user: dict = Depends(get_validated_user),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user(db, current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await set_marketing_consent(db, user, req.marketing)
    return ConsentState(**get_consent_state(user))


@router.get("/users/me/export")
async def export_my_data(
    current_user: dict = Depends(get_validated_user), db: AsyncSession = Depends(get_db)
):
    """Right to access (data-subject-rights spec): a downloadable, machine
    readable bundle of profile data, consent history, and a listing of the
    financial records the user created. Synchronous — orgs on this
    platform are small enough that this doesn't need async/email delivery
    (see design.md's open question; revisit if that stops being true)."""
    user = await get_user(db, current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    financial_records = await get_financial_record_refs(str(user.id), current_user["token"])

    return {
        "profile": {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "status": user.status,
            "email_verified": user.email_verified,
        },
        "consent": get_consent_state(user),
        "financial_records_created": financial_records,
    }


@router.post("/users/me/email")
async def request_email_change(
    req: EmailChangeRequest,
    current_user: dict = Depends(get_validated_user),
    db: AsyncSession = Depends(get_db),
):
    """Rectification (data-subject-rights spec): the new address is stored
    unverified; the account keeps logging in with the old address until the
    verification link (same /auth/verify-email endpoint used at signup) is
    followed."""
    user = await get_user(db, current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.email_verified:
        # Otherwise this would overwrite the still-pending signup verification token.
        raise HTTPException(
            status_code=400,
            detail="Verify your current email address before requesting a change",
        )

    try:
        raw_token = await set_pending_email_verification_token(db, user, req.new_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        enqueue_verification_email(req.new_email, raw_token, user.first_name)
    except Exception:
        logger.exception("email_change_verification_enqueue_failed", user_id=str(user.id))

    debug_token = raw_token if settings.EXPOSE_VERIFICATION_TOKEN_FOR_TESTS else None
    return {"pending_email": req.new_email, "debug_token": debug_token}


@router.post("/users/invite", response_model=InviteUserResponse)
async def invite_user_endpoint(
    req: InviteUserRequest,
    db: AsyncSession = Depends(get_db),
    valid_user: dict = Depends(get_validated_user),
):
    user, raw_token = await invite_user_service(
        db,
        valid_user,
        email=req.email,
        first_name=req.first_name,
        last_name=req.last_name,
        role=req.role,
    )

    inviter = await get_user(db, valid_user["user_id"])
    inviter_name = (
        f"{inviter.first_name or ''} {inviter.last_name or ''}".strip() or inviter.email
        if inviter
        else ""
    )
    company = await get_customer(db, user.customer_id)
    try:
        enqueue_invite_email(
            user.email,
            raw_token,
            user.first_name,
            inviter_name=inviter_name,
            company_name=company.name if company else "",
        )
    except Exception:
        logger.exception("invite_email_enqueue_failed", user_id=str(user.id))

    debug_token = raw_token if settings.EXPOSE_VERIFICATION_TOKEN_FOR_TESTS else None
    return InviteUserResponse(
        user_id=str(user.id), email=user.email, status=user.status, debug_token=debug_token
    )


@router.post("/users/accept-invite", response_model=AcceptInviteResponse)
async def accept_invite_endpoint(req: AcceptInviteRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_verification_token(db, req.email, req.token)
    expires_at = user.email_verification_expires_at if user else None
    if (
        not user
        or user.hashed_password is not None
        or not expires_at
        or expires_at.replace(tzinfo=ZoneInfo("UTC")) < datetime.now(ZoneInfo("UTC"))
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired invite token")

    await accept_invite(db, user, req.password)
    return AcceptInviteResponse(email_verified=True)


@router.delete("/users/{user_id}/remove")
async def remove_company_user_endpoint(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    valid_user: dict = Depends(get_validated_user),
):
    """Admin-scoped removal of another user in the caller's own company —
    distinct from the self-service DELETE /users/{user_id} above."""
    await remove_user_service(db, valid_user, user_id)
    return {"removed": True}


@router.patch("/users/{user_id}/role", response_model=User)
async def update_user_role_endpoint(
    user_id: UUID,
    req: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    valid_user: dict = Depends(get_validated_user),
):
    return await update_user_role_service(db, valid_user, user_id, req.role)


@router.delete("/users/{user_id}")
async def delete_my_account(
    user_id: UUID,
    current_user: dict = Depends(get_validated_user),
    db: AsyncSession = Depends(get_db),
):
    """Right to erasure (data-subject-rights spec) — self-service only, no
    admin-initiated deletion of other accounts here."""
    if str(current_user["user_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to delete this account")

    user = await get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sessions = await revoke_all_sessions_for_user(db, user_id)
    for s in sessions:
        await mark_session_revoked(str(s.id), ttl_seconds=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)

    await soft_delete_user(db, user)
    return {"deleted": True}
