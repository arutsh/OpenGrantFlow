from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.customer_schema import Customer
from app.schemas.admin_management_schema import CompanyUpdateRequest
from app.db.session import get_db
from app.crud.customer_crud import (
    create_customer,
    get_customers,
    get_customers_by_ids,
)
from app.services.admin_management_services import (
    deactivate_company_service,
    get_company_service,
    update_company_service,
)
from shared.security.dependencies import get_validated_user
from shared.security.internal_service import get_validated_user_or_internal_service
from uuid import UUID

router = APIRouter()


@router.get("/customers/", response_model=list[Customer])
async def list_customers(
    is_ngo: bool | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    valid_user: dict = Depends(get_validated_user),
):
    return await get_customers(session=db, is_ngo=is_ngo, search=search)


@router.post("/customers/", response_model=Customer)
async def create_customer_endpoint(
    customer: Customer,
    db: AsyncSession = Depends(get_db),
    valid_user: dict = Depends(get_validated_user),
):
    db_customer = await create_customer(
        session=db,
        name=customer.name,
        is_ngo=customer.is_ngo,
        is_donor=customer.is_donor,
        country=customer.country,
        currency=customer.currency,
    )
    return db_customer


@router.get("/customers/{customer_id}", response_model=Customer)
async def get_customer_endpoint(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    valid_user: dict = Depends(get_validated_user),
):
    return await get_company_service(db, valid_user, customer_id)


@router.patch("/customers/{customer_id}", response_model=Customer)
async def update_customer_endpoint(
    customer_id: UUID,
    req: CompanyUpdateRequest,
    db: AsyncSession = Depends(get_db),
    valid_user: dict = Depends(get_validated_user),
):
    return await update_company_service(
        db, valid_user, customer_id, req.model_dump(exclude_unset=True)
    )


@router.post("/customers/{customer_id}/deactivate", response_model=Customer)
async def deactivate_customer_endpoint(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    valid_user: dict = Depends(get_validated_user),
):
    return await deactivate_company_service(db, valid_user, customer_id)


@router.post("/customers/by_ids/", response_model=list[Customer])
async def get_customers_by_ids_endpoint(
    customer_ids: list[UUID],
    db: AsyncSession = Depends(get_db),
    valid_user: dict | None = Depends(get_validated_user_or_internal_service),
):
    # Any authenticated user or service credential — same posture as
    # GET /customers/, which is not tenant-scoped (see design.md non-goals).
    if not customer_ids:
        return []
    return await get_customers_by_ids(session=db, customer_ids=customer_ids)
