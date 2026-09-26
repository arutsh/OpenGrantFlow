import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import or_, func, select, Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserModel
from app.utils.security import hash_password, hash_token, verify_token_hash
from app.services.event_publisher import get_publisher
from shared.schemas.user_schema import UserStatus


from app.core.logging import get_logger

logger = get_logger(__name__)

EMAIL_VERIFICATION_TOKEN_TTL_HOURS = 24
PASSWORD_RESET_TOKEN_TTL_HOURS = 1


def _user_event_payload(user: UserModel) -> dict:
    return {
        "user_id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "status": user.status,
        "customer_id": str(user.customer_id) if user.customer_id else None,
        "role": user.role,
    }


async def _publish_user_event(event_type: str, user: UserModel) -> None:
    try:
        publisher = get_publisher()
        await publisher.publish(event_type, _user_event_payload(user))
    except Exception as e:
        logger.error(
            "user_event_publish_failed", event_type=event_type, user_id=str(user.id), error=str(e)
        )


async def get_user(session: AsyncSession, user_id: UUID):
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str):
    result = await session.execute(select(UserModel).where(UserModel.email == email))
    return result.scalar_one_or_none()


def build_users_select(user_ids: list[UUID] | None = None) -> Select:
    stmt = select(UserModel)
    if user_ids:
        stmt = stmt.where(UserModel.id.in_(user_ids))
    return stmt


async def get_users_by_ids(session: AsyncSession, user_ids: list[UUID]):
    result = await session.execute(build_users_select(user_ids))
    return list(result.scalars().all())


async def get_users(session: AsyncSession, limit: int = 100):
    result = await session.execute(build_users_select().limit(limit))
    return list(result.scalars().all())


async def create_user(
    session: AsyncSession,
    email: str,
    password: str,
    first_name: str | None = "",
    last_name: str | None = "",
    role: str | None = "user",
    customer_id: UUID | None = None,
    consent_data_processing: bool = False,
    consent_marketing: bool = False,
) -> UserModel:
    existing = await get_user_by_email(session, email)
    if existing:
        logger.warning("user_creation_rejected", email=email, reason="email_already_exists")
        raise ValueError("Email already registered")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = UserModel(
        email=email,
        hashed_password=await hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=role,
        customer_id=customer_id,
        # RegisterRequest already rejects consent_data_processing=False
        # (consent-management spec), so this is always set at this point —
        # still guarded here in case create_user is ever called directly.
        consent_data_processing_at=now if consent_data_processing else None,
        consent_marketing_at=now if consent_marketing else None,
    )
    session.add(user)
    await session.commit()

    logger.info(
        "user_created",
        user_id=str(user.id),
        email=user.email,
        role=role,
        customer_id=str(customer_id) if customer_id else None,
    )

    await _publish_user_event("user.created", user)
    return user


async def update_user(session: AsyncSession, user: UserModel, updates: dict) -> UserModel:
    for key, value in updates.items():
        if key == "password":
            value = await hash_password(value)
        setattr(user, key, value)

    await session.commit()

    await _publish_user_event("user.updated", user)
    return user


async def get_user_customer_id(session: AsyncSession, user_id: UUID) -> UUID | None:
    user = await get_user(session, user_id)
    if user:
        return user.customer_id
    return None


async def set_email_verification_token(session: AsyncSession, user: UserModel) -> str:
    """Generate a new single-use verification token, store its hash +
    expiry on the user, and return the raw token — the raw value is only
    ever placed in the emailed link, never persisted itself. Overwrites any
    prior token, invalidating it (used for both initial send and resend)."""
    raw_token = secrets.token_urlsafe(32)
    user.email_verification_token_hash = hash_token(raw_token)
    user.email_verification_expires_at = datetime.now(timezone.utc).replace(
        tzinfo=None
    ) + timedelta(hours=EMAIL_VERIFICATION_TOKEN_TTL_HOURS)
    await session.commit()
    return raw_token


async def get_user_by_verification_token(
    session: AsyncSession, email: str, raw_token: str
) -> UserModel | None:
    """The stored hash is bcrypt (salted), so equality can't be pushed into
    a WHERE clause — the caller supplies the email (round-tripped through
    the verification link) so lookup is a single indexed query + one
    hash-verify, rather than scanning every account with a pending token.

    Matches on `email` OR `pending_email` so this same lookup (and the same
    /auth/verify-email endpoint) serves both initial account verification
    and email-change rectification — the verification link always carries
    whichever address the token was actually issued for.
    """
    result = await session.execute(
        select(UserModel).where(or_(UserModel.email == email, UserModel.pending_email == email))
    )
    user = result.scalar_one_or_none()
    if not user or not user.email_verification_token_hash:
        return None
    if not verify_token_hash(raw_token, user.email_verification_token_hash):
        return None
    return user


async def mark_email_verified(session: AsyncSession, user: UserModel) -> UserModel:
    user.email_verified = True
    if user.pending_email:
        # Rectification confirmation: promote the pending address now that
        # it's verified. The old address remained active/loginable up to
        # this point (data-subject-rights spec: "old email remains active
        # until confirmed").
        user.email = user.pending_email
        user.pending_email = None
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    await session.commit()
    return user


