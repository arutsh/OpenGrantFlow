from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.export_template_crud import (
    get_system_default_template,
    list_export_templates,
    list_shared_export_templates,
)
from app.models.budget import BudgetModel
from app.schemas.export_template_schema import ExportTemplateCandidate, TemplateSource
from app.services.donor_grantee_client import (
    DonorGranteeServiceError,
    check_donor_grantee_relationship,
)


async def list_candidate_templates(
    db: AsyncSession, valid_user: dict, budget: BudgetModel
) -> list[ExportTemplateCandidate]:
    """System default + caller's own + funder's shared templates, live-gated (no caching)."""
    customer_id = valid_user.get("customer_id")
    assert customer_id is not None  # guaranteed by get_viewable_budget_service upstream
    candidates: list[ExportTemplateCandidate] = []

    default = await get_system_default_template(db)
    if default:
        candidates.append(_to_candidate(default, TemplateSource.system))

    for template in await list_export_templates(db, customer_id):
        candidates.append(_to_candidate(template, TemplateSource.own))

    donor_id = budget.funding_customer_id
    if donor_id and str(donor_id) != str(customer_id):
        try:
            is_grantee = await check_donor_grantee_relationship(donor_id, budget.owner_id)
        except DonorGranteeServiceError:
            is_grantee = False
        if is_grantee:
            for template in await list_shared_export_templates(db, donor_id):
                candidates.append(_to_candidate(template, TemplateSource.donor))

    return candidates


def _to_candidate(template, source: TemplateSource) -> ExportTemplateCandidate:
    return ExportTemplateCandidate(
        id=template.id,
        name=template.name,
        visibility=template.visibility,
        version=template.version,
        source=source,
    )
