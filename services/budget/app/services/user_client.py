from app.core.config import settings
import uuid
import httpx
from typing import List, Dict
from shared.utils.gateway_wrapper import service_call_exception_handler

USER_SERVICE_URL = settings.user_all_services_url
_client: httpx.AsyncClient = httpx.AsyncClient(base_url=USER_SERVICE_URL)


async def init_urls():
    global USER_SERVICE_URL, _client

    USER_SERVICE_URL = settings.user_all_services_url
    _client = httpx.AsyncClient(base_url=USER_SERVICE_URL)
    print(f"✅ Users client initialized: {USER_SERVICE_URL}")


async def close_urls():
    """Gracefully close HTTP client session."""
    global _client  # noqa F824
    if _client:
        await _client.aclose()
        print("🛑 Users client closed")


@service_call_exception_handler
async def get_users_by_ids(ids: List[str | uuid.UUID], token: str) -> Dict[str, dict]:
    if not ids:
        return {}
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # call a batch endpoint if available (recommended)
    r = await _client.post(
        f"{USER_SERVICE_URL}users/by_ids/", headers=headers, json=[str(i) for i in ids]
    )
    r.raise_for_status()
    items = r.json()
    return {it["id"]: it for it in items}


@service_call_exception_handler
async def get_customers_by_ids(ids: List[str | uuid.UUID], token: str) -> Dict[str, dict]:
    if not ids:
        return {}
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # call a batch endpoint if available (recommended)
    r = await _client.post(
        f"{USER_SERVICE_URL}customers/by_ids/", headers=headers, json=[str(i) for i in ids]
    )
    r.raise_for_status()
    items = r.json()
    return {it["id"]: it for it in items}
