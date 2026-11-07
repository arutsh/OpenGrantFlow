"""Tests for BudgetToolRegistry post-#97 (OpenAPI -> MCP bridge dispatch).

Uses the real cached spec + httpx.MockTransport, so requests actually flow
through FastMCP's OpenAPI bridge (RequestDirector, transforms) rather than
mocking httpx.AsyncClient directly — this is what actually proves the
rename/hide/inject transforms behave correctly, not just that our own code
calls the right MagicMock.
"""

import json

import httpx
import pytest

from app.services.budget_tool_registry import BudgetToolRegistry
from app.services.mcp_bridge import fetch_cached_spec

pytestmark = pytest.mark.anyio

_SPEC = fetch_cached_spec()


async def _registry(tool_handler) -> BudgetToolRegistry:
    """initialize() fetches /openapi.json before any tool call happens —
    route that specifically to the real cached spec, everything else to the
    test's own handler for the actual dispatch under test.
    """

    def combined_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json=_SPEC)
        return tool_handler(request)

    http = httpx.AsyncClient(
        base_url="http://budget:8000/api/v1", transport=httpx.MockTransport(combined_handler)
    )
    registry = BudgetToolRegistry(http, "http://budget:8000/api/v1")
    await registry.initialize()
    return registry


def _json_handler(status_code: int, body):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    return handler


def _capturing_json_handler(sent: list, status_code: int, body):
    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(status_code, json=body)

    return handler


def _malformed_2xx_handler(sent: list):
    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, content=b"<html>not json</html>")

    return handler


class TestListTools:
    async def test_budgets_page_returns_curated_tools(self):
        registry = await _registry(_json_handler(200, {}))
        tools = registry.list_tools("budgets")
        assert {t.name for t in tools} == {
            "create_budget",
            "create_budget_with_lines",
            "add_budget_line",
            "update_budget",
            "get_budget_summary",
        }

    async def test_no_page_returns_no_tools(self):
        registry = await _registry(_json_handler(200, {}))
        assert registry.list_tools(None) == []

    async def test_tool_schemas_never_contain_a_budget_id(self):
        registry = await _registry(_json_handler(200, {}))
        for tool in registry.list_tools("budgets"):
            assert "budget_id" not in tool.parameters.get("properties", {})

    async def test_no_internal_fields_leak_through(self):
        """Internal fields in the raw create/update schemas must stay hidden; total_amount
        is no longer in the spec at all, but stays listed as a regression guard."""
        registry = await _registry(_json_handler(200, {}))
        internal_fields = {
            "owner_id",
            "funding_customer_id",
            "status",
            "total_amount",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "id",
            "category_id",
            "extra_fields",
        }
        for tool in registry.list_tools("budgets"):
            leaked = internal_fields & tool.parameters.get("properties", {}).keys()
            assert not leaked, f"{tool.name} leaks {leaked}"


class TestTargetedTools:
    def test_targeted_set_excludes_create(self):
        assert BudgetToolRegistry.targeted_tools == {
            "add_budget_line",
            "update_budget",
            "get_budget_summary",
        }

    def test_creating_tools_and_resource_id_param(self):
        assert BudgetToolRegistry.creating_tools == {"create_budget", "create_budget_with_lines"}
        assert BudgetToolRegistry.resource_id_param == "budget_id"


class TestCallCreateBudget:
    async def test_success_returns_budget_id(self):
        sent: list = []
        registry = await _registry(
            _capturing_json_handler(sent, 200, {"id": "budget-1", "name": "USAID Grant"})
        )

        result = await registry.call_tool(
            "create_budget",
            {"budget_name": "USAID Grant", "external_funder_name": "USAID"},
            token="tok",
        )

        assert result.success is True
        assert result.created_resource_id == "budget-1"
        (req,) = sent
        assert req.method == "POST"
        assert str(req.url) == "http://budget:8000/api/v1/budgets/"
        assert json.loads(req.content) == {
            "name": "USAID Grant",
            "external_funder_name": "USAID",
            "status": "ai_draft",
        }
        assert req.headers["authorization"] == "Bearer tok"

    async def test_success_message_never_embeds_the_raw_id(self):
        """specs/chat-url-context.md: "the raw id SHALL NOT be rendered in the
        chat transcript" — this message becomes the assistant's chat bubble."""
        registry = await _registry(_json_handler(200, {"id": "budget-1", "name": "USAID Grant"}))

        result = await registry.call_tool(
            "create_budget",
            {"budget_name": "USAID Grant", "external_funder_name": "USAID"},
            token="tok",
        )

        assert "budget-1" not in result.message

    async def test_domain_rejection_relayed_not_raised(self):
        registry = await _registry(_json_handler(422, {"detail": "Funding source is required"}))

        result = await registry.call_tool(
            "create_budget", {"budget_name": "X", "external_funder_name": "Y"}, token="tok"
        )

        assert result.success is False
        assert "Failed to create budget" in result.message

    async def test_invalid_currency_422_relayed_with_detail(self):
        detail = "actual_currency: Value error, ABC is not a valid ISO 4217 currency code"
        registry = await _registry(_json_handler(422, {"detail": detail}))

        result = await registry.call_tool(
            "create_budget_with_lines",
            {"budget_name": "X", "external_funder_name": "Y", "lines": []},
            token="tok",
        )

        assert result.success is False
        assert "ISO 4217" in result.message


