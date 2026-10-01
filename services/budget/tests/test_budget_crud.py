import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.crud.budget_crud import create_budget, delete_budget, update_budget
from app.crud.budget_category_crud import create_budget_category
from app.crud.budget_line_crud import create_budget_line, delete_budget_line
from app.models.budget import BudgetModel
from shared.security.current_user_context import reset_current_user_id, set_current_user_id
from tests.factories.user import ValidUserFactory


@pytest.mark.anyio
class TestCreateBudget:
    async def test_omitted_fields_use_model_defaults(self, db):
        user = ValidUserFactory()

        budget = await create_budget(
            session=db, user_id=user["user_id"], name="No extras", owner_id=user["customer_id"]
        )

        assert budget.local_currency == "GBP"
        assert budget.duration_months == 0

    async def test_provided_fields_are_persisted(self, db):
        user = ValidUserFactory()

        budget = await create_budget(
            session=db,
            user_id=user["user_id"],
            name="With extras",
            owner_id=user["customer_id"],
            local_currency="EUR",
            actual_currency="NOK",
            duration_months=12,
            donor_total_amount=5000.0,
            estimated_exchange_rate=1.1,
        )

        assert budget.local_currency == "EUR"
        assert budget.actual_currency == "NOK"
        assert budget.duration_months == 12
        assert budget.donor_total_amount == 5000.0
        assert budget.estimated_exchange_rate == 1.1


@pytest.mark.anyio
class TestUpdateBudgetAuditTrail:
    async def test_updated_by_reflects_the_editing_user_not_the_creator(self, db):
        """update_budget never touches updated_by itself — only the listener should."""
        creator = ValidUserFactory()
        editor = ValidUserFactory()
        creator_id = uuid.UUID(creator["user_id"])
        editor_id = uuid.UUID(editor["user_id"])

        token = set_current_user_id(creator_id)
        try:
            budget = await create_budget(
                session=db, user_id=creator_id, name="Original", owner_id=creator["customer_id"]
            )
        finally:
            reset_current_user_id(token)

        assert budget.updated_by == creator_id

        token = set_current_user_id(editor_id)
        try:
            updated = await update_budget(session=db, budget_id=budget.id, name="Edited")
        finally:
            reset_current_user_id(token)

        assert updated.updated_by == editor_id


async def _budget_with_orphaned_category(db) -> BudgetModel:
    """A budget with a line added then removed, leaving its
    auto-created category behind (see #295's failure mode)."""
    user = ValidUserFactory()
    budget = await create_budget(
        session=db, user_id=user["user_id"], name="Cascade", owner_id=user["customer_id"]
    )
    category = await create_budget_category(
        session=db, user_id=user["user_id"], budget_id=budget.id, name="Travel"
    )
    line = await create_budget_line(
        session=db,
        user_id=user["user_id"],
        budget_id=budget.id,
        category_id=category.id,
        description="Flight",
        amount=100.0,
    )
    await delete_budget_line(session=db, budget_line=line)
    return budget


@pytest.mark.anyio
class TestDeleteBudgetCascadesOrphanedCategory:
    async def test_delete_succeeds_with_categories_unloaded(self, db):
        budget = await _budget_with_orphaned_category(db)

        assert await delete_budget(session=db, budget=budget) is True

    async def test_delete_succeeds_with_categories_already_loaded(self, db):
        # Distinguishes cascade+passive_deletes from passive_deletes alone,
        # which only fixes the unloaded case.
        budget = await _budget_with_orphaned_category(db)

        result = await db.execute(
            select(BudgetModel)
            .where(BudgetModel.id == budget.id)
            .options(selectinload(BudgetModel.categories))
        )
        loaded_budget = result.scalar_one()
        assert len(list(loaded_budget.categories)) == 1

        assert await delete_budget(session=db, budget=loaded_budget) is True
