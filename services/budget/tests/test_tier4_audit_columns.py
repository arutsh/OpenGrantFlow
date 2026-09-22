"""audit-mixin-rollout-tier4 group 2: created_by/updated_by for DonorTemplateModel.
Real-JWT route test — overriding get_validated_user would skip the contextvar."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.mapping_routes import get_db as mapping_get_db
from app.models.mapping import DonorTemplateModel
from main import app
from tests.conftest import _token_for

pytestmark = pytest.mark.anyio


class TestDonorTemplateAuditTrail:
    async def test_created_by_populated_via_real_auth_chain(self, db):
        app.dependency_overrides[mapping_get_db] = lambda: db
        try:
            user_id = str(uuid4())
            client = TestClient(app)

            response = client.post(
                "/api/v1/donor-mapping/templates",
                headers={"Authorization": f"Bearer {_token_for(user_id)}"},
                json={"name": "Sample Donor Template"},
            )
        finally:
            del app.dependency_overrides[mapping_get_db]

        assert response.status_code == 200
        template = (
            await db.execute(
                select(DonorTemplateModel).where(
                    DonorTemplateModel.id == response.json()["id"]
                )
            )
        ).scalar_one()
        assert str(template.created_by) == user_id
        assert template.updated_by is None
