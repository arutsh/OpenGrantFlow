"""Budget.total_amount is derived from its lines on read (money-integrity Decision 5)."""

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.factories.user import ValidUserFactory
from tests.factories.budget import BudgetCategoryFactory, BudgetFactory, BudgetLineFactory
from app.models.budget import BudgetModel
from app.schemas import BudgetLineCreate
from app.services.budget_line_services import create_budget_line_service

pytestmark = pytest.mark.anyio

OWNER_ID = str(uuid4())


async def _seed(db, *amounts):
    budget = BudgetFactory.build(owner_id=OWNER_ID)
    category = BudgetCategoryFactory.build(budget=budget)
    lines = [
        BudgetLineFactory.build(
            budget=budget, category=category, category_id=category.id, amount=Decimal(a)
        )
        for a in amounts
    ]
    db.add_all([budget, category, *lines])
    await db.commit()
    return budget.id, category.id, [line.id for line in lines]


async def _total(db, budget_id):
    query = select(BudgetModel.total_amount).where(BudgetModel.id == budget_id)
    return (await db.execute(query)).scalar_one()


class TestDerivedTotalViaRoutes:
    async def test_budget_with_no_lines_totals_zero(self, db):
        budget_id, _, _ = await _seed(db)

        assert await _total(db, budget_id) == 0

    async def test_adding_a_line_raises_the_total(self, db, make_client):
        budget_id, category_id, _ = await _seed(db, "1000")
        client = make_client(db=db, customer_id=OWNER_ID)

        response = client.post(
            "/api/v1/budget-lines/",
            json={
                "budget_id": str(budget_id),
                "category_id": str(category_id),
                "description": "Coordinator",
                "amount": 500,
            },
        )

        assert response.status_code == 200
        assert await _total(db, budget_id) == Decimal("1500")

    async def test_updating_a_line_amount_changes_the_total(self, db, make_client):
        budget_id, _, (line_id, _) = await _seed(db, "500", "1000")
        client = make_client(db=db, customer_id=OWNER_ID)

        response = client.patch(
            f"/api/v1/budget-lines/{line_id}/",
            json={"budget_id": str(budget_id), "amount": 300},
        )

        assert response.status_code == 200
        assert await _total(db, budget_id) == Decimal("1300")

    async def test_deleting_a_line_lowers_the_total(self, db, make_client):
        budget_id, _, (line_id, _) = await _seed(db, "300", "1000")
        client = make_client(db=db, customer_id=OWNER_ID)

        response = client.delete(f"/api/v1/budget-lines/{line_id}/")

        assert response.status_code == 200
        assert await _total(db, budget_id) == Decimal("1000")


class TestCreateLineTransaction:
    async def test_new_category_joins_the_line_commit(self):
        budget = BudgetFactory.build(owner_id=OWNER_ID)
        line = BudgetLineFactory.build(budget=budget)
        payload = BudgetLineCreate(
            budget_id=budget.id, description="Travel", amount=100, category_name="Travel"
        )

        with (
            patch("app.services.budget_line_services.get_budget", return_value=budget),
            patch(
                "app.services.budget_line_services.get_or_create_category_service",
                return_value=line.category,
            ) as mock_category,
            patch("app.services.budget_line_services.create_budget_line", return_value=line),
        ):
            user = ValidUserFactory(customer_id=OWNER_ID)
            await create_budget_line_service(object(), user, payload)

        # sqlite can't prove the savepoint rollback, so assert the flag instead.
        assert mock_category.call_args.kwargs["commit"] is False
