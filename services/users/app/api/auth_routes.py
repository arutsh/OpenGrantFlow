from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from app.schemas.auth_schema import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenResponse,
    ChangePasswordRequest,
    VerifyEmailRequest,
    VerifyEmailResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ImpersonateRequest,
    ImpersonateResponse,
)
from app.schemas.session_schema import SessionSummary

from app.db.session import get_db
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_token,
    verify_token_hash,
    REFRESH_TOKEN_EXPIRE_DAYS,
    IMPERSONATION_TOKEN_EXPIRE_MINUTES,
)
from shared.security.password_policy import validate_password_strength
from shared.security.session_revocation import mark_session_revoked
from app.core.config import settings
from app.crud.sessions_curd import (
    create_session,
    get_session_by_id,
    get_non_revoked_sessions_for_user,
    revoke_session,
    revoke_all_sessions_for_user,
)
from app.crud.user_crud import (
    get_user,
    get_user_by_email,
    create_user,
    set_email_verification_token,
    get_user_by_verification_token,
    mark_email_verified,
    set_password_reset_token,
    get_user_by_password_reset_token,
    reset_password,
)
from app.crud.customer_crud import get_customer
from app.utils.redis import _cache_get, _delete_key
from app.services.celery_client import enqueue_verification_email, enqueue_password_reset_email
from app.services.login_rate_limiter import (
    is_locked_out,
    record_failed_attempt,
    clear_failed_attempts,
)
from shared.security.dependencies import get_validated_user
from shared.security.privileged_access import log_privileged_access
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _role_flags(customer) -> dict:
    """is_ngo/is_donor for the JWT, false when there is no customer."""
    if not customer:
        return {"is_ngo": False, "is_donor": False}
    return {"is_ngo": customer.is_ngo, "is_donor": customer.is_donor}


def _email_verified_claim(user) -> dict:
    """email_verified for the JWT, alongside the is_ngo/is_donor role flags."""
    return {"email_verified": bool(user.email_verified)}


async def _customer_role_claims(db: AsyncSession, customer_id) -> dict:
    """Same as _role_flags, but for callers with only a customer_id, no
    already-loaded customer (e.g. a just-inserted user with nothing eager-
    loaded yet). Prefer passing the loaded customer via _role_flags directly
    when one is already in hand — UserModel.customer is lazy="joined", so
    it usually is.

    Swallows lookup failures instead of raising: callers of this reach it
    after already durably committing a user/session, so a transient DB
    error here should degrade the claims to false/false, not turn an
    already-successful registration into a 500 with no token issued.
    """
    if not customer_id:
        return {"is_ngo": False, "is_donor": False}
    try:
        customer = await get_customer(db, customer_id)
    except Exception:
        logger.exception("Failed to look up customer %s for role claims", customer_id)
        return {"is_ngo": False, "is_donor": False}
    return _role_flags(customer)


