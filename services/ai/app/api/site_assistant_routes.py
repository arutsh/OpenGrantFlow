"""Anonymous site assistant (specs/site-assistant). No user-auth dependency, so no tenant data."""

from collections.abc import Generator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.services import site_assistant
from app.services.human_verification import HumanVerifier, get_human_verifier
from app.services.provider import resolve_site_assistant_model
from app.services.rate_limiter import (
    CapStoreUnavailable,
    DailyCapReached,
    enforce_daily_cap,
    hash_client_ip,
)
from app.services.site_retrieval import Persona

router = APIRouter(prefix="/ai/site-assistant", tags=["Site Assistant"])

PER_IP_SCOPE = "site-assistant-ip"
GLOBAL_SCOPE = "site-assistant-global"


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    persona: Persona | None = None


class SiteAssistantConfig(BaseModel):
    enabled: bool
    max_question_chars: int


@contextmanager
def _cap_errors_as_http() -> Generator[None, None, None]:
    try:
        yield
    except DailyCapReached as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "daily_cap_reached"},
            headers={"Retry-After": str(exc.retry_after)},
        ) from None
    except CapStoreUnavailable:
        raise HTTPException(status_code=503, detail={"code": "assistant_unavailable"}) from None


def _require_enabled() -> None:
    if not settings.SITE_ASSISTANT_ENABLED:
        raise HTTPException(status_code=404)


@router.get("/config", response_model=SiteAssistantConfig)
async def site_assistant_config() -> SiteAssistantConfig:
    return SiteAssistantConfig(
        enabled=settings.SITE_ASSISTANT_ENABLED,
        max_question_chars=settings.SITE_ASSISTANT_MAX_QUESTION_CHARS,
    )


@router.post(
    "/ask", response_model=site_assistant.AskResponse, dependencies=[Depends(_require_enabled)]
)
async def ask_route(
    body: AskRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    verifier: HumanVerifier = Depends(get_human_verifier),
) -> site_assistant.AskResponse:
    question = body.question.strip()
    if not question or len(question) > settings.SITE_ASSISTANT_MAX_QUESTION_CHARS:
        raise HTTPException(status_code=422, detail={"code": "invalid_question_length"})

    # Uvicorn's proxy-headers resolve client.host from the X-Forwarded-For the gateway overwrites.
    client_ip = request.client.host if request.client else "unknown"
    with _cap_errors_as_http():
        await enforce_daily_cap(
            PER_IP_SCOPE, hash_client_ip(client_ip), settings.site_assistant_per_ip_cap
        )

    if not await verifier.verify(request):
        raise HTTPException(status_code=403, detail={"code": "verification_failed"})

    resolved = resolve_site_assistant_model()
    if resolved is None:
        raise HTTPException(status_code=503, detail={"code": "assistant_unavailable"})

    async def _enforce_global_cap() -> None:
        await enforce_daily_cap(GLOBAL_SCOPE, "all", settings.site_assistant_global_cap)

    try:
        with _cap_errors_as_http():
            return await site_assistant.ask(
                db, question, body.persona, resolved, before_model_call=_enforce_global_cap
            )
    except site_assistant.SiteAssistantUnavailable:
        raise HTTPException(status_code=503, detail={"code": "assistant_unavailable"}) from None
