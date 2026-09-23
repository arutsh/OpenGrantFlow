# /services/budget/app/api/budget_routes.py
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4, UUID  # noqa: F401

from app.db.session import get_db
from app.schemas.budget_schema import (
    BudgetCreate,
    BudgetUpdate,
    BudgetWithLines,
    FundedBudgetsSummary,
    GranteeSummary,
    FundedBudgetListItem,
    GranteeDashboardSummary,
)
from app.schemas.budget_line_schema import BudgetLine
from app.schemas.excel_import_schema import ExcelPrepareImportResult
from app.schemas.mapping_schema import DonorTemplate, DonorTemplateCreate
from app.schemas.with_lines_schema import CreateBudgetWithLinesRequest
from app.services.budget_line_services import get_viewable_budget_lines_service
from app.services.budget_services import (
    create_budget_service,
    create_budget_with_lines_service,
    get_viewable_budget_service,
    save_budget_as_template_service,
    update_budget_service,
    restore_budget_service,
    list_budget_service,
    delete_budget_service,
    get_funded_budgets_summary_service,
    get_funded_grantees_service,
    get_funded_budgets_service,
    get_grantee_dashboard_summary_service,
)
from app.services.customer_client import require_donor
from app.services.excel_export_service import export_budget_workbook_service
from app.services.excel_import_service import prepare_excel_import_service
from app.crud.budget_crud import get_budgets_by_creator
from shared.observability import set_span_attributes
from shared.security.dependencies import get_validated_user
from shared.storage.storage_service import safe_content_disposition

router = APIRouter(prefix="/budgets", tags=["Public Budgets"])
private_router = APIRouter(prefix="/budgets", tags=["Private Budgets"])


@router.post("/")
async def create_budget_endpoint(
    budget: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    result = await create_budget_service(budget, valid_user, db, include_user_datails=True)
    set_span_attributes(budget_id=result["id"])
    return result


@router.get("/funded/summary", response_model=FundedBudgetsSummary)
async def get_funded_budgets_summary_endpoint(
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    require_donor(valid_user)
    return await get_funded_budgets_summary_service(valid_user["customer_id"], db)


@router.get("/funded/grantees", response_model=list[GranteeSummary])
async def get_funded_grantees_endpoint(
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    require_donor(valid_user)
    return await get_funded_grantees_service(valid_user["customer_id"], valid_user, db)


@router.get("/funded/", response_model=list[FundedBudgetListItem])
async def get_funded_budgets_endpoint(
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    require_donor(valid_user)
    return await get_funded_budgets_service(valid_user["customer_id"], valid_user, db)


@router.get("/dashboard/summary", response_model=GranteeDashboardSummary)
async def get_dashboard_summary_endpoint(
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    return await get_grantee_dashboard_summary_service(valid_user.get("customer_id"), db)


@router.get("/{budget_id}", response_model=BudgetWithLines)
async def get_budget_endpoint(
    budget_id: UUID,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    set_span_attributes(budget_id=budget_id)
    budget = await get_viewable_budget_service(budget_id, valid_user, db, include_user_details=True)
    if budget:
        budget_lines = await get_viewable_budget_lines_service(
            db=db, valid_user=valid_user, budget_id=budget_id
        )
        budget["lines"] = [BudgetLine.model_validate(line) for line in budget_lines]
    return budget


@router.get("/{budget_id}/export.xlsx")
async def export_budget_workbook_endpoint(
    budget_id: UUID,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    set_span_attributes(budget_id=budget_id)
    budget, workbook_bytes = await export_budget_workbook_service(db, valid_user, budget_id)
    return StreamingResponse(
        io.BytesIO(workbook_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": safe_content_disposition(f"{budget.name}.xlsx")},
    )


@router.patch("/{budget_id}", response_model=BudgetUpdate)
async def update_budget_endpoint(
    budget_id: UUID,
    budget: BudgetUpdate,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    set_span_attributes(budget_id=budget_id)
    updated_budget = await update_budget_service(
        budget_id=budget_id, budget=budget, valid_user=valid_user, db=db
    )
    if not updated_budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return updated_budget


@router.post("/{budget_id}/save-as-template", response_model=DonorTemplate)
async def save_budget_as_template_endpoint(
    budget_id: UUID,
    payload: DonorTemplateCreate,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    set_span_attributes(budget_id=budget_id)
    template = await save_budget_as_template_service(budget_id, payload.name, valid_user, db)
    set_span_attributes(donor_template_id=template.id)
    return template


@router.post("/{budget_id}/restore", response_model=BudgetUpdate)
async def restore_budget_endpoint(
    budget_id: UUID,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    set_span_attributes(budget_id=budget_id)
    updated_budget = await restore_budget_service(budget_id=budget_id, valid_user=valid_user, db=db)
    if not updated_budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return updated_budget


@router.get("/")
async def get_all_budgets_endpoint(
    db: AsyncSession = Depends(get_db), valid_user=Depends(get_validated_user)
):

    return await list_budget_service(db=db, valid_user=valid_user, include_user_details=True)


@router.post("/with-lines")
async def create_budget_with_lines_endpoint(
    request: CreateBudgetWithLinesRequest,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    return await create_budget_with_lines_service(request, valid_user, db)


@router.post("/excel/prepare-import", response_model=ExcelPrepareImportResult)
async def prepare_excel_import_endpoint(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    return await prepare_excel_import_service(db, valid_user, file)


@router.delete("/{budget_id}")
async def delete_budget_endpoint(
    budget_id: UUID, db: AsyncSession = Depends(get_db), valid_user=Depends(get_validated_user)
):
    set_span_attributes(budget_id=budget_id)
    return {
        "success": await delete_budget_service(budget_id=budget_id, valid_user=valid_user, db=db)
    }


@router.get("/by-creator/{user_id}")
async def get_budgets_by_creator_endpoint(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    valid_user=Depends(get_validated_user),
):
    # Unlike /customers/by_ids/, no gateway exclusion protects this path — this is the only guard.
    if str(valid_user["user_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this user's budgets")
    budgets = await get_budgets_by_creator(db, user_id)
    return [
        {"id": str(b.id), "name": b.name, "type": "budget", "created_at": b.created_at}
        for b in budgets
    ]
