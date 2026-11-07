from contextlib import nullcontext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from app.models.budget import BudgetCategoryModel
from app.crud.budget_category_crud import (
    get_budget_category,
    get_budget_categories_by_names,
    bulk_create_budget_categories,
    update_budget_category,
    delete_budget_category,
    list_budget_categories,
)
from app.crud.budget_crud import get_budget
from app.core.exceptions import DomainError
from fastapi import status


def _assert_budget_editable(budget) -> None:
    # Local import to avoid a cycle: budget_services imports this module.
    from app.services.budget_services import assert_budget_editable

    assert_budget_editable(budget, "categories")


async def get_or_create_category_service(
    db: AsyncSession,
    valid_user: dict,
    budget_id: UUID,
    category_id: UUID | None = None,
    category_name: str | None = None,
    commit: bool = True,
) -> BudgetCategoryModel:
    """Get an existing category by id/name, or create "Miscellaneous", scoped to budget_id."""
    if category_id:
        category = await get_budget_category(db, category_id)
        if not category or category.budget_id != budget_id:
            raise DomainError(
                "Budget Category not found",
                status.HTTP_404_NOT_FOUND,
            )
        return category

    name = category_name if category_name else "Miscellaneous"
    result = await get_or_create_categories_by_names_service(
        db, valid_user, budget_id, [name], commit=commit
    )
    return result[name]


async def get_or_create_categories_by_names_service(
    db: AsyncSession,
    valid_user: dict,
    budget_id: UUID,
    category_names: list[str],
    commit: bool = True,
) -> dict[str, BudgetCategoryModel]:
    """Batched form of get_or_create_category_service for a list of names — avoids N+1 lookups."""
    unique_names = list(dict.fromkeys(category_names))
    if not unique_names:
        return {}

    existing = await get_budget_categories_by_names(db, budget_id, unique_names)
    result = {category.name: category for category in existing}

    missing_names = [name for name in unique_names if name not in result]
    if missing_names:
        names_and_codes: list[tuple[str, str | None]] = [
            (name, "_".join(name.split()).upper()) for name in missing_names
        ]
        # commit=False: SAVEPOINT the insert so a race can't roll back the caller's flushed budget.
        savepoint = db.begin_nested() if not commit else nullcontext()
        try:
            async with savepoint:
                created = await bulk_create_budget_categories(
                    db, valid_user["user_id"], budget_id, names_and_codes, commit=commit
                )
        except IntegrityError:
            # A concurrent request created the same name for this budget; re-read it.
            if commit:
                await db.rollback()
            created = await get_budget_categories_by_names(db, budget_id, unique_names)
            if len(created) != len(unique_names):
                raise DomainError(
                    "Failed to create budget categories",
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            result = {category.name: category for category in created}
        else:
            result.update({name: category for (name, _), category in zip(names_and_codes, created)})

    return result


async def _get_owned_budget_or_none(db: AsyncSession, valid_user: dict, budget_id: UUID):
    customer_id = valid_user.get("customer_id")
    return await get_budget(db, budget_id, customer_id) if customer_id else None


async def list_budget_categories_service(
    db: AsyncSession, valid_user: dict, budget_id: UUID
) -> list[BudgetCategoryModel]:
    budget = await _get_owned_budget_or_none(db, valid_user, budget_id)
    if not budget:
        raise DomainError("Budget Not found", status.HTTP_400_BAD_REQUEST)
    return await list_budget_categories(db, budget_id=budget_id)


async def _get_owned_category_or_404(db: AsyncSession, valid_user: dict, category_id: UUID):
    customer_id = valid_user.get("customer_id")
    category = await get_budget_category(db, category_id, customer_id) if customer_id else None
    if not category:
        raise DomainError("Budget Category not found", status.HTTP_404_NOT_FOUND)

    return category, category.budget


async def update_budget_category_service(
    db: AsyncSession, valid_user: dict, category_id: UUID, update_data: dict
) -> BudgetCategoryModel:
    category, budget = await _get_owned_category_or_404(db, valid_user, category_id)
    _assert_budget_editable(budget)

    if not update_data:
        return category

    name = update_data.get("name", category.name)
    code = update_data.get("code", category.code)

    try:
        return await update_budget_category(db, category, valid_user["user_id"], name, code)
    except IntegrityError:
        await db.rollback()
        raise DomainError(
            "A category with this name already exists in this budget",
            status.HTTP_400_BAD_REQUEST,
        )


async def delete_budget_category_service(
    db: AsyncSession, valid_user: dict, category_id: UUID
) -> bool:
    category, budget = await _get_owned_category_or_404(db, valid_user, category_id)
    _assert_budget_editable(budget)

    return await delete_budget_category(db, category)
