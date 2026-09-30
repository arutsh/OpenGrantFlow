from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.ai_provider import get_by_name
from app.crud.ai_provider_model import exists_for_provider as model_exists_for_provider
from app.crud.customer_ai_defaults import get as get_customer_ai_defaults, set_platform_fallback
from app.crud.user_provider_key import create, delete, list_for_customer, set_default
from app.db.session import AsyncSessionLocal
from app.services import egress_policy
from app.services.provider import _REGISTRY
from app.utils.encryption import decrypt, encrypt
from app.utils.security import get_validated_user, resolve_customer_id

router = APIRouter(prefix="/ai/settings", tags=["AI Settings"])

_ADMIN_ROLES = {"superuser", "admin"}


async def get_db():
    async with AsyncSessionLocal() as db:
        yield db


def _require_admin(valid_user: dict) -> None:
    if valid_user.get("role") not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin or superuser role required")


def _require_superuser(valid_user: dict) -> None:
    if valid_user.get("role") != "superuser":
        raise HTTPException(status_code=403, detail="Superuser role required")


def _mask_key(plaintext: str) -> str:
    if len(plaintext) <= 8:
        return "••••"
    return f"{plaintext[:6]}…{plaintext[-4:]}"


class ProviderKeyConfig(BaseModel):
    id: str
    provider: str
    label: str | None
    model: str | None
    masked_key: str | None
    base_url: str | None
    is_default: bool


class ApprovedEndpoint(BaseModel):
    origin: str
    label: str


class SettingsResponse(BaseModel):
    configs: list[ProviderKeyConfig]
    platform_fallback_enabled: bool
    approved_endpoints: list[ApprovedEndpoint]


class CreateKeyRequest(BaseModel):
    provider: str
    label: str | None = None
    key: str | None = None
    model: str
    base_url: str | None = None
    is_default: bool = False


class DeleteKeyRequest(BaseModel):
    new_default_id: str | None = None


class PlatformFallbackRequest(BaseModel):
    enabled: bool


def _resolve_and_validate_base_url(provider, requested_base_url: str | None) -> str | None:
    """Enforce the operator's approved-origin policy for key-less providers
    (e.g. Ollama); reject a base_url on providers that require a key."""
    if provider.key_prefix:
        if requested_base_url:
            raise HTTPException(
                status_code=422, detail=f"{provider.name} does not accept a base_url"
            )
        return None
    base_url = requested_base_url or settings.OLLAMA_URL
    if base_url:
        approved = egress_policy.parse_approved_origins(settings.AI_PROVIDER_APPROVED_ORIGINS)
        if egress_policy.is_approved(base_url, approved) is None:
            raise HTTPException(status_code=422, detail="base_url is not an approved endpoint")
    return base_url


async def _validate_key_with_provider(
    provider_name: str, key_prefix: str | None, key: str | None
) -> None:
    if key_prefix and not key:
        raise HTTPException(status_code=422, detail=f"{provider_name} requires an API key")
    if key_prefix and key and not key.startswith(key_prefix):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid key format for {provider_name} (expected prefix: {key_prefix})",
        )
    adapter = _REGISTRY.get(provider_name)
    if adapter and key:
        await adapter.validate_key(key)


async def _build_settings_response(customer_id: str, db: AsyncSession) -> SettingsResponse:
    configs = await list_for_customer(customer_id, db)
    items: list[ProviderKeyConfig] = []
    for c in configs:
        masked = None
        if c.encrypted_key:
            try:
                masked = _mask_key(decrypt(c.encrypted_key, settings.ENCRYPTION_KEY))
            except Exception:
                masked = "••••"
        items.append(
            ProviderKeyConfig(
                id=str(c.id),
                provider=c.provider.name,
                label=c.label,
                model=c.model_name,
                masked_key=masked,
                base_url=c.base_url,
                is_default=c.is_default,
            )
        )
    defaults = await get_customer_ai_defaults(customer_id, db)
    approved = egress_policy.parse_approved_origins(settings.AI_PROVIDER_APPROVED_ORIGINS)
    return SettingsResponse(
        configs=items,
        platform_fallback_enabled=bool(defaults and defaults.platform_fallback_enabled),
        approved_endpoints=[
            ApprovedEndpoint(origin=o.origin, label=o.label or o.origin) for o in approved
        ],
    )


@router.get("", response_model=SettingsResponse)
async def get_ai_settings(
    valid_user: dict = Depends(get_validated_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(valid_user)
    customer_id = resolve_customer_id(valid_user)
    return await _build_settings_response(customer_id, db)


@router.post("/keys", response_model=SettingsResponse)
async def create_ai_key(
    body: CreateKeyRequest,
    valid_user: dict = Depends(get_validated_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(valid_user)
    provider = await get_by_name(body.provider, db)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{body.provider}' not found")
    if not await model_exists_for_provider(str(provider.id), body.model, db):
        raise HTTPException(
            status_code=422,
            detail=f"Model '{body.model}' is not valid for provider '{provider.name}'",
        )
    await _validate_key_with_provider(provider.name, provider.key_prefix, body.key)
    encrypted = encrypt(body.key, settings.ENCRYPTION_KEY) if body.key else None
    base_url = _resolve_and_validate_base_url(provider, body.base_url)
    user_id = str(valid_user["user_id"])
    customer_id = resolve_customer_id(valid_user)
    await create(
        customer_id=customer_id,
        user_id=user_id,
        provider_id=str(provider.id),
        label=body.label,
        encrypted_key=encrypted,
        model_name=body.model,
        base_url=base_url,
        is_default=body.is_default,
        db=db,
    )
    return await _build_settings_response(customer_id, db)


@router.post("/keys/{config_id}/default", response_model=SettingsResponse)
async def set_default_ai_key(
    config_id: str,
    valid_user: dict = Depends(get_validated_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(valid_user)
    customer_id = resolve_customer_id(valid_user)
    try:
        await set_default(customer_id, config_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Config not found") from exc
    return await _build_settings_response(customer_id, db)


@router.delete("/keys/{config_id}", response_model=SettingsResponse)
async def delete_ai_key(
    config_id: str,
    body: DeleteKeyRequest | None = None,
    valid_user: dict = Depends(get_validated_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(valid_user)
    new_default_id = body.new_default_id if body else None

    customer_id = resolve_customer_id(valid_user)
    try:
        await delete(customer_id, config_id, db, new_default_id=new_default_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return await _build_settings_response(customer_id, db)


@router.put("/platform-fallback", response_model=SettingsResponse)
async def set_platform_fallback_route(
    body: PlatformFallbackRequest,
    valid_user: dict = Depends(get_validated_user),
    db: AsyncSession = Depends(get_db),
):
    _require_superuser(valid_user)
    customer_id = resolve_customer_id(valid_user)
    await set_platform_fallback(customer_id, body.enabled, db)
    return await _build_settings_response(customer_id, db)