class TestCallCreateBudgetWithLines:
    async def test_success_returns_budget_id(self):
        sent: list = []
        registry = await _registry(
            _capturing_json_handler(sent, 200, {"id": "budget-1", "name": "Imported Budget"})
        )

        result = await registry.call_tool(
            "create_budget_with_lines",
            {
                "budget_name": "Imported Budget",
                "external_funder_name": "Imported budget",
                "lines": [
                    {"category_name": "Travel", "description": "Flights", "amount": 500},
                ],
                "donor_template_id": 7,
            },
            token="tok",
        )

        assert result.success is True
        assert result.created_resource_id == "budget-1"
        (req,) = sent
        assert str(req.url) == "http://budget:8000/api/v1/budgets/with-lines"
        body = json.loads(req.content)
        assert body["donor_template_id"] == 7
        assert body["lines"] == [
            {"category_name": "Travel", "description": "Flights", "amount": 500}
        ]

    async def test_success_message_never_embeds_the_raw_id(self):
        registry = await _registry(_json_handler(200, {"id": "budget-1"}))

        result = await registry.call_tool(
            "create_budget_with_lines",
            {"budget_name": "X", "external_funder_name": "Y", "lines": []},
            token="tok",
        )

        assert "budget-1" not in result.message

    async def test_domain_rejection_relayed_not_raised(self):
        registry = await _registry(_json_handler(400, {"detail": "No budget lines"}))

        result = await registry.call_tool(
            "create_budget_with_lines",
            {"budget_name": "X", "external_funder_name": "Y", "lines": []},
            token="tok",
        )

        assert result.success is False
        assert "Failed to create budget with lines" in result.message


class TestCallAddBudgetLine:
    async def test_injects_budget_id_from_params(self):
        sent: list = []
        registry = await _registry(_capturing_json_handler(sent, 200, {"id": "line-1"}))

        result = await registry.call_tool(
            "add_budget_line",
            {
                "category_name": "Travel",
                "amount": 500,
                "budget_id": "budget-1",
                "description": "Travel",
            },
            token="tok",
        )

        assert result.success is True
        body = json.loads(sent[0].content)
        assert body["budget_id"] == "budget-1"
        assert body["description"] == "Travel"
        assert str(sent[0].url) == "http://budget:8000/api/v1/budget-lines/"

    async def test_success_message_never_embeds_the_raw_line_id(self):
        registry = await _registry(_json_handler(200, {"id": "line-1"}))

        result = await registry.call_tool(
            "add_budget_line",
            {
                "category_name": "Travel",
                "amount": 500,
                "budget_id": "budget-1",
                "description": "Travel",
            },
            token="tok",
        )

        assert "line-1" not in result.message

    async def test_malformed_2xx_body_reported_as_failure(self):
        sent: list = []
        registry = await _registry(_malformed_2xx_handler(sent))

        result = await registry.call_tool(
            "add_budget_line",
            {
                "category_name": "Travel",
                "amount": 500,
                "budget_id": "budget-1",
                "description": "Travel",
            },
            token="tok",
        )

        assert result.success is False


class TestCallUpdateBudget:
    async def test_patches_only_provided_fields(self):
        sent: list = []
        registry = await _registry(_capturing_json_handler(sent, 200, {}))

        await registry.call_tool(
            "update_budget", {"name": "New Name", "budget_id": "budget-1"}, token="tok"
        )

        assert json.loads(sent[0].content) == {"name": "New Name"}
        assert str(sent[0].url) == "http://budget:8000/api/v1/budgets/budget-1"

    async def test_success_message_never_embeds_the_raw_budget_id(self):
        registry = await _registry(_json_handler(200, {}))

        result = await registry.call_tool(
            "update_budget", {"name": "New Name", "budget_id": "budget-1"}, token="tok"
        )

        assert "budget-1" not in result.message


class TestCallGetBudgetSummary:
    async def test_summarizes_lines(self):
        body = {
            "name": "USAID Grant",
            "lines": [{"description": "Travel", "amount": 500}],
        }
        sent: list = []
        registry = await _registry(_capturing_json_handler(sent, 200, body))

        result = await registry.call_tool(
            "get_budget_summary", {"budget_id": "budget-1"}, token="tok"
        )

        assert result.success is True
        assert "USAID Grant" in result.message
        assert "1 lines" in result.message
        assert str(sent[0].url) == "http://budget:8000/api/v1/budgets/budget-1"
        assert sent[0].method == "GET"
