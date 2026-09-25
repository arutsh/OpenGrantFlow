from unittest.mock import patch
from uuid import uuid4

import pytest

from app.schemas.export_template_schema import TemplateSource, TemplateVisibility
from app.services.export_template_service import list_candidate_templates
from tests.factories.budget import BudgetFactory
from tests.factories.export_template import ExportTemplateFactory

pytestmark = pytest.mark.anyio


async def _make_budget(db, owner_id, funding_customer_id=None):
    budget = BudgetFactory.build(owner_id=owner_id, funding_customer_id=funding_customer_id)
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return budget


async def _add_template(db, owner_customer_id, name, visibility=TemplateVisibility.private):
    template = ExportTemplateFactory.build(
        owner_customer_id=owner_customer_id, name=name, visibility=visibility
    )
    db.add(template)
    await db.commit()
    return template


class TestListCandidateTemplates:
    async def test_grantee_sees_funders_shared_template(self, db):
        grantee_id, donor_id = uuid4(), uuid4()
        budget = await _make_budget(db, owner_id=grantee_id, funding_customer_id=donor_id)
        shared = await _add_template(
            db, donor_id, "Donor Report", TemplateVisibility.shared_with_grantees
        )

        with patch(
            "app.services.export_template_service.check_donor_grantee_relationship",
            return_value=True,
        ):
            candidates = await list_candidate_templates(
                db, {"customer_id": grantee_id}, budget
            )

        donor_candidates = [c for c in candidates if c.source == TemplateSource.donor]
        assert [c.id for c in donor_candidates] == [shared.id]

    async def test_donors_private_template_is_not_offered(self, db):
        grantee_id, donor_id = uuid4(), uuid4()
        budget = await _make_budget(db, owner_id=grantee_id, funding_customer_id=donor_id)
        await _add_template(db, donor_id, "Internal Only", TemplateVisibility.private)

        with patch(
            "app.services.export_template_service.check_donor_grantee_relationship",
            return_value=True,
        ):
            candidates = await list_candidate_templates(
                db, {"customer_id": grantee_id}, budget
            )

        assert [c for c in candidates if c.source == TemplateSource.donor] == []

    async def test_unrelated_organisations_shared_template_is_not_offered(self, db):
        grantee_id, donor_id, unrelated_id = uuid4(), uuid4(), uuid4()
        budget = await _make_budget(db, owner_id=grantee_id, funding_customer_id=donor_id)
        await _add_template(
            db, unrelated_id, "Unrelated Org Template", TemplateVisibility.shared_with_grantees
        )

        with patch(
            "app.services.export_template_service.check_donor_grantee_relationship",
            return_value=True,
        ):
            candidates = await list_candidate_templates(
                db, {"customer_id": grantee_id}, budget
            )

        assert [c for c in candidates if c.source == TemplateSource.donor] == []

    async def test_revoked_relationship_drops_template_on_next_call_with_no_cache(self, db):
        grantee_id, donor_id = uuid4(), uuid4()
        budget = await _make_budget(db, owner_id=grantee_id, funding_customer_id=donor_id)
        await _add_template(
            db, donor_id, "Donor Report", TemplateVisibility.shared_with_grantees
        )

        with patch(
            "app.services.export_template_service.check_donor_grantee_relationship",
            return_value=True,
        ):
            first_call = await list_candidate_templates(db, {"customer_id": grantee_id}, budget)
        with patch(
            "app.services.export_template_service.check_donor_grantee_relationship",
            return_value=False,
        ):
            second_call = await list_candidate_templates(db, {"customer_id": grantee_id}, budget)

        assert any(c.source == TemplateSource.donor for c in first_call)
        assert not any(c.source == TemplateSource.donor for c in second_call)

    async def test_system_default_and_own_templates_always_included(self, db):
        grantee_id = uuid4()
        budget = await _make_budget(db, owner_id=grantee_id)
        await _add_template(db, None, "GrandFlow Default")
        await _add_template(db, grantee_id, "My Template")

        candidates = await list_candidate_templates(db, {"customer_id": grantee_id}, budget)

        sources = {c.source for c in candidates}
        assert TemplateSource.system in sources
        assert TemplateSource.own in sources
