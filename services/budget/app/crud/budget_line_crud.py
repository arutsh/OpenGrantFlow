from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.budget import BudgetLineModel, BudgetModel
from uuid import UUID

from app.schemas import BudgetLineCreate


async def create_budget_line(
    session: AsyncSession,
    user_id: UUID,
    budget_id: UUID,
    category_id: UUID | None,
    description: str,
    amount: float,
    extra_fields: dict | None = None,
    commit: bool = True,
) -> BudgetLineModel:
    """
    Create a budget line after validating NGO and Donor IDs.
    """
    # Validate external customer IDs

    budget_line = BudgetLineModel(
        budget_id=budget_id,
        category_id=category_id,
        description=description,
        amount=amount,
        extra_fields=extra_fields,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(budget_line)
    if commit:
        await session.commit()
    else:
        await session.flush()
    # The response schema always nests `category`; refresh it explicitly rather than
    # relying on it happening to already sit in the identity map.
    await session.refresh(budget_line, attribute_names=["category"])
    return budget_line


async def bulk_create_budget_lines(
    session: AsyncSession,
    user_id: UUID,
    budget_id: UUID,
    lines: list[dict],
    commit: bool = True,
) -> list[BudgetLineModel]:
    """Create multiple budget lines with a single insert + commit."""
    budget_lines = [
        BudgetLineModel(
            budget_id=budget_id,
            category_id=line["category_id"],
            description=line["description"],
            amount=line["amount"],
            extra_fields=line.get("extra_fields"),
            created_by=user_id,
            updated_by=user_id,
        )
        for line in lines
    ]
    session.add_all(budget_lines)
    if commit:
        await session.commit()
    else:
        await session.flush()

    line_ids = [budget_line.id for budget_line in budget_lines]
    result = await session.execute(
        select(BudgetLineModel)
        .where(BudgetLineModel.id.in_(line_ids))
        .options(selectinload(BudgetLineModel.category))
    )
    return list(result.scalars().all())


async def get_budget_line(session: AsyncSession, budget_line_id: UUID) -> BudgetLineModel | None:
    # The BudgetLine response schema always nests `category`, so every caller needs it.
    result = await session.execute(
        select(BudgetLineModel)
        .where(BudgetLineModel.id == budget_line_id)
        .options(selectinload(BudgetLineModel.category))
    )
    return result.scalar_one_or_none()


async def list_budget_lines(
    session: AsyncSession,
    budget_id: UUID | None = None,
    customer_id: UUID | None = None,
    limit: int | None = 100,
):
    query = (
        select(BudgetLineModel)
        .options(selectinload(BudgetLineModel.category))
        .order_by(BudgetLineModel.created_at, BudgetLineModel.id)
    )
    if budget_id:
        query = query.where(BudgetLineModel.budget_id == budget_id)
    if customer_id:
        query = query.join(BudgetLineModel.budget).where(BudgetModel.owner_id == customer_id)
    query = query.limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_budget_lines_by_category(
    session: AsyncSession, category_id: UUID | None = None, limit: int = 100
):
    query = select(BudgetLineModel)
    if category_id:
        query = query.where(BudgetLineModel.category_id == category_id)
    result = await session.execute(query.limit(limit))
    return list(result.scalars().all())


async def update_budget_line(
    session: AsyncSession, existing_line, new_budget_line: BudgetLineCreate
) -> BudgetLineModel | None:
    if new_budget_line.description is not None:
        existing_line.description = new_budget_line.description
    if new_budget_line.amount is not None:
        existing_line.amount = new_budget_line.amount
    if new_budget_line.extra_fields is not None:
        existing_line.extra_fields = {
            **(existing_line.extra_fields or {}),
            **new_budget_line.extra_fields,
        }
    await session.commit()
    return existing_line


async def delete_budget_line(
    session: AsyncSession, budget_line: BudgetLineModel, commit: bool = True
) -> bool:
    await session.delete(budget_line)
    if commit:
        await session.commit()
    else:
        await session.flush()
    return True
