from typing import Protocol

from fastapi import Request

from app.core.config import settings


class HumanVerifier(Protocol):
    async def verify(self, request: Request) -> bool: ...


class NoopVerifier:
    """Default verifier: allows every request until bot protection is configured."""

    async def verify(self, request: Request) -> bool:
        return True


_VERIFIERS: dict[str, type[HumanVerifier]] = {"none": NoopVerifier}


def get_human_verifier() -> HumanVerifier:
    return _VERIFIERS[settings.SITE_ASSISTANT_HUMAN_VERIFIER]()
