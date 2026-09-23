# /services/budget/app/main.py
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Must run before any app.* import — app.db.session creates the engine at import time.
from shared.observability import (
    init_logging,
    init_observability,
    instrument_fastapi,
    metrics_endpoint,
)
from shared.security.privileged_access import register_privileged_access_sink

init_observability("budget-service")

from app.api import (  # noqa: E402
    budget_routes,
    budget_line_routes,
    budget_category_routes,
    mapping_routes,
    report_routes,
    report_line_routes,
    attachment_routes,
    funding_receipt_routes,
    currency_conversion_routes,
    health_routes,
)
from fastapi.openapi.utils import get_openapi  # noqa: E402
from app.core.exceptions import DomainError, PermissionDenied  # noqa: E402
from shared.exceptions.error_handlers import (  # noqa: E402
    domain_error_handler,
    unhandled_exception_handler,
)
from app.core.config import settings  # noqa: E402
from app.core.logging import setup_logging, get_logger  # noqa: E402
from app.services.user_client import (  # noqa: E402
    init_urls as user_client_init_urls,
    close_urls as close_user_client_urls,
)
from app.services.customer_client import (  # noqa: E402
    init_urls as customer_client_init_urls,
    close_urls as close_customer_client_urls,
)
from app.services.event_consumer import init_consumer, close_consumer, start_consumer  # noqa: E402
from app.services.privileged_access_audit import write_privileged_access_log  # noqa: E402

setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)

register_privileged_access_sink(write_privileged_access_log)

init_logging("budget-service")

# Only enable debugpy when running in VSCode
if os.getenv("VSCODE_DEBUGGER") == "1":
    try:
        import debugpy

        debugpy.listen(("0.0.0.0", 5680))
        print("✅ VS Code debugger is listening on port 5680")
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    logger.info("app_startup", service="budget")
    try:
        async with asyncio.timeout(30):
            await user_client_init_urls()
            logger.info("user_client_initialized")
            await customer_client_init_urls()
            logger.info("customer_client_initialized")
            await init_consumer()
            logger.info("event_consumer_initialized")
            await start_consumer()
            logger.info("event_consumer_started")
    except asyncio.TimeoutError:
        logger.error("startup_timeout", timeout_seconds=30, service="budget")
        raise

    yield

    logger.info("app_shutdown", service="budget")
    await close_user_client_urls()
    await close_customer_client_urls()
    await close_consumer()
    logger.info("event_consumer_stopped")


# Donot create dbs on startup, it has to go through migrations.
# Base.metadata.create_all(bind=engine)
app = FastAPI(title="Budget Service", lifespan=lifespan)

# Instrument FastAPI AFTER app creation
instrument_fastapi(app)

app.include_router(health_routes.router)
app.include_router(budget_routes.router, prefix="/api/v1")
app.include_router(budget_routes.private_router, prefix="/api/private/v1")
app.include_router(budget_line_routes.router, prefix="/api/v1")
app.include_router(budget_category_routes.router, prefix="/api/v1")
app.include_router(mapping_routes.router, prefix="/api/v1")
app.include_router(report_routes.router, prefix="/api/v1")
app.include_router(report_line_routes.router, prefix="/api/v1")
app.include_router(attachment_routes.router, prefix="/api/v1")
app.include_router(funding_receipt_routes.router, prefix="/api/v1")
app.include_router(currency_conversion_routes.router, prefix="/api/v1")

app.add_route("/metrics", metrics_endpoint, methods=["GET"])

# Register global exception handler
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(PermissionDenied, domain_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Budget Service API",
        version="1.0.0",
        description="API for managing budgets and budget lines",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema

    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore
