import httpx
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.logging import get_logger
from app.services.pinned_transport import build_public_only_transport
from app.services.provider import ProviderAdapter, ResolvedModel, register

logger = get_logger(__name__)

_http_clients: dict[bool, httpx.AsyncClient] = {}


def _shared_http_client(allow_private: bool) -> httpx.AsyncClient:
    # One pooled client per egress mode; base_url is applied by OpenAIProvider.
    client = _http_clients.get(allow_private)
    if client is None or client.is_closed:
        transport = None if allow_private else build_public_only_transport()
        client = httpx.AsyncClient(transport=transport, follow_redirects=False)
        _http_clients[allow_private] = client
    return client


def build_ollama_model(base_url: str | None, model_name: str, subject: str) -> ResolvedModel | None:
    """Ollama model behind the egress allow-list; None when unset or not approved."""
    from app.core.config import settings
    from app.services import egress_policy

    if not base_url:
        return None

    approved = egress_policy.parse_approved_origins(settings.AI_PROVIDER_APPROVED_ORIGINS)
    origin = egress_policy.is_approved(base_url, approved)
    if origin is None:
        logger.warning(
            "ai_egress_denied",
            customer_id=subject,
            origin=egress_policy.normalize_origin(base_url),
        )
        return None

    return ResolvedModel(
        model=OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(
                base_url=f"{base_url.rstrip('/')}/v1",
                api_key="ollama",
                http_client=_shared_http_client(origin.allow_private),
            ),
        ),
        provider_name="ollama",
        model_name=model_name,
    )


@register("ollama")
class OllamaAdapter(ProviderAdapter):
    def build(self, user_key) -> ResolvedModel | None:
        from app.core.config import settings

        return build_ollama_model(
            user_key.base_url or settings.OLLAMA_URL,
            user_key.model_name,
            str(user_key.customer_id),
        )

    # validate_key not overridden — Ollama requires no live key validation
