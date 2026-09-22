"""Users-service test bootstrap.

Everything here must run before any test module imports `main`:
importing it initializes OpenTelemetry, and main.py's lifespan awaits
init_db() (a real Postgres connection) on startup.
"""

import os
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch
from uuid import uuid4

os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import app.db.init_db as _init_db_module  # noqa: E402

# main.py's lifespan awaits init_db() on startup; tests have no database.
_init_db_module.init_db = AsyncMock()

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from main import app  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.customer import CustomerModel, DonorGranteeModel  # noqa: E402
from app.models.privileged_access_log import PrivilegedAccessLog  # noqa: E402
from app.models.user import UserModel  # noqa: E402
from app.utils.security import get_current_user  # noqa: E402
from shared.security.dependencies import get_validated_user  # noqa: E402
from shared.security.jwt_utils import create_access_token  # noqa: E402
from tests.factories.user import ValidUserFactory  # noqa: E402


@pytest.fixture
def anyio_backend():
    """asyncio only — matches services/ai/tests' sibling fixture."""
    return "asyncio"


@pytest.fixture
async def db():
    """Real in-memory async sqlite session (Customer/DonorGrantee/PrivilegedAccessLog/User);
    mirrors services/ai/tests/test_email_verified_gate.py's TestClient+real-session pattern."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                CustomerModel.__table__,
                DonorGranteeModel.__table__,
                PrivilegedAccessLog.__table__,
                UserModel.__table__,
            ],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def _token_for(user_id: str, **extra_claims) -> str:
    """A real signed JWT, for tests that need get_validated_user's contextvar side effect."""
    return create_access_token(
        {
            "user_id": user_id,
            "session_id": str(uuid4()),
            "role": "user",
            "email_verified": True,
            **extra_claims,
        }
    )


@pytest.fixture
def make_client():
    """Build a TestClient with a fake authenticated user and (optionally) a
    mocked outbound AI service.

    Usage:
        client = make_client()                  # no outbound HTTP expected
        client = make_client(handler=handler)   # httpx.MockTransport handler
        client = make_client(is_donor=True)      # override any JWT field
        client = make_client(db=db)              # route the get_db dependency to
                                                  # a real session (see the `db`
                                                  # fixture above) — the calling
                                                  # test must be async
                                                  # (@pytest.mark.anyio), since
                                                  # `db` is an async fixture
        client.user                             # the fake JWT payload dict

    Overrides both get_current_user and get_validated_user with the same fake
    payload, since routes depend on either one depending on how much of the
    JWT claims they need (donor-grantee routes need get_validated_user's full
    payload for customer_id/is_donor/is_ngo).

    The users lifespan connects to RabbitMQ (init_publisher) — patched out —
    and creates app.state.http_client, which is replaced by a MockTransport
    client when a handler is given.
    """
    stack = ExitStack()

    def _make(handler=None, db=None, **user_kwargs):
        user = ValidUserFactory(**user_kwargs)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_validated_user] = lambda: user
        if db is not None:
            app.dependency_overrides[get_db] = lambda: db
        stack.enter_context(patch("main.init_publisher", AsyncMock()))
        stack.enter_context(patch("main.close_publisher", AsyncMock()))
        client = stack.enter_context(TestClient(app))
        if handler is not None:
            app.state.http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client.user = user
        return client

    yield _make
    stack.close()
    app.dependency_overrides = {}
