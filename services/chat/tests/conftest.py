import os
from contextlib import ExitStack

os.environ.setdefault("CHAT_DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.api.chat_routes import get_validated_user  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.conversation import Conversation  # noqa: E402
from app.models.message import Message  # noqa: E402
from app.models.privileged_access_log import PrivilegedAccessLog  # noqa: E402
from main import app  # noqa: E402,F401
from tests.factories.user import ValidUserFactory  # noqa: E402

_DB_TABLES = [PrivilegedAccessLog.__table__, Conversation.__table__, Message.__table__]


@pytest.fixture
def db():
    """Real in-memory sqlite session — sync, matching this service's sync
    audit sinks. Add tables to _DB_TABLES as more tests need a real DB session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=_DB_TABLES)
    return sessionmaker(bind=engine)()


@pytest.fixture
def anyio_backend():
    """Run @pytest.mark.anyio tests on asyncio only (trio isn't installed)."""
    return "asyncio"


@pytest.fixture
def make_client():
    stack = ExitStack()

    def _make(**user_kwargs):
        user = ValidUserFactory(**user_kwargs)
        app.dependency_overrides[get_validated_user] = lambda: user
        client = stack.enter_context(TestClient(app))
        client.user = user
        return client

    yield _make
    stack.close()
    app.dependency_overrides = {}
