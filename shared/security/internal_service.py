import contextlib
import hmac
import os
from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from .dependencies import get_current_user, get_validated_user

INTERNAL_SERVICE_HEADER = "X-Internal-Service-Token"

# auto_error=False: a missing bearer token here must fall through to the
# internal-service check below, not 401 before we can even look at it.
_optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def _valid_internal_service_token(token: str | None) -> bool:
    """Fails closed: an unset INTERNAL_SERVICE_TOKEN never validates."""
    expected = os.getenv("INTERNAL_SERVICE_TOKEN") or ""
    return bool(expected) and bool(token) and hmac.compare_digest(token, expected)


async def require_internal_service(
    x_internal_service_token: str | None = Header(default=None, alias=INTERNAL_SERVICE_HEADER),
) -> None:
    """FastAPI dependency: 401s unless the internal-service token is present and correct."""
    if not _valid_internal_service_token(x_internal_service_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal service credential",
        )


async def get_validated_user_or_internal_service(
    request: Request,
    token: str | None = Depends(_optional_oauth2_scheme),
    x_internal_service_token: str | None = Header(default=None, alias=INTERNAL_SERVICE_HEADER),
) -> AsyncIterator[dict | None]:
    """A valid service token yields None; otherwise validates the user token."""
    if _valid_internal_service_token(x_internal_service_token):
        yield None
        return
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Yield (not return) so the current-user contextvar outlives the endpoint call.
    async with contextlib.asynccontextmanager(get_current_user)(token) as user:
        yield await get_validated_user(user=user, request=request)
