import uuid
from collections import OrderedDict

import httpx
from app.core.config import settings
from fastapi import status
from app.core.exceptions import DomainError

CUSTOMER_SERVICE_URL = settings.customer_service_url
_client: httpx.AsyncClient = httpx.AsyncClient(base_url=CUSTOMER_SERVICE_URL)

_CACHE_MAXSIZE = 128
_customer_cache: "OrderedDict[str, dict]" = OrderedDict()


class CustomerServiceError(Exception):
    pass


async def init_urls():
    global CUSTOMER_SERVICE_URL, _client

    CUSTOMER_SERVICE_URL = settings.customer_service_url
    _client = httpx.AsyncClient(base_url=CUSTOMER_SERVICE_URL)
    print(f"✅ Customer client initialized: {CUSTOMER_SERVICE_URL}")


async def close_urls():
    """Gracefully close HTTP client session."""
    global _client  # noqa: F824
    if _client:
        await _client.aclose()
        print("🛑 Customer client closed")


async def get_customer(customer_id: str | uuid.UUID) -> dict:
    """No-auth by_ids/ endpoint: this is a service-to-service call, no user token to forward."""
    try:
        resp = await _client.post(f"{CUSTOMER_SERVICE_URL}by_ids/", json=[str(customer_id)])
        resp.raise_for_status()
        items = resp.json()
    except httpx.HTTPError as e:
        raise CustomerServiceError(f"Failed to fetch customer {customer_id}") from e

    if not items:
        raise CustomerServiceError(f"Failed to fetch customer {customer_id}")
    return items[0]


async def get_customer_cached(customer_id: str | uuid.UUID) -> dict:
    """Same maxsize=128, no-TTL semantics as the old @lru_cache, async-compatible."""
    key = str(customer_id)
    if key in _customer_cache:
        _customer_cache.move_to_end(key)
        return _customer_cache[key]

    customer = await get_customer(customer_id)
    _customer_cache[key] = customer
    if len(_customer_cache) > _CACHE_MAXSIZE:
        _customer_cache.popitem(last=False)
    return customer


async def validate_customer_can_fund(
    customer_id: str | uuid.UUID, raise_domain_error: bool = False
):
    """Assert the customer has is_donor=True (can issue grants)."""
    Error = DomainError if raise_domain_error else ValueError
    try:
        customer = await get_customer_cached(customer_id)
    except CustomerServiceError as e:
        raise Error(str(e))

    if not customer.get("is_donor"):
        raise Error(f"Customer {customer_id} is not a donor and cannot fund budgets")
    return customer


def require_donor(valid_user: dict) -> None:
    """Reads is_donor off the JWT claims rather than get_customer_cached (ticket #135)."""
    if not valid_user.get("is_donor"):
        raise DomainError("Customer is not a donor", status.HTTP_403_FORBIDDEN)


async def validate_customer_can_own(
    customer_id: str | uuid.UUID, raise_domain_error: bool = False
):
    """Assert the customer has is_ngo=True (can receive grants / own budgets)."""
    Error = DomainError if raise_domain_error else ValueError
    try:
        customer = await get_customer_cached(customer_id)
    except CustomerServiceError as e:
        raise Error(str(e))

    if not customer.get("is_ngo"):
        raise Error(f"Customer {customer_id} is not an NGO and cannot own budgets")
    return customer