async def set_pending_email_verification_token(
    session: AsyncSession, user: UserModel, new_email: str
) -> str:
    """Rectification: stores `new_email` as unverified and returns a raw
    verification token for it (mirrors set_email_verification_token). The
    account's active `email` is left untouched until the token is
    confirmed via /auth/verify-email."""
    result = await session.execute(
        select(UserModel).where(
            or_(UserModel.email == new_email, UserModel.pending_email == new_email)
        )
    )
    existing = result.scalar_one_or_none()
    if existing and existing.id != user.id:
        # Covers both an already-active email and another user's in-flight
        # pending change to the same address — without the latter check,
        # both requests would succeed here and the second to actually
        # verify would hit the `email` unique constraint as an unhandled
        # 500 in /auth/verify-email instead of a clean error right here.
        raise ValueError("Email already registered")

    raw_token = secrets.token_urlsafe(32)
    user.pending_email = new_email
    user.email_verification_token_hash = hash_token(raw_token)
    user.email_verification_expires_at = datetime.now(timezone.utc).replace(
        tzinfo=None
    ) + timedelta(hours=EMAIL_VERIFICATION_TOKEN_TTL_HOURS)
    await session.commit()
    return raw_token


async def set_password_reset_token(session: AsyncSession, user: UserModel) -> str | None:
    """Mirrors set_email_verification_token, on the dedicated reset column
    pair. No-ops (returns None) for an account with no password set — a
    reset token there would be a set-invite-password case, not a reset."""
    if not user.hashed_password:
        return None
    raw_token = secrets.token_urlsafe(32)
    user.password_reset_token_hash = hash_token(raw_token)
    user.password_reset_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        hours=PASSWORD_RESET_TOKEN_TTL_HOURS
    )
    await session.commit()
    return raw_token


async def get_user_by_password_reset_token(
    session: AsyncSession, email: str, raw_token: str
) -> UserModel | None:
    user = await get_user_by_email(session, email)
    if not user or not user.password_reset_token_hash or not user.password_reset_expires_at:
        return None
    if user.password_reset_expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        return None
    if not verify_token_hash(raw_token, user.password_reset_token_hash):
        return None
    return user


async def reset_password(session: AsyncSession, user: UserModel, new_password: str) -> UserModel:
    user.hashed_password = await hash_password(new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    await session.commit()
    return user


def get_consent_state(user: UserModel) -> dict:
    return {
        "data_processing_granted": user.consent_data_processing_at is not None,
        "data_processing_at": user.consent_data_processing_at,
        "marketing_granted": user.consent_marketing_at is not None,
        "marketing_at": user.consent_marketing_at,
    }


async def set_marketing_consent(session: AsyncSession, user: UserModel, granted: bool) -> UserModel:
    user.consent_marketing_at = datetime.now(timezone.utc).replace(tzinfo=None) if granted else None
    await session.commit()
    return user


async def create_invited_user(
    session: AsyncSession,
    email: str,
    customer_id: UUID,
    role: str = "user",
    first_name: str | None = "",
    last_name: str | None = "",
) -> tuple[UserModel, str]:
    """Admin-management-page invite flow: creates a pending row immediately
    (visible in the company's user list right away), reusing the
    email-verification token columns/helpers for the accept-invite link
    rather than a dedicated invite-token table (design.md decision 3)."""
    existing = await get_user_by_email(session, email)
    if existing:
        raise ValueError("Email already registered")

    user = UserModel(
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        customer_id=customer_id,
    )
    session.add(user)
    await session.commit()

    raw_token = await set_email_verification_token(session, user)

    logger.info(
        "user_invited", user_id=str(user.id), email=user.email, customer_id=str(customer_id)
    )
    await _publish_user_event("user.created", user)
    return user, raw_token


async def accept_invite(session: AsyncSession, user: UserModel, password: str) -> UserModel:
    """Distinct from mark_email_verified: also sets the invitee's chosen
    password and activates the pending account in one step."""
    user.hashed_password = await hash_password(password)
    user.email_verified = True
    user.status = "active"
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    await session.commit()
    return user


async def count_admins(
    session: AsyncSession, customer_id: UUID, exclude_user_id: UUID | None = None
) -> int:
    """Only counts admins who can actually authenticate — a pending,
    unaccepted admin invite (no password set yet) must not count toward the
    last-admin quorum, or the real admin could lock themselves out while the
    invite sits unaccepted."""
    stmt = (
        select(func.count())
        .select_from(UserModel)
        .where(
            UserModel.customer_id == customer_id,
            UserModel.role == "admin",
            UserModel.status == UserStatus.active,
            UserModel.deleted_at.is_(None),
        )
    )
    if exclude_user_id:
        stmt = stmt.where(UserModel.id != exclude_user_id)
    result = await session.execute(stmt)
    return result.scalar_one()


def _tombstone_email(user_id: UUID) -> str:
    return f"deleted-{user_id}@deleted.invalid"


async def soft_delete_user(session: AsyncSession, user: UserModel) -> UserModel:
    """Right to erasure (data-subject-rights spec): scrub PII to a
    tombstone value and block future login, but keep the row — financial
    records' created_by/updated_by references must not dangle (design.md
    decision 2). Session revocation is the caller's job (it also needs to
    touch Redis — see app/api/auth_routes.py's _revoke_session_everywhere).
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user.first_name = "Deleted"
    user.last_name = "User"
    user.email = _tombstone_email(user.id)
    user.pending_email = None
    user.hashed_password = None
    user.deletion_requested_at = user.deletion_requested_at or now
    user.deleted_at = now
    await session.commit()
    return user
