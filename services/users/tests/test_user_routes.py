"""Route tests for the self-service PATCH /api/users/{user_id}/ (founder onboarding and
the account-tenant-authz hardening: self-only, no membership/role/status changes)."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.customer import CustomerModel
from app.models.user import UserModel
from tests.factories.user import CustomerFactory, UserModelFactory


@pytest.fixture
async def db():
    """Only the users/customers tables this endpoint touches."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all, tables=[UserModel.__table__, CustomerModel.__table__]
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _persist(db, obj):
    db.add(obj)
    await db.commit()
    return obj


async def _make_pending_user(db, **overrides):
    # UserModelFactory already defaults to role=user, status=pending.
    return await _persist(db, UserModelFactory.build(**overrides))


async def _make_company_admin(db, name="Company A"):
    customer = await _persist(db, CustomerFactory.build(name=name))
    admin = await _persist(
        db,
        UserModelFactory.build(customer_id=customer.id, role="admin", status="active"),
    )
    return customer, admin


async def _reload(db, user):
    await db.refresh(user)
    return user


async def _customer_count(db):
    return (await db.execute(select(func.count()).select_from(CustomerModel))).scalar_one()


@pytest.mark.anyio
class TestUpdateUserOnboarding:
    async def test_new_customer_name_promotes_founder_to_admin(self, make_client, db):
        pending_user = await _make_pending_user(db)
        client = make_client(db=db, user_id=pending_user.id, role="user")

        response = client.patch(
            f"/api/users/{pending_user.id}/",
            json={"new_customer_name": "Acme NGO"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["role"] == "admin"
        assert body["status"] == "active"
        assert body["customer_id"] is not None

        result = await db.execute(
            select(CustomerModel).where(CustomerModel.id == body["customer_id"])
        )
        customer = result.scalar_one_or_none()
        assert customer is not None
        assert customer.name == "Acme NGO"
        assert customer.is_ngo is True

    async def test_new_customer_name_ignored_once_user_has_a_company(self, make_client, db):
        customer, admin = await _make_company_admin(db)
        client = make_client(db=db, user_id=admin.id, role="admin", customer_id=customer.id)
        before = await _customer_count(db)

        response = client.patch(f"/api/users/{admin.id}/", json={"new_customer_name": "Other"})

        assert response.status_code == 200
        assert response.json()["customer_id"] == str(customer.id)
        assert await _customer_count(db) == before

    async def test_invited_pending_user_cannot_found_a_new_company(self, make_client, db):
        customer = await _persist(db, CustomerFactory.build(name="Inviter Org"))
        invited = await _make_pending_user(db, customer_id=customer.id)
        client = make_client(db=db, user_id=invited.id, role="user", customer_id=customer.id)

        response = client.patch(f"/api/users/{invited.id}/", json={"new_customer_name": "Mine"})

        assert response.status_code == 200
        invited = await _reload(db, invited)
        assert str(invited.customer_id) == str(customer.id)
        assert invited.role == "user"


@pytest.mark.anyio
class TestSelfUpdatePreservesMembership:
    async def test_first_name_only_keeps_customer_and_role(self, make_client, db):
        """Regression: an omitted customer_id used to be written back as None."""
        customer, admin = await _make_company_admin(db)
        client = make_client(db=db, user_id=admin.id, role="admin", customer_id=customer.id)

        response = client.patch(f"/api/users/{admin.id}/", json={"first_name": "Renamed"})

        assert response.status_code == 200
        admin = await _reload(db, admin)
        assert admin.first_name == "Renamed"
        assert str(admin.customer_id) == str(customer.id)
        assert admin.role == "admin"
        assert response.json()["customer"]["id"] == str(customer.id)


@pytest.mark.anyio
class TestSelfUpdateRejectsPrivilegedFields:
    @pytest.mark.parametrize(
        "field, value",
        [
            ("customer_id", "__other_customer__"),
            ("role", "superuser"),
            ("status", "active"),
            ("email", "new@example.com"),
        ],
    )
    async def test_privileged_field_is_422(self, make_client, db, field, value):
        customer, admin = await _make_company_admin(db)
        other = await _persist(db, CustomerFactory.build(name="Company B"))
        if value == "__other_customer__":
            value = str(other.id)
        client = make_client(db=db, user_id=admin.id, role="admin", customer_id=customer.id)

        response = client.patch(f"/api/users/{admin.id}/", json={field: value})

        assert response.status_code == 422
        admin = await _reload(db, admin)
        assert str(admin.customer_id) == str(customer.id)
        assert admin.role == "admin"
        assert admin.status == "active"

    async def test_admin_cannot_move_into_another_company(self, make_client, db):
        customer_a, admin = await _make_company_admin(db, "Company A")
        customer_b = await _persist(db, CustomerFactory.build(name="Company B"))
        client = make_client(db=db, user_id=admin.id, role="admin", customer_id=customer_a.id)

        response = client.patch(
            f"/api/users/{admin.id}/",
            json={"first_name": "Mallory", "customer_id": str(customer_b.id)},
        )

        assert response.status_code == 422
        admin = await _reload(db, admin)
        assert str(admin.customer_id) == str(customer_a.id)
        assert admin.role == "admin"
        assert admin.first_name != "Mallory"

    async def test_pending_user_cannot_join_existing_company(self, make_client, db):
        customer_b = await _persist(db, CustomerFactory.build(name="Company B"))
        pending_user = await _make_pending_user(db)
        client = make_client(db=db, user_id=pending_user.id, role="user")

        response = client.patch(
            f"/api/users/{pending_user.id}/", json={"customer_id": str(customer_b.id)}
        )

        assert response.status_code == 422
        pending_user = await _reload(db, pending_user)
        assert pending_user.customer_id is None
        assert pending_user.status == "pending"

    async def test_smuggled_role_on_founder_onboarding_is_422(self, make_client, db):
        pending_user = await _make_pending_user(db)
        client = make_client(db=db, user_id=pending_user.id, role="user")
        before = await _customer_count(db)

        response = client.patch(
            f"/api/users/{pending_user.id}/",
            json={"new_customer_name": "Sneaky Org", "role": "superuser"},
        )

        assert response.status_code == 422
        assert await _customer_count(db) == before


@pytest.mark.anyio
class TestSelfUpdateIsSelfOnly:
    @pytest.mark.parametrize(
        "claims",
        [
            {"role": "user"},
            {"role": "admin"},
            {"role": "superuser"},
            {"role": "admin", "is_impersonating": True},
        ],
    )
    async def test_editing_another_user_is_403(self, make_client, db, claims):
        customer, target = await _make_company_admin(db)
        caller_id = str(uuid4())
        client = make_client(db=db, user_id=caller_id, customer_id=customer.id, **claims)

        response = client.patch(f"/api/users/{target.id}/", json={"first_name": "Hijacked"})

        assert response.status_code == 403
        target = await _reload(db, target)
        assert target.first_name != "Hijacked"

    async def test_superuser_in_db_gets_no_cross_user_edit(self, make_client, db):
        """The actor's stored superuser role must not widen an impersonation token."""
        superuser = await _persist(
            db, UserModelFactory.build(role="superuser", status="active")
        )
        customer, target = await _make_company_admin(db)
        client = make_client(
            db=db,
            user_id=superuser.id,
            role="admin",
            customer_id=customer.id,
            is_impersonating=True,
        )

        response = client.patch(f"/api/users/{target.id}/", json={"first_name": "Hijacked"})

        assert response.status_code == 403