@router.post("/register", response_model=RegisterResponse)
async def register_endpoint(
    req: RegisterRequest,
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
):
    # No existing account to key on yet, so both scopes use the IP —
    # volumetric abuse from one source is the threat, not one account.
    client_ip = request.client.host if request is not None and request.client else "unknown"
    if is_locked_out(client_ip, client_ip, bucket="register"):
        raise HTTPException(
            status_code=429,
            detail="Too many registration attempts. Try again later.",
        )

    try:
        user = await create_user(
            session=db,
            email=req.email,
            password=req.password,
            first_name=req.first_name,
            last_name=req.last_name,
            consent_data_processing=req.consent_data_processing,
            consent_marketing=req.consent_marketing,
        )
    except ValueError as e:
        record_failed_attempt(client_ip, client_ip, bucket="register")
        raise HTTPException(status_code=400, detail=str(e))

    clear_failed_attempts(client_ip, bucket="register")

    raw_token = await set_email_verification_token(db, user)
    try:
        enqueue_verification_email(user.email, raw_token, user.first_name)
    except Exception:
        # Registration already succeeded and was committed — a broker blip
        # shouldn't turn that into a failed registration response. The user
        # can self-serve via /auth/resend-verification either way.
        logger.exception("verification_email_enqueue_failed", user_id=str(user.id))

    # No session/token here — unauthenticated until verify-email succeeds.
    return RegisterResponse(
        message="Check your email to confirm your account.",
        email=user.email,
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request is not None and request.client else "unknown"

    if is_locked_out(req.email, client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Try again later.",
        )

    user = await get_user_by_email(db, req.email)
    if (
        not user
        or not user.hashed_password
        or getattr(user, "deleted_at", None) is not None
        or (user.customer and getattr(user.customer, "deactivated_at", None) is not None)
        or not await verify_password(req.password, user.hashed_password)
    ):
        record_failed_attempt(req.email, client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    clear_failed_attempts(req.email)

    if not user.email_verified:
        # Valid credentials, but no session until the account is verified.
        raise HTTPException(status_code=403, detail="email_not_verified")

    refresh_token = create_refresh_token()

    session = await create_session(
        session=db,
        user_id=user.id,
        refresh_token_hash=refresh_token,
    )

    token = create_access_token(
        {
            "user_id": user.id,
            "session_id": session.id,
            "role": user.role,
            "customer_id": user.customer_id,
            **_role_flags(user.customer),
            **_email_verified_claim(user),
        }
    )

    return TokenResponse(access_token=token, refresh_token=refresh_token, status=user.status)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    redis_key = f"refresh:{refresh_token}"
    session_id = _cache_get(redis_key)
    _delete_key(redis_key)
    if not session_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    s = await get_session_by_id(db, session_id)
    if not s or s.revoked:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if s.user.customer and getattr(s.user.customer, "deactivated_at", None) is not None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Session model always has naive datetime, assume UTC
    if s.expires_at.replace(tzinfo=ZoneInfo("UTC")) < datetime.now(ZoneInfo("UTC")):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if verify_token_hash(refresh_token, s.refresh_token_hash):
        # Rotate new refresh token
        new_refresh = create_refresh_token()
        s.refresh_token_hash = hash_token(new_refresh)
        await db.commit()

        access_token = create_access_token(
            {
                "user_id": s.user_id,
                "session_id": s.id,
                "role": s.user.role,
                "customer_id": s.user.customer_id,
                **_role_flags(s.user.customer),
                **_email_verified_claim(s.user),
            }
        )

        return TokenResponse(
            access_token=access_token, refresh_token=new_refresh, status=s.user.status
        )

    raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@router.post("/auth/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    req: VerifyEmailRequest,
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
):
    # Same class of attacker-guessable input (email + token) that login-rate-
    # limiting was added to defend — reuses that mechanism under a separate
    # bucket rather than leaving this endpoint unguarded.
    client_ip = request.client.host if request is not None and request.client else "unknown"
    if is_locked_out(req.email, client_ip, bucket="verify_email"):
        raise HTTPException(
            status_code=429,
            detail="Too many verification attempts. Try again later.",
        )

    user = await get_user_by_verification_token(db, req.email, req.token)
    if not user:
        record_failed_attempt(req.email, client_ip, bucket="verify_email")
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    expires_at = user.email_verification_expires_at
    if not expires_at or expires_at.replace(tzinfo=ZoneInfo("UTC")) < datetime.now(ZoneInfo("UTC")):
        record_failed_attempt(req.email, client_ip, bucket="verify_email")
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    clear_failed_attempts(req.email, bucket="verify_email")
    user = await mark_email_verified(db, user)

    # This is the account's first session — verification is the login moment.
    refresh_token = create_refresh_token()
    session = await create_session(
        session=db,
        user_id=user.id,
        refresh_token_hash=refresh_token,
    )
    token = create_access_token(
        {
            "user_id": user.id,
            "session_id": session.id,
            "role": user.role,
            "customer_id": user.customer_id,
            **await _customer_role_claims(db, user.customer_id),
            **_email_verified_claim(user),
        }
    )

    return VerifyEmailResponse(
        email_verified=True,
        access_token=token,
        refresh_token=refresh_token,
        status=user.status,
    )


@router.post("/auth/resend-verification", response_model=ResendVerificationResponse)
async def resend_verification(
    req: ResendVerificationRequest,
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
):
    """Anonymous and enumeration-safe: same response regardless of account state."""
    client_ip = request.client.host if request is not None and request.client else "unknown"
    if is_locked_out(req.email, client_ip, bucket="resend_verification"):
        raise HTTPException(
            status_code=429,
            detail="Too many resend attempts. Try again later.",
        )
    record_failed_attempt(req.email, client_ip, bucket="resend_verification")

    debug_token = None
    user = await get_user_by_email(db, req.email)
    if user and not user.email_verified:
        raw_token = await set_email_verification_token(db, user)
        try:
            enqueue_verification_email(user.email, raw_token, user.first_name)
        except Exception:
            logger.exception("verification_email_enqueue_failed", user_id=str(user.id))
        if settings.EXPOSE_VERIFICATION_TOKEN_FOR_TESTS:
            debug_token = raw_token

    return ResendVerificationResponse(sent=True, debug_token=debug_token)


@router.post("/auth/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    req: ForgotPasswordRequest,
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
):
    """Anonymous and enumeration-safe: same response regardless of account state."""
    client_ip = request.client.host if request is not None and request.client else "unknown"
    if is_locked_out(req.email, client_ip, bucket="forgot_password"):
        raise HTTPException(
            status_code=429,
            detail="Too many reset attempts. Try again later.",
        )
    record_failed_attempt(req.email, client_ip, bucket="forgot_password")

    debug_token = None
    user = await get_user_by_email(db, req.email)
    if user:
        raw_token = await set_password_reset_token(db, user)
        if raw_token:
            try:
                enqueue_password_reset_email(user.email, raw_token, user.first_name)
            except Exception:
                logger.exception("password_reset_email_enqueue_failed", user_id=str(user.id))
            if settings.EXPOSE_VERIFICATION_TOKEN_FOR_TESTS:
                debug_token = raw_token

    return ForgotPasswordResponse(sent=True, debug_token=debug_token)


@router.post("/auth/reset-password", response_model=ResetPasswordResponse)
async def reset_password_endpoint(
    req: ResetPasswordRequest,
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
):
    """Anonymous: consumes the reset token, sets the new password, and
    revokes every session for the account. No session is issued here."""
    client_ip = request.client.host if request is not None and request.client else "unknown"
    if is_locked_out(req.email, client_ip, bucket="reset_password"):
        raise HTTPException(
            status_code=429,
            detail="Too many reset attempts. Try again later.",
        )

    user = await get_user_by_password_reset_token(db, req.email, req.token)
    if not user:
        record_failed_attempt(req.email, client_ip, bucket="reset_password")
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    try:
        validate_password_strength(
            req.new_password,
            email=user.email,
            name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    clear_failed_attempts(req.email, bucket="reset_password")
    await reset_password(db, user, req.new_password)

    sessions = await revoke_all_sessions_for_user(db, user.id)
    for s in sessions:
        await mark_session_revoked(str(s.id), ttl_seconds=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)

    return ResetPasswordResponse(reset=True)


@router.post("/auth/change-password")
async def change_password(
    req: ChangePasswordRequest,
    request: Request = None,  # type: ignore[assignment]
    current_user: dict = Depends(get_validated_user),
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request is not None and request.client else "unknown"
    # Keyed on user id, not email — always available from the token.
    subject = str(current_user["user_id"])

    if is_locked_out(subject, client_ip, bucket="change_password"):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again later.",
        )

    user = await get_user(db, current_user["user_id"])
    if (
        not user
        or not user.hashed_password
        or not await verify_password(req.current_password, user.hashed_password)
    ):
        record_failed_attempt(subject, client_ip, bucket="change_password")
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    clear_failed_attempts(subject, bucket="change_password")

    try:
        validate_password_strength(
            req.new_password,
            email=user.email,
            name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user.hashed_password = await hash_password(req.new_password)
    await db.commit()

    # Revoke every other session, like logout()/delete_my_account() do; keep this one alive.
    current_session_id = current_user.get("session_id")
    for session in await get_non_revoked_sessions_for_user(db, user.id):
        if str(session.id) == str(current_session_id):
            continue
        await _revoke_session_everywhere(db, session)

    return {"changed": True}


async def _revoke_session_everywhere(db: AsyncSession, session) -> None:
    """Revoke a session in both stores: Postgres (`SessionModel.revoked`,
    the source of truth used by the active-sessions listing) and Redis
    (the cross-service check every service's `get_current_user` consults —
    see shared/security/session_revocation.py for why a DB lookup alone
    can't be shared across services)."""
    await revoke_session(db, session)
    await mark_session_revoked(str(session.id), ttl_seconds=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)


@router.post("/auth/logout")
async def logout(
    current_user: dict = Depends(get_validated_user), db: AsyncSession = Depends(get_db)
):
    session_id = current_user.get("session_id")
    session = await get_session_by_id(db, session_id) if session_id else None
    if session and not session.revoked:
        await _revoke_session_everywhere(db, session)
    return {"logged_out": True}


@router.get("/auth/sessions", response_model=list[SessionSummary])
async def list_sessions(
    current_user: dict = Depends(get_validated_user), db: AsyncSession = Depends(get_db)
):
    sessions = await get_non_revoked_sessions_for_user(db, current_user["user_id"])
    current_session_id = str(current_user.get("session_id") or "")
    return [
        SessionSummary(
            id=s.id,
            issued_at=s.issued_at,
            expires_at=s.expires_at,
            current=str(s.id) == current_session_id,
        )
        for s in sessions
    ]


@router.delete("/auth/sessions/{session_id}")
async def revoke_one_session(
    session_id: UUID,
    current_user: dict = Depends(get_validated_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_by_id(db, session_id)
    if not session or str(session.user_id) != str(current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.revoked:
        await _revoke_session_everywhere(db, session)
    return {"revoked": True}


@router.post("/auth/impersonate", response_model=ImpersonateResponse)
async def start_impersonation(
    req: ImpersonateRequest,
    current_user: dict = Depends(get_validated_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
):
    """Stateless: no impersonation_sessions table, no refresh token — short
    expiry + the audit log (not revocation) is the accepted mitigation."""
    if current_user.get("role") != "superuser":
        raise HTTPException(status_code=403, detail="Superuser role required")

    customer = await get_customer(db, req.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Log the mint here — get_validated_user's audit hook won't fire for this request.
    await run_in_threadpool(
        log_privileged_access,
        {"user_id": str(current_user["user_id"]), "customer_id": str(customer.id)},
        request,
    )

    expires_delta = timedelta(minutes=IMPERSONATION_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        {
            "user_id": str(current_user["user_id"]),
            "customer_id": str(customer.id),
            "role": "admin",
            "is_impersonating": True,
            **_role_flags(customer),
            "email_verified": current_user.get("email_verified", True),
        },
        expires_delta=expires_delta,
    )

    return ImpersonateResponse(
        access_token=token,
        customer_id=customer.id,
        customer_name=customer.name,
        expires_in=int(expires_delta.total_seconds()),
    )
