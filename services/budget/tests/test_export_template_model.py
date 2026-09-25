from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from tests.factories.export_template import ExportTemplateFactory

pytestmark = pytest.mark.anyio


async def _add_template(db, owner_customer_id, name="Annual Report"):
    template = ExportTemplateFactory.build(owner_customer_id=owner_customer_id, name=name)
    db.add(template)
    await db.commit()
    return template


class TestExportTemplateUniqueness:
    async def test_duplicate_name_within_one_organisation_is_rejected(self, db):
        owner_id = uuid4()
        await _add_template(db, owner_id)

        with pytest.raises(IntegrityError):
            await _add_template(db, owner_id)

    async def test_same_name_accepted_across_two_organisations(self, db):
        await _add_template(db, uuid4())
        await _add_template(db, uuid4())


class TestSystemDefaultConstraints:
    async def test_a_second_system_default_is_rejected(self, db):
        await _add_template(db, None, "GrandFlow Default")

        with pytest.raises(IntegrityError):
            await _add_template(db, None, "Another Default")

    async def test_system_default_with_an_owner_is_rejected(self, db):
        db.add(ExportTemplateFactory.build(owner_customer_id=uuid4(), is_system_default=True))

        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_ownerless_non_default_is_rejected(self, db):
        db.add(ExportTemplateFactory.build(owner_customer_id=None, is_system_default=False))

        with pytest.raises(IntegrityError):
            await db.commit()
