"""Anonymous site assistant (specs/site-assistant). No user-auth dependency, so no tenant data."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.services import site_assistant
from app.services.human_verification import HumanVerifier, get_human_verifier
from app.services.provider import resolve_site_assistant_model
from app.services.site_retrieval import Persona

router = APIRouter(prefix="/ai/site-assistant", tags=["Site Assistant"])


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    persona: Persona | None = None


class SiteAssistantConfig(BaseModel):
    enabled: bool
    max_question_chars: int


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

    if not await verifier.verify(request):
        raise HTTPException(status_code=403, detail={"code": "verification_failed"})

    resolved = resolve_site_assistant_model()
    if resolved is None:
        raise HTTPException(status_code=503, detail={"code": "assistant_unavailable"})

    try:
        return await site_assistant.ask(db, question, body.persona, resolved)
    except site_assistant.SiteAssistantUnavailable:
        raise HTTPException(status_code=503, detail={"code": "assistant_unavailable"}) from None
