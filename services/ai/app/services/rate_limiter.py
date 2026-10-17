import hashlib
import hmac
import ipaddress
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import redis.asyncio as aioredis
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import HTTPException

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None
_DAILY_CAP_TTL_SECONDS = 48 * 3600


class CapStoreUnavailable(Exception):
    """The daily-cap store can't be reached; callers must fail closed."""


class DailyCapReached(Exception):
    """A daily cap is exhausted; `retry_after` is seconds until UTC midnight."""

    def __init__(self, retry_after: int):
        super().__init__(retry_after)
        self.retry_after = retry_after


def get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def check_and_increment(
    customer_id: str, limit: int | None = None, *, scope: str = "ai"
) -> tuple[bool, int]:
    """Sliding window counter keyed by (scope, customer_id).

    `scope` namespaces the counter — e.g. "ai" for the general per-request
    limit, "excel-import-platform" for the GrantFlow-funded Excel-import
    fallback's own, separately-tracked limit — so different call sites don't
    share a bucket.

    Returns (allowed, retry_after_seconds). retry_after is 0 when allowed.
    Fails open if Redis is unavailable.
    """
    effective_limit = limit if limit is not None else settings.AI_RATE_LIMIT_PER_HOUR
    key = f"rate_limit:{scope}:{customer_id}"
    try:
        count = await _incr_with_ttl(key, 3600)
        if count > effective_limit:
            ttl = await get_redis_client().ttl(key)
            return False, max(ttl, 0)
        return True, 0
    except Exception:
        logger.warning("rate_limiter_unavailable", customer_id=customer_id, scope=scope)
        return True, 0


async def enforce_rate_limit(
    customer_id: str,
    *,
    limit: int | None = None,
    scope: str = "ai",
    extra_headers: dict | None = None,
) -> None:
    """Raise 429 with a Retry-After header when the customer is over their hourly limit."""
    allowed, retry_after = await check_and_increment(customer_id, limit, scope=scope)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(retry_after), **(extra_headers or {})},
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _incr_with_ttl(key: str, ttl: int) -> int:
    """INCR plus EXPIRE NX in one transaction, so no key is ever left without a TTL."""
    async with get_redis_client().pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, ttl, nx=True)
        count, _ = await pipe.execute()
    return count


@lru_cache(maxsize=1)
def _ip_hash_key() -> bytes:
    # Purpose-bound subkey so the AES data key is never used directly as an HMAC key.
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"site-assistant-ip-hash"
    ).derive(settings.ENCRYPTION_KEY.encode())


def client_ip_subject(ip: str) -> str:
    """IPv6 collapses to its /64 so one allocation can't rotate past the cap."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped is not None:
            return str(addr.ipv4_mapped)
        return str(ipaddress.IPv6Network((addr, 64), strict=False))
    return str(addr)


def hash_client_ip(ip: str) -> str:
    """Keyed hash so cap keys in Redis never hold a raw IP."""
    digest = hmac.new(_ip_hash_key(), client_ip_subject(ip).encode(), hashlib.sha256)
    return digest.hexdigest()[:32]


async def check_daily_cap(scope: str, subject: str, limit: int | None) -> tuple[bool, int]:
    """UTC-day counter; `None`/`0` is unlimited. Returns (allowed, seconds_to_utc_midnight).
    Unlike check_and_increment it fails closed, raising CapStoreUnavailable on Redis errors."""
    if not limit:
        return True, 0
    now = _utc_now()
    key = f"rate_limit:{scope}:{subject}:{now:%Y%m%d}"
    try:
        count = await _incr_with_ttl(key, _DAILY_CAP_TTL_SECONDS)
    except Exception as exc:
        logger.warning("daily_cap_store_unavailable", scope=scope, error_type=type(exc).__name__)
        raise CapStoreUnavailable(scope) from exc
    if count > limit:
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return False, max(int((midnight - now).total_seconds()), 1)
    return True, 0


async def enforce_daily_cap(scope: str, subject: str, limit: int | None) -> None:
    """Raise DailyCapReached over the cap; CapStoreUnavailable propagates from the check."""
    allowed, retry_after = await check_daily_cap(scope, subject, limit)
    if not allowed:
        raise DailyCapReached(retry_after)
