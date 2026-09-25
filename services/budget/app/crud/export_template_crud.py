from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models.export_template import ExportTemplateModel
from app.schemas.export_template_schema import ExportTemplateOptions, TemplateVisibility


async def create_export_template(
    session: AsyncSession,
    customer_id: UUID,
    name: str,
    visibility: TemplateVisibility,
    options: ExportTemplateOptions,
) -> ExportTemplateModel:
    template = ExportTemplateModel(
        owner_customer_id=customer_id,
        name=name,
        visibility=visibility,
        options=options.model_dump(mode="json"),
    )
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def list_export_templates(
    session: AsyncSession, customer_id: UUID
) -> list[ExportTemplateModel]:
    result = await session.execute(
        select(ExportTemplateModel).where(ExportTemplateModel.owner_customer_id == customer_id)
    )
    return list(result.scalars().all())


async def get_export_template(
    session: AsyncSession, customer_id: UUID, template_id: UUID
) -> ExportTemplateModel | None:
    """Scoped to the requesting organisation — an unscoped read is not expressible."""
    result = await session.execute(
        select(ExportTemplateModel).where(
            ExportTemplateModel.id == template_id,
            ExportTemplateModel.owner_customer_id == customer_id,
        )
    )
    return result.scalar_one_or_none()


async def get_system_default_template(session: AsyncSession) -> ExportTemplateModel | None:
    result = await session.execute(
        select(ExportTemplateModel).where(ExportTemplateModel.is_system_default.is_(True))
    )
    return result.scalar_one_or_none()


async def list_shared_export_templates(
    session: AsyncSession, owner_customer_id: UUID
) -> list[ExportTemplateModel]:
    """A donor's templates marked shared with grantees — candidate-resolution reads only."""
    result = await session.execute(
        select(ExportTemplateModel).where(
            ExportTemplateModel.owner_customer_id == owner_customer_id,
            ExportTemplateModel.visibility == TemplateVisibility.shared_with_grantees,
        )
    )
    return list(result.scalars().all())


async def _is_system_default(session: AsyncSession, template_id: UUID) -> bool:
    result = await session.execute(
        select(ExportTemplateModel.id).where(
            ExportTemplateModel.id == template_id,
            ExportTemplateModel.is_system_default.is_(True),
        )
    )
    return result.scalar_one_or_none() is not None


async def update_export_template(
    session: AsyncSession,
    customer_id: UUID,
    template_id: UUID,
    name: str | None = None,
    visibility: TemplateVisibility | None = None,
    options: ExportTemplateOptions | None = None,
) -> ExportTemplateModel | None:
    if await _is_system_default(session, template_id):
        raise DomainError("The system default template cannot be edited", status.HTTP_403_FORBIDDEN)
    template = await get_export_template(session, customer_id, template_id)
    if not template:
        return None
    if name is not None:
        template.name = name
    if visibility is not None:
        template.visibility = visibility
    if options is not None:
        template.options = options.model_dump(mode="json")
    template.version += 1
    await session.commit()
    await session.refresh(template)
    return template


async def delete_export_template(
    session: AsyncSession, customer_id: UUID, template_id: UUID
) -> bool:
    if await _is_system_default(session, template_id):
        raise DomainError(
            "The system default template cannot be deleted", status.HTTP_403_FORBIDDEN
        )
    template = await get_export_template(session, customer_id, template_id)
    if not template:
        return False
    await session.delete(template)
    await session.commit()
    return True
