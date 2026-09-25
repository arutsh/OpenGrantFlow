"""Budget-service test bootstrap.

Everything here must run before any test module imports `main`: importing
it initializes OpenTelemetry, and app.db.session creates the async engine
at import time.
"""

import os
from uuid import uuid4

os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from main import app  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.budget import BudgetModel, BudgetLineModel, BudgetCategoryModel  # noqa: E402
from app.models.mapping import DonorTemplateModel  # noqa: E402
from app.models.report import ReportModel, ReportLineModel, AttachmentModel  # noqa: E402
from app.models.currency_ledger import (  # noqa: E402
    FundingReceiptModel,
    CurrencyConversionModel,
    ReportLineConversionAllocationModel,
)
from app.models.privileged_access_log import PrivilegedAccessLog  # noqa: E402
from app.models.export_template import ExportTemplateModel  # noqa: E402
from shared.security.dependencies import get_validated_user  # noqa: E402
from shared.security.jwt_utils import create_access_token  # noqa: E402
from tests.factories.user import ValidUserFactory  # noqa: E402


@pytest.fixture
def anyio_backend():
    """Run @pytest.mark.anyio tests on asyncio only.

    anyio's built-in fixture parametrizes every anyio test over both asyncio
    and trio, but this service is asyncio-only and trio isn't installed.
    """
    return "asyncio"


@pytest.fixture
async def db():
    """Real in-memory async sqlite session covering Budget/BudgetLine/BudgetCategory/
    DonorTemplate/Report/ReportLine/Attachment/FundingReceipt/CurrencyConversion/
    ReportLineConversionAllocation/PrivilegedAccessLog — shared by any test that
    exercises budget<->report behavior against real SQLAlchemy relationships rather
    than mocking every crud call (see test_report_routes.py and
    test_budget_confirmation_lifecycle.py).
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                BudgetModel.__table__,
                BudgetLineModel.__table__,
                BudgetCategoryModel.__table__,
                DonorTemplateModel.__table__,
                ReportModel.__table__,
                ReportLineModel.__table__,
                AttachmentModel.__table__,
                FundingReceiptModel.__table__,
                CurrencyConversionModel.__table__,
                ReportLineConversionAllocationModel.__table__,
                PrivilegedAccessLog.__table__,
                ExportTemplateModel.__table__,
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
    """Build a TestClient authenticated as a fresh fake user.

    Usage:
        client = make_client()                    # regular user
        client = make_client(role="superuser")    # override any JWT field
        client = make_client(db=db)               # route the get_db dependency to
                                                    # a real session (see the `db`
                                                    # fixture above) — the calling
                                                    # test must be async
                                                    # (@pytest.mark.anyio), since
                                                    # `db` is an async fixture
        client.user                                # the fake JWT payload dict

    Older test files carry their own autouse auth override; new tests should
    use this instead.
    """

    def _make(db=None, **user_kwargs):
        user = ValidUserFactory(**user_kwargs)
        app.dependency_overrides[get_validated_user] = lambda: user
        if db is not None:
            app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)
        client.user = user
        return client

    yield _make
    app.dependency_overrides = {}
