from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, TypeVar

from fastapi import Depends
from pydantic_ai import Agent
from pydantic_ai.output import OutputSpec
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.core.logging import get_logger
from app.utils.security import get_validated_user, resolve_customer_id

logger = get_logger(__name__)

# Cheapest current Claude model — used only for the GrantFlow-funded fallback
# path (no BYOK key configured), never the user's own choice of model.
_PLATFORM_FUNDED_MODEL = "claude-haiku-4-5-20251001"


@dataclass
class ResolvedModel:
    """PydanticAI model ready for use in an Agent, plus metadata for audit logging."""

    model: AnthropicModel | OpenAIChatModel
    provider_name: str
    model_name: str


OutputDataT = TypeVar("OutputDataT")


def build_agent(
    model: AnthropicModel | OpenAIChatModel,
    *,
    output_type: OutputSpec[OutputDataT] = str,  # type: ignore[assignment]
    instrument: bool | InstrumentationSettings = True,
    **kwargs: Any,
) -> Agent[None, OutputDataT]:
    """Construct a PydanticAI Agent with OTEL instrumentation enabled — every Agent in this
    service must go through here so `agent.run()` produces spans (see 2026-08-21 trace
    investigation)."""
    agent: Agent[None, OutputDataT] = Agent(model, output_type=output_type, **kwargs)
    agent.instrument = instrument
    return agent


class ProviderAdapter(ABC):
    @abstractmethod
    def build(self, user_key) -> ResolvedModel | None: ...

    async def validate_key(self, key: str) -> None:
        pass  # default: no live validation needed (e.g. Ollama)


_REGISTRY: dict[str, ProviderAdapter] = {}


def register(name: str):
    def decorator(cls: type[ProviderAdapter]) -> type[ProviderAdapter]:
        _REGISTRY[name] = cls()
        return cls

    return decorator


def resolve_model(user_key=None, *, customer_id: str = "") -> ResolvedModel | None:
    """Return a PydanticAI model for the active provider key, or None if unavailable."""
    if user_key is None:
        return None

    if not user_key.provider:
        logger.warning("provider_key_no_provider", customer_id=customer_id)
        return None

    provider_name = user_key.provider.name

    if user_key.model_name is None:
        logger.warning(
            "provider_key_missing_model",
            customer_id=customer_id,
            provider=provider_name,
        )
        return None

    adapter = _REGISTRY.get(provider_name)
    if adapter is None:
        logger.warning(
            "provider_not_registered",
            customer_id=customer_id,
            provider=provider_name,
        )
        return None

    resolved = adapter.build(user_key)
    if resolved is None:
        logger.warning(
            "provider_adapter_build_failed",
            customer_id=customer_id,
            provider=provider_name,
            model=user_key.model_name,
        )
        return None

    logger.debug(
        "provider_resolved",
        customer_id=customer_id,
        provider=resolved.provider_name,
        model=resolved.model_name,
    )
    return resolved


def _platform_anthropic_model(model_name: str) -> ResolvedModel | None:
    """Anthropic model on the platform's own key, or None if that key isn't configured."""
    from app.core.config import settings

    if not settings.ANTHROPIC_API_KEY:
        return None
    return ResolvedModel(
        model=AnthropicModel(
            model_name, provider=AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
        ),
        provider_name="anthropic",
        model_name=model_name,
    )


def resolve_site_assistant_model() -> ResolvedModel | None:
    """Operator-configured model for the anonymous site assistant, or None to fail closed."""
    from app.core.config import settings

    return _site_assistant_model(
        settings.SITE_ASSISTANT_PROVIDER,
        settings.SITE_ASSISTANT_MODEL,
        settings.ANTHROPIC_API_KEY,
        settings.OLLAMA_URL,
        settings.OLLAMA_MODEL,
        settings.AI_PROVIDER_APPROVED_ORIGINS,
    )


@lru_cache(maxsize=1)
def _site_assistant_model(
    provider: str,
    model_name: str | None,
    _anthropic_key: str | None,
    ollama_url: str | None,
    ollama_model: str,
    _approved_origins: str | None,
) -> ResolvedModel | None:
    # Keyed on every setting the build reads, so a config change rebuilds instead of going stale.
    if provider == "anthropic":
        return _platform_anthropic_model(model_name or _PLATFORM_FUNDED_MODEL)
    return build_ollama_model(ollama_url, model_name or ollama_model, "site-assistant")


def resolve_platform_funded_model() -> ResolvedModel | None:
    """GrantFlow-funded fallback for organizations with no configured provider
    key. A deliberate, scoped carve-out from the platform's BYOK-only/no-fallback
    policy — see budget-export-from-excel design.md Decision 5. Returns None if
    the platform's own key isn't configured, so callers can fail closed."""
    return _platform_anthropic_model(_PLATFORM_FUNDED_MODEL)


async def get_resolved_model(
    valid_user: dict = Depends(get_validated_user),
) -> ResolvedModel | None:
    """FastAPI dependency — injects a resolved provider model into route handlers.

    BYOK-only, shared by all three provider-consuming routes; never falls
    through to the platform model itself (see resolve_with_platform_fallback)."""
    from app.crud.user_provider_key import get_active_key_for_customer
    from app.db.session import AsyncSessionLocal

    customer_id = resolve_customer_id(valid_user)

    async with AsyncSessionLocal() as db:
        user_key = await get_active_key_for_customer(customer_id, db)

    if user_key is None:
        logger.info("no_active_provider_key", customer_id=customer_id)
        return None

    return resolve_model(user_key, customer_id=customer_id)


async def resolve_with_platform_fallback(customer_id: str) -> ResolvedModel | None:
    """Platform model if a superuser set it as this customer's default, else None.
    Used only by /ai/decide and /ai/parse-budget/stream — excel keeps its own
    unconditional fallback regardless of this flag."""
    from app.crud.customer_ai_defaults import get as get_customer_ai_defaults
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        defaults = await get_customer_ai_defaults(customer_id, db)

    if defaults is None or not defaults.platform_fallback_enabled:
        return None

    return resolve_platform_funded_model()


# Import adapters to trigger their @register decorators
from app.services.adapters.anthropic import AnthropicAdapter  # noqa: E402, F401
from app.services.adapters.ollama import OllamaAdapter, build_ollama_model  # noqa: E402, F401
