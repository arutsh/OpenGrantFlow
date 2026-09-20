import pytest

from app.api.parse_routes import get_validated_user
from app.services.provider import get_resolved_model
from tests.factories.user import ValidUserFactory
from tests.factories.provider import ResolvedModelFactory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import os

os.environ.setdefault("AI_DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.privileged_access_log import PrivilegedAccessLog  # noqa: E402
from app.models.audit_log import AIAuditLog  # noqa: E402
from app.models.prompt import AIPrompt  # noqa: E402
from app.models.user_provider_key import UserProviderKey  # noqa: E402
from app.models.customer_ai_defaults import CustomerAiDefaults  # noqa: E402
from app.models.ai_provider import AIProvider  # noqa: E402

_DB_TABLES = [
    PrivilegedAccessLog.__table__,
    AIAuditLog.__table__,
    AIPrompt.__table__,
    AIProvider.__table__,
    UserProviderKey.__table__,
    CustomerAiDefaults.__table__,
]


@pytest.fixture
def db():
    """Real in-memory sqlite session — sync, matching this service's sync
    audit sinks. Add tables to _DB_TABLES as more tests need a real DB session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=_DB_TABLES)
    return sessionmaker(bind=engine)()


@pytest.fixture(autouse=True)
def _no_platform_fallback_by_default():
    """Default resolve_with_platform_fallback to None so unpatched tests don't hit a real DB."""
    with (
        patch(
            "app.api.decide_routes.resolve_with_platform_fallback",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.api.parse_routes.resolve_with_platform_fallback",
            new=AsyncMock(return_value=None),
        ),
    ):
        yield


@pytest.fixture
def anyio_backend():
    """Run @pytest.mark.anyio tests on asyncio only.

    anyio's built-in fixture parametrizes every anyio test over both asyncio
    and trio, but this service is asyncio-only and trio isn't installed.
    """
    return "asyncio"


@pytest.fixture
def make_client():
    stack = ExitStack()

    def _make(resolved=None, **user_kwargs):
        user = ValidUserFactory(**user_kwargs)
        model = ResolvedModelFactory() if resolved else None
        app.dependency_overrides[get_validated_user] = lambda: user
        app.dependency_overrides[get_resolved_model] = lambda: model
        client = stack.enter_context(TestClient(app))
        client.user = user
        return client

    yield _make
    stack.close()
    app.dependency_overrides = {}
