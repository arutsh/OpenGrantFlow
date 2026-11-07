"""OpenAPI -> MCP bridge over budget's public REST API (specs/chat-tool-registry.md).

Two separate FastMCP instances are built from the same spec, for two
different reasons:

- `build_schema_bridge()` — built once at startup, used only to ask
  `list_tools()` what the model-facing schemas look like. Hidden resource-id
  arguments (`budget_id`) need *some* default at this point (FastMCP refuses
  to hide a required arg with none), so this one uses a placeholder — the
  schema it produces never has that default leak into `parameters`, since
  the arg is hidden, and this instance is never used to actually call
  anything.
- `build_dispatch_bridge()` — built fresh per tool call, with a client
  carrying that call's real bearer token and (for targeted tools) the
  request's real `context_id` baked in as the hidden arg's default. Building
  it is cheap (~1-2ms, confirmed empirically — no network I/O, just
  Pydantic/schema construction), so a fresh instance per call is simpler and
  safer than trying to mutate a shared client's headers across concurrent
  users' turns.
"""

import json
from pathlib import Path
from typing import Final

import httpx
from fastmcp import FastMCP
from fastmcp.server.providers.openapi import MCPType, RouteMap
from fastmcp.server.transforms import ToolTransform
from fastmcp.tools.tool_transform import ArgTransformConfig, ToolTransformConfig

from app.core.logging import get_logger

logger = get_logger(__name__)

_CACHED_SPEC_PATH: Final = Path(__file__).parent / "cache" / "budget_openapi.json"

# operationId -> (context passed to arguments dict is the operation's own
# names, budget's real field names — renames below map model-facing names
# back onto these before building the request).
_ROUTE_MAPS: Final = [
    RouteMap(methods=["POST"], pattern=r"^/api/v1/budgets/$", mcp_type=MCPType.TOOL),
    RouteMap(methods=["PATCH"], pattern=r"^/api/v1/budgets/\{budget_id\}$", mcp_type=MCPType.TOOL),
    RouteMap(methods=["GET"], pattern=r"^/api/v1/budgets/\{budget_id\}$", mcp_type=MCPType.TOOL),
    RouteMap(methods=["POST"], pattern=r"^/api/v1/budget-lines/$", mcp_type=MCPType.TOOL),
    RouteMap(methods=["POST"], pattern=r"^/api/v1/budgets/with-lines$", mcp_type=MCPType.TOOL),
    RouteMap(pattern=r".*", mcp_type=MCPType.EXCLUDE),
]

# FastAPI-generated operationIds -> model-facing tool name.
CREATE_BUDGET = "create_budget_endpoint_api_v1_budgets"
UPDATE_BUDGET = "update_budget_endpoint_api_v1_budgets"
GET_BUDGET_SUMMARY = "get_budget_endpoint_api_v1_budgets"
ADD_BUDGET_LINE = "create_budget_line_view_api_v1_budget_lines"
# Truncated to 56 chars — FastMCP truncates the pre-transform name before ToolTransform's lookup.
CREATE_BUDGET_WITH_LINES = "create_budget_with_lines_endpoint_api_v1_budgets_with_li"


def service_root(budget_service_url: str) -> str:
    """Strip the `/api/v1` (or any path) suffix off BUDGET_SERVICE_URL.

    The spec's own paths already include `/api/v1/...` (confirmed against
    budget's real app.openapi() output), so any httpx.AsyncClient built for
    build_schema_bridge()/build_dispatch_bridge() must use the bare service
    root as base_url — combining it with settings.BUDGET_SERVICE_URL as-is
    (which the *old*, hand-written dispatchers' base_url expects) doubles
    the prefix into `/api/v1/api/v1/...` (caught by running this against a
    mocked transport before wiring it in for real).
    """
    url = httpx.URL(budget_service_url)
    return f"{url.scheme}://{url.netloc.decode()}"


def fetch_cached_spec() -> dict:
    """Load the checked-in fallback spec (services/chat/app/services/cache/budget_openapi.json).

    Refreshed manually by re-running budget's app.openapi() and overwriting
    this file — there is no automatic drift detection, so the schema-parity
    tests are what catch it going stale relative to budget's real routes.
    """
    return json.loads(_CACHED_SPEC_PATH.read_text())


async def fetch_live_spec(budget_service_url: str, http: httpx.AsyncClient) -> dict:
    """Fetch budget's real OpenAPI spec from its root (not the /api/v1-prefixed
    API itself — FastAPI serves /openapi.json unprefixed at the app root).
    """
    resp = await http.get(f"{service_root(budget_service_url)}/openapi.json", timeout=10.0)
    resp.raise_for_status()
    return resp.json()


