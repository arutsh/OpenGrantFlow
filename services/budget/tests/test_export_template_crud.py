from uuid import uuid4

import pytest

from app.core.exceptions import DomainError
from app.crud.export_template_crud import (
    create_export_template,
    delete_export_template,
    get_export_template,
    update_export_template,
)
from app.schemas.export_template_schema import ExportTemplateOptions, TemplateVisibility
from tests.factories.export_template import ExportTemplateFactory

pytestmark = pytest.mark.anyio


class TestScoping:
    async def test_org_a_cannot_read_org_bs_private_template(self, db):
        org_a, org_b = uuid4(), uuid4()
        template = ExportTemplateFactory.build(owner_customer_id=org_b, name="Board Report")
        db.add(template)
        await db.commit()

        assert await get_export_template(db, org_a, template.id) is None
        assert await get_export_template(db, org_b, template.id) is not None


class TestVersionBump:
    async def test_update_increments_version(self, db):
        owner_id = uuid4()
        template = await create_export_template(
            db, owner_id, "Draft", TemplateVisibility.private, ExportTemplateOptions()
        )
        assert template.version == 1

        updated = await update_export_template(db, owner_id, template.id, name="Final")

        assert updated.version == 2
        assert updated.name == "Final"


class TestSystemDefaultGuard:
    async def test_editing_the_system_default_is_rejected(self, db):
        default = ExportTemplateFactory.build(owner_customer_id=None, name="GrandFlow Default")
        db.add(default)
        await db.commit()

        with pytest.raises(DomainError):
            await update_export_template(db, uuid4(), default.id, name="Hacked")

    async def test_deleting_the_system_default_is_rejected(self, db):
        default = ExportTemplateFactory.build(owner_customer_id=None, name="GrandFlow Default")
        db.add(default)
        await db.commit()

        with pytest.raises(DomainError):
            await delete_export_template(db, uuid4(), default.id)
