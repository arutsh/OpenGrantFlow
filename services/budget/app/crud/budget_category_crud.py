from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager
from app.models.budget import BudgetCategoryModel, BudgetModel
from uuid import UUID


async def create_budget_category(
    session: AsyncSession,
    user_id: UUID,
    budget_id: UUID,
    name: str,
    code: str | None = None,
) -> BudgetCategoryModel:
    budget_category = BudgetCategoryModel(
        name=name,
        code=code,
        budget_id=budget_id,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(budget_category)
    await session.commit()
    return budget_category


async def get_budget_category_by_name(
    session: AsyncSession, budget_id: UUID, name: str
) -> BudgetCategoryModel | None:
    result = await session.execute(
        select(BudgetCategoryModel).where(
            BudgetCategoryModel.budget_id == budget_id, BudgetCategoryModel.name == name
        )
    )
    return result.scalar_one_or_none()


async def get_budget_categories_by_names(
    session: AsyncSession, budget_id: UUID, names: list[str]
) -> list[BudgetCategoryModel]:
    result = await session.execute(
        select(BudgetCategoryModel).where(
            BudgetCategoryModel.budget_id == budget_id,
            BudgetCategoryModel.name.in_(names),
        )
    )
    return list(result.scalars().all())


async def bulk_create_budget_categories(
    session: AsyncSession,
    user_id: UUID,
    budget_id: UUID,
    names_and_codes: list[tuple[str, str | None]],
    commit: bool = True,
) -> list[BudgetCategoryModel]:
    categories = [
        BudgetCategoryModel(
            name=name,
            code=code,
            budget_id=budget_id,
            created_by=user_id,
            updated_by=user_id,
        )
        for name, code in names_and_codes
    ]
    session.add_all(categories)
    if commit:
        await session.commit()
    else:
        await session.flush()
    return categories


async def get_budget_category(
    session: AsyncSession, category_id: UUID, customer_id: UUID | None = None
) -> BudgetCategoryModel | None:
    query = select(BudgetCategoryModel).where(BudgetCategoryModel.id == category_id)
    if customer_id:
        query = (
            query.join(BudgetCategoryModel.budget)
            .where(BudgetModel.owner_id == customer_id)
            .options(contains_eager(BudgetCategoryModel.budget))
        )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_budget_categories(
    session: AsyncSession, budget_id: UUID | None = None, limit: int | None = 100
):
    query = select(BudgetCategoryModel).order_by(
        BudgetCategoryModel.created_at, BudgetCategoryModel.id
    )
    if budget_id:
        query = query.where(BudgetCategoryModel.budget_id == budget_id)
    query = query.limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_budget_category(
    session: AsyncSession,
    category: BudgetCategoryModel,
    user_id: UUID,
    name: str,
    code: str | None = None,
) -> BudgetCategoryModel:
    category.name = name
    category.code = code
    category.updated_by = user_id
    await session.commit()
    return category


async def delete_budget_category(session: AsyncSession, category: BudgetCategoryModel) -> bool:
    await session.delete(category)
    await session.commit()
    return True