async def load_spec(budget_service_url: str, http: httpx.AsyncClient) -> dict:
    """Startup spec fetch with cached fallback (specs/chat-tool-registry.md:
    "chat SHALL boot with a cached spec when budget's live spec is unreachable")."""
    try:
        return await fetch_live_spec(budget_service_url, http)
    except Exception as exc:
        logger.warning("budget_openapi_fetch_failed_using_cache", error=str(exc))
        return fetch_cached_spec()


def _transform_config(*, budget_id: str | None) -> ToolTransform:
    """Build the rename/hide transform. `budget_id=None` is for schema
    generation only (a placeholder default, since FastMCP requires hidden
    required args to have one); real dispatch always passes the turn's
    actual context_id.
    """
    hidden_budget_id = ArgTransformConfig(hide=True, default=budget_id or "")

    return ToolTransform(
        {
            CREATE_BUDGET: ToolTransformConfig(
                name="create_budget",
                description="Create a new, empty budget.",
                arguments={
                    "name": ArgTransformConfig(name="budget_name", required=True),
                    "external_funder_name": ArgTransformConfig(required=True),
                    "owner_id": ArgTransformConfig(hide=True),
                    "funding_customer_id": ArgTransformConfig(hide=True),
                    # Matches the old ai-driven parse-budget flow's status, so
                    # chat-created budgets get the same "needs review" UI
                    # treatment (SingleBudgetView auto-opens edit mode for
                    # ai_draft) rather than the plain-create default "draft".
                    "status": ArgTransformConfig(hide=True, default="ai_draft"),
                    "created_by": ArgTransformConfig(hide=True),
                    "updated_by": ArgTransformConfig(hide=True),
                    "updated_at": ArgTransformConfig(hide=True),
                    "created_at": ArgTransformConfig(hide=True),
                    # actual_currency/start_date were added to BudgetCreate by
                    # the currency-ledger/budget-reports work, after this tool
                    # was curated — hidden rather than silently exposed
                    # unreviewed. start_date in particular is meant to be set
                    # only via the confirm action, never at creation.
                    "actual_currency": ArgTransformConfig(hide=True),
                    "start_date": ArgTransformConfig(hide=True),
                },
            ),
            UPDATE_BUDGET: ToolTransformConfig(
                name="update_budget",
                description="Update fields on the budget currently in view.",
                arguments={
                    "budget_id": hidden_budget_id,
                    "owner_id": ArgTransformConfig(hide=True),
                    "funding_customer_id": ArgTransformConfig(hide=True),
                    "status": ArgTransformConfig(hide=True),
                    "created_by": ArgTransformConfig(hide=True),
                    "updated_by": ArgTransformConfig(hide=True),
                    "updated_at": ArgTransformConfig(hide=True),
                    "created_at": ArgTransformConfig(hide=True),
                    "id": ArgTransformConfig(hide=True),
                    # See create_budget's note — start_date is confirm-only,
                    # and actual_currency isn't yet a reviewed chat-editable
                    # field.
                    "actual_currency": ArgTransformConfig(hide=True),
                    "start_date": ArgTransformConfig(hide=True),
                },
            ),
            GET_BUDGET_SUMMARY: ToolTransformConfig(
                name="get_budget_summary",
                description="Fetch a read-only summary of the budget currently in view.",
                arguments={"budget_id": hidden_budget_id},
            ),
            ADD_BUDGET_LINE: ToolTransformConfig(
                name="add_budget_line",
                description="Add a line item to the budget currently in view.",
                arguments={
                    "budget_id": hidden_budget_id,
                    "category_name": ArgTransformConfig(required=True),
                    "category_id": ArgTransformConfig(hide=True),
                    "extra_fields": ArgTransformConfig(hide=True),
                },
            ),
            CREATE_BUDGET_WITH_LINES: ToolTransformConfig(
                name="create_budget_with_lines",
                description="Create a new budget with an initial set of line items in one call.",
                arguments={
                    "owner_id": ArgTransformConfig(hide=True),
                },
            ),
        }
    )


def build_schema_bridge(spec: dict, client: httpx.AsyncClient) -> FastMCP:
    """For list_tools() only — never used to dispatch a real call."""
    mcp = FastMCP.from_openapi(spec, client=client, name="budget", route_maps=_ROUTE_MAPS)
    mcp.add_transform(_transform_config(budget_id=None))
    return mcp


def build_dispatch_bridge(
    spec: dict, client: httpx.AsyncClient, *, budget_id: str | None
) -> FastMCP:
    """For a single call_tool() — rebuilt per turn with that turn's real JWT
    (baked into `client`'s default headers) and, for targeted tools, that
    turn's real budget_id baked in as the hidden argument's default.
    """
    mcp = FastMCP.from_openapi(spec, client=client, name="budget", route_maps=_ROUTE_MAPS)
    mcp.add_transform(_transform_config(budget_id=budget_id))
    return mcp
