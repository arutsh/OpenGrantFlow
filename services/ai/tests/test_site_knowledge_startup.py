"""Startup ingestion must not take the service down when indexing fails."""

import pytest

import main


@pytest.mark.anyio
async def test_ingest_failure_is_logged_not_raised(monkeypatch):
    async def boom(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(main, "ingest_site_content", boom)

    await main._ingest_site_knowledge()
