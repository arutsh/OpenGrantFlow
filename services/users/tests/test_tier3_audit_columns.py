"""audit-mixin-rollout-tier3 group 4: created_by/updated_by population for
PrivilegedAccessLog."""

import uuid
from datetime import datetime, timezone

import pytest

from app.models.privileged_access_log import PrivilegedAccessLog
from shared.security.current_user_context import reset_current_user_id, set_current_user_id


def _now():
    return datetime.now(timezone.utc)


class TestPrivilegedAccessLogAppendOnly:
    @pytest.mark.anyio
    async def test_created_by_matches_existing_actor_field(self, db):
        """actor_user_id already captures the acting user (task 1.3) — the
        automatically-populated created_by should equal it, not diverge."""
        actor_id = uuid.uuid4()
        token = set_current_user_id(actor_id)
        try:
            log = PrivilegedAccessLog(
                actor_user_id=str(actor_id),
                customer_id=str(uuid.uuid4()),
                method="PUT",
                path="/api/v1/users",
                created_at=_now(),
            )
            db.add(log)
            await db.commit()
        finally:
            reset_current_user_id(token)

        assert log.created_by == actor_id
        assert str(log.actor_user_id) == str(actor_id)

    @pytest.mark.anyio
    async def test_updated_by_stays_null_with_no_update_path(self, db):
        token = set_current_user_id(uuid.uuid4())
        try:
            log = PrivilegedAccessLog(
                actor_user_id=str(uuid.uuid4()),
                customer_id=str(uuid.uuid4()),
                method="GET",
                path="/api/v1/users",
                created_at=_now(),
            )
            db.add(log)
            await db.commit()
        finally:
            reset_current_user_id(token)

        assert log.updated_by is None
