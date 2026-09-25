import uuid

import httpx

from app.core.config import settings
from app.core.exceptions import DomainError

DONOR_GRANTEE_SERVICE_URL = settings.donor_grantee_service_url
REQUEST_TIMEOUT_SECONDS = 5
_client: httpx.AsyncClient = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)


class DonorGranteeServiceError(Exception):
    pass


async def init_urls():
    global DONOR_GRANTEE_SERVICE_URL, _client

    DONOR_GRANTEE_SERVICE_URL = settings.donor_grantee_service_url
    _client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
    print(f"✅ Donor-grantee client initialized: {DONOR_GRANTEE_SERVICE_URL}")


async def close_urls():
    """Gracefully close HTTP client session."""
    global _client  # noqa: F824
    if _client:
        await _client.aclose()
        print("🛑 Donor-grantee client closed")


async def check_donor_grantee_relationship(
    donor_id: str | uuid.UUID, grantee_id: str | uuid.UUID
) -> bool:
    """No caching, deliberately — unlike get_customer_cached, revocation must
    take effect on the very next call, not after some cache TTL/eviction."""
    try:
        resp = await _client.get(
            f"{DONOR_GRANTEE_SERVICE_URL}exists",
            params={"donor_id": str(donor_id), "grantee_id": str(grantee_id)},
        )
        resp.raise_for_status()
        return bool(resp.json().get("exists", False))
    except httpx.HTTPError as e:
        raise DonorGranteeServiceError(
            f"Failed to check donor-grantee relationship for donor {donor_id}, "
            f"grantee {grantee_id}"
        ) from e


async def validate_donor_grantee_relationship(
    donor_id: str | uuid.UUID,
    grantee_id: str | uuid.UUID,
    raise_domain_error: bool = False,
):
    """Assert a donor_grantees row exists linking donor_id (funder) to grantee_id (owner)."""
    Error = DomainError if raise_domain_error else ValueError
    try:
        exists = await check_donor_grantee_relationship(donor_id, grantee_id)
    except DonorGranteeServiceError as e:
        raise Error(str(e))

    if not exists:
        raise Error(f"Donor {donor_id} has not approved grantee {grantee_id} to fund their budgets")
