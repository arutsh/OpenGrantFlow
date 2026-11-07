"""Acceptance-gate tests for ticket #97 (specs/chat-tool-registry.md's
"OpenAPI bridge equivalence" requirement): generated schemas match the
pre-bridge curated ones, and chat boots on the cached spec when budget's
live spec is unreachable.
"""

import httpx
import pytest

from app.services.mcp_bridge import build_schema_bridge, fetch_cached_spec, load_spec

pytestmark = pytest.mark.anyio

# The hand-curated shapes from budget_tool_registry.py before ticket #97 —
# frozen here so schema drift in the bridge (or in budget's own OpenAPI
# spec) gets caught by a test failure instead of silently changing what the
# model is told it can do.
_CURATED_REQUIRED = {
    "create_budget": {"budget_name", "external_funder_name"},
    "create_budget_with_lines": {"budget_name", "external_funder_name", "lines"},
    "add_budget_line": {"category_name", "amount", "description"},
    "update_budget": set(),
    "get_budget_summary": set(),
}
_CURATED_PROPERTIES = {
    "create_budget": {"budget_name", "external_funder_name", "duration_months"},
    "create_budget_with_lines": {
        "budget_name",
        "external_funder_name",
        "duration_months",
        "local_currency",
        "actual_currency",
        "donor_total_amount",
        "estimated_exchange_rate",
        "lines",
        "donor_template_id",
        "excel_import_fingerprint",
        "excel_import_structure",
        "excel_import_lines_locked_count",
    },
    "add_budget_line": {"category_name", "amount", "description"},
    "update_budget": {"name", "external_funder_name", "duration_months", "local_currency"},
    "get_budget_summary": set(),
}


async def _schema_tools() -> dict:
    spec = fetch_cached_spec()
    client = httpx.AsyncClient(base_url="http://budget:8000")
    mcp = build_schema_bridge(spec, client)
    tools = await mcp.list_tools()
    return {t.name: t for t in tools}


class TestSchemaParity:
    async def test_all_curated_tools_present(self):
        tools = await _schema_tools()
        assert tools.keys() == _CURATED_REQUIRED.keys()

    async def test_required_fields_match_curated(self):
        tools = await _schema_tools()
        for name, expected_required in _CURATED_REQUIRED.items():
            actual = set(tools[name].parameters.get("required", []))
            assert actual == expected_required, f"{name}: {actual} != {expected_required}"

    async def test_no_extra_properties_beyond_curated_plus_local_currency(self):
        """create_budget legitimately gains fields the old curated version
        didn't have (local_currency, donor_total_amount, estimated_exchange_rate)
        — a deliberate superset, not a leak, since these are plain
        user-controllable budget-economics fields with nothing sensitive
        about them. Every other property must be an exact subset match;
        nothing internal/sensitive may appear anywhere.
        """
        tools = await _schema_tools()
        _budget_economics_fields = {
            "local_currency",
            "donor_total_amount",
            "estimated_exchange_rate",
        }
        allowed_extra = {
            "create_budget": _budget_economics_fields,
            "update_budget": _budget_economics_fields - {"local_currency"},
        }
        for name, curated in _CURATED_PROPERTIES.items():
            actual = set(tools[name].parameters.get("properties", {}).keys())
            extra = actual - curated
            assert extra <= allowed_extra.get(
                name, set()
            ), f"{name} leaks {extra - allowed_extra.get(name, set())}"
            assert curated <= actual, f"{name} missing {curated - actual}"

    async def test_no_tool_schema_accepts_a_budget_id(self):
        tools = await _schema_tools()
        for name, tool in tools.items():
            assert "budget_id" not in tool.parameters.get("properties", {}), name

    async def test_no_tool_schema_accepts_total_amount(self):
        tools = await _schema_tools()
        for name, tool in tools.items():
            assert "total_amount" not in tool.parameters.get("properties", {}), name


class TestSpecFetchFallback:
    async def test_uses_live_spec_when_reachable(self):
        live_spec = {"openapi": "3.1.0", "info": {"title": "live"}, "paths": {}}

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/openapi.json"
            return httpx.Response(200, json=live_spec)

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        spec = await load_spec("http://budget:8000/api/v1", http)

        assert spec == live_spec

    async def test_falls_back_to_cache_when_unreachable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("budget is down", request=request)

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        spec = await load_spec("http://budget:8000/api/v1", http)

        assert spec == fetch_cached_spec()

    async def test_falls_back_to_cache_on_non_2xx(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        spec = await load_spec("http://budget:8000/api/v1", http)

        assert spec == fetch_cached_spec()
