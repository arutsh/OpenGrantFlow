"""Throwaway-schema Postgres sessions for tests that need real full-text search."""

import gc
import os
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import Table, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base

PG_URL = os.environ.get("AI_TEST_POSTGRES_URL")

# Skip locally without a DB, but never in CI, so a lost service fails loudly instead.
requires_postgres = pytest.mark.skipif(
    not PG_URL and not os.environ.get("CI"),
    reason="AI_TEST_POSTGRES_URL not set; ts_rank_cd needs real Postgres",
)


@asynccontextmanager
async def postgres_schema_session(
    prefix: str, tables: list[Table]
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a session bound to a fresh schema holding `tables`, dropped afterwards."""
    if not PG_URL:
        raise RuntimeError("AI_TEST_POSTGRES_URL must be set to run Postgres-backed tests")
    url = make_url(PG_URL).set(drivername="postgresql+asyncpg")
    schema = f"{prefix}_{uuid.uuid4().hex[:12]}"

    admin = create_async_engine(url)
    async with admin.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=tables)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()
        gc.collect()
