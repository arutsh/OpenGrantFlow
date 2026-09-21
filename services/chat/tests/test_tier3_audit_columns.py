"""audit-mixin-rollout-tier3 group 2: created_by/updated_by population for
Conversation, Message, PrivilegedAccessLog."""

import uuid
from datetime import datetime, timezone

from app.models.privileged_access_log import PrivilegedAccessLog
from shared.security.current_user_context import reset_current_user_id, set_current_user_id
from tests.factories.conversation import ConversationFactory, MessageFactory


def _now():
    return datetime.now(timezone.utc)


class TestConversationMutable:
    def test_created_by_populated_on_insert(self, db):
        user_id = uuid.uuid4()
        token = set_current_user_id(user_id)
        try:
            conversation = ConversationFactory()
            db.add(conversation)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert conversation.created_by == user_id

    def test_updated_by_populated_on_update(self, db):
        conversation = ConversationFactory()
        db.add(conversation)
        db.commit()

        updater_id = uuid.uuid4()
        token = set_current_user_id(updater_id)
        try:
            conversation.message_count = 2
            conversation.last_activity_at = _now()
            db.commit()
        finally:
            reset_current_user_id(token)

        assert conversation.updated_by == updater_id


class TestMessageAppendOnly:
    # No update code path exists for Message anywhere in the app (see app/crud/conversation.py).

    def test_created_by_populated_on_insert(self, db):
        user_id = uuid.uuid4()
        token = set_current_user_id(user_id)
        try:
            message = MessageFactory()
            db.add(message)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert message.created_by == user_id

    def test_updated_by_stays_null_with_no_update_path(self, db):
        token = set_current_user_id(uuid.uuid4())
        try:
            message = MessageFactory()
            db.add(message)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert message.updated_by is None


class TestPrivilegedAccessLogAppendOnly:
    def test_created_by_matches_existing_actor_field(self, db):
        """actor_user_id already captures the acting user (task 1.3) — the
        automatically-populated created_by should equal it, not diverge."""
        actor_id = uuid.uuid4()
        token = set_current_user_id(actor_id)
        try:
            log = PrivilegedAccessLog(
                actor_user_id=str(actor_id),
                customer_id=str(uuid.uuid4()),
                method="PUT",
                path="/api/v1/chat",
                created_at=_now(),
            )
            db.add(log)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert log.created_by == actor_id
        assert str(log.actor_user_id) == str(actor_id)

    def test_updated_by_stays_null_with_no_update_path(self, db):
        token = set_current_user_id(uuid.uuid4())
        try:
            log = PrivilegedAccessLog(
                actor_user_id=str(uuid.uuid4()),
                customer_id=str(uuid.uuid4()),
                method="GET",
                path="/api/v1/chat",
                created_at=_now(),
            )
            db.add(log)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert log.updated_by is None
