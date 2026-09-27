from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import CustomerModel


async def get_customer(session: AsyncSession, customer_id: UUID):
    result = await session.execute(select(CustomerModel).where(CustomerModel.id == customer_id))
    return result.scalar_one_or_none()


async def lock_customer_for_update(session: AsyncSession, customer_id: UUID) -> None:
    """Take a row lock on the customer for the rest of this transaction, so
    concurrent admin-management mutations (remove/demote) for the same
    company serialize instead of racing past each other's last-admin check."""
    await session.execute(
        select(CustomerModel).where(CustomerModel.id == customer_id).with_for_update()
    )


async def get_customers(
    session: AsyncSession,
    limit: int = 100,
    is_ngo: bool | None = None,
    search: str | None = None,
):
    stmt = select(CustomerModel)
    if is_ngo is not None:
        stmt = stmt.where(CustomerModel.is_ngo == is_ngo)
    if search:
        # Escape ilike wildcards (% and _) in user input so they're matched
        # literally rather than acting as pattern metacharacters.
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(CustomerModel.name.ilike(f"%{escaped}%", escape="\\"))
    result = await session.execute(stmt.limit(limit))
    return list(result.scalars().all())


async def create_customer(
    session: AsyncSession,
    name: str,
    is_ngo: bool = True,
    is_donor: bool = False,
    country: str = "GB",
    currency: str = "GBP",
) -> CustomerModel:
    customer = CustomerModel(
        name=name,
        is_ngo=is_ngo,
        is_donor=is_donor,
        country=country,
        currency=currency,
    )
    session.add(customer)
    await session.commit()
    return customer


async def get_customers_by_ids(session: AsyncSession, customer_ids: list[UUID]):
    if not customer_ids:
        return []
    result = await session.execute(select(CustomerModel).where(CustomerModel.id.in_(customer_ids)))
    return list(result.scalars().all())


async def update_customer(
    session: AsyncSession, customer: CustomerModel, updates: dict
) -> CustomerModel:
    for key, value in updates.items():
        setattr(customer, key, value)
    await session.commit()
    return customer


async def deactivate_customer(session: AsyncSession, customer: CustomerModel) -> CustomerModel:
    customer.deactivated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.commit()
    return customer
