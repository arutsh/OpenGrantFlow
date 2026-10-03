import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from opentelemetry import trace
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider

from app.api import decide_routes, excel_extraction_routes, parse_routes, settings_routes
from app.core.config import settings
from app.core.exceptions import DomainError, PermissionDenied
from app.core.logging import setup_logging, get_logger
from app.db.session import AsyncSessionLocal, engine
from app.services.guide_doc_ingestion import ingest_guide_docs
from app.services.privileged_access_audit import write_privileged_access_log
from app.services.site_content_ingestion import ingest_site_content
from shared.exceptions.error_handlers import domain_error_handler, unhandled_exception_handler
from shared.observability import (
    init_logging,
    init_observability,
    instrument_fastapi,
    metrics_endpoint,
)
from shared.security.privileged_access import register_privileged_access_sink

setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)

init_observability("ai-service")
init_logging("ai-service")

register_privileged_access_sink(write_privileged_access_log)

# Async engines need explicit instrumentation — init_observability hooks into sync engine
# creation events which don't fire for create_async_engine.
SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
RedisInstrumentor().instrument()

if os.getenv("VSCODE_DEBUGGER") == "1":
    try:
        import debugpy

        debugpy.listen(("0.0.0.0", 5682))
        print("✅ VS Code debugger is listening on port 5682")
    except Exception:
        pass


async def _ingest_site_knowledge() -> None:
    # A failed reindex must not stop the service; the previous index keeps serving.
    try:
        async with AsyncSessionLocal() as db:
            await ingest_site_content(db, Path(settings.SITE_CONTENT_DIR))
            await ingest_guide_docs(
                db, Path(settings.GUIDE_DOCS_DIR), Path(settings.PRODUCT_DOC_PATH)
            )
        logger.info("site_knowledge_index_ingested")
    except Exception:
        logger.exception("site_knowledge_index_ingest_failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", service="ai")
    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
    if os.getenv("ENV") != "test":
        await _ingest_site_knowledge()
    yield
    await app.state.http_client.aclose()
    logger.info("app_shutdown", service="ai")
    provider = trace.get_tracer_provider()
    if isinstance(provider, SDKTracerProvider):
        provider.force_flush(timeout_millis=5000)


app = FastAPI(title="AI Service", lifespan=lifespan)

instrument_fastapi(app)

app.include_router(parse_routes.router, prefix="/api/v1")
app.include_router(settings_routes.router, prefix="/api/v1")
app.include_router(decide_routes.router, prefix="/api/v1")
app.include_router(excel_extraction_routes.router, prefix="/api/v1")
app.add_route("/metrics", metrics_endpoint, methods=["GET"])

app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(PermissionDenied, domain_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="AI Service API",
        version="1.0.0",
        description="AI-powered budget parsing service",
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
