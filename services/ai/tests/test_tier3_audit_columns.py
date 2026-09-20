"""audit-mixin-rollout-tier3 group 1: created_by/updated_by population for
AIAuditLog, AIPrompt, UserProviderKey, CustomerAiDefaults, PrivilegedAccessLog."""

import uuid
from datetime import datetime, timezone

from app.models.audit_log import AIAuditLog
from app.models.prompt import AIPrompt
from app.models.user_provider_key import UserProviderKey
from app.models.customer_ai_defaults import CustomerAiDefaults
from app.models.privileged_access_log import PrivilegedAccessLog
from app.models.ai_provider import AIProvider
from shared.security.current_user_context import reset_current_user_id, set_current_user_id


def _now():
    return datetime.now(timezone.utc)


class TestAIAuditLogAppendOnly:
    def test_created_by_populated_on_insert(self, db):
        user_id = uuid.uuid4()
        token = set_current_user_id(user_id)
        try:
            log = AIAuditLog(
                customer_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                prompt_version="v1",
                input_text="text",
                provider="anthropic",
                model="claude",
                success=True,
                duration_ms=1,
                created_at=_now(),
            )
            db.add(log)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert log.created_by == user_id

    def test_updated_by_stays_null_with_no_update_path(self, db):
        log = AIAuditLog(
            customer_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            prompt_version="v1",
            input_text="text",
            provider="anthropic",
            model="claude",
            success=True,
            duration_ms=1,
            created_at=_now(),
        )
        db.add(log)
        db.commit()

        assert log.updated_by is None


class TestAIPromptMutable:
    def test_created_by_populated_on_insert(self, db):
        user_id = uuid.uuid4()
        token = set_current_user_id(user_id)
        try:
            prompt = AIPrompt(
                name="excel_extraction",
                version="v1",
                system_prompt="sys",
                user_template="tmpl",
                created_at=_now(),
            )
            db.add(prompt)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert prompt.created_by == user_id

    def test_updated_by_populated_on_update(self, db):
        prompt = AIPrompt(
            name="excel_extraction",
            version="v1",
            system_prompt="sys",
            user_template="tmpl",
            created_at=_now(),
        )
        db.add(prompt)
        db.commit()

        updater_id = uuid.uuid4()
        token = set_current_user_id(updater_id)
        try:
            prompt.is_active = True
            db.commit()
        finally:
            reset_current_user_id(token)

        assert prompt.updated_by == updater_id


class TestUserProviderKeyMutable:
    def _make_provider(self, db):
        provider = AIProvider(name="anthropic", display_name="Anthropic")
        db.add(provider)
        db.commit()
        return provider

    def test_created_by_populated_on_insert(self, db):
        provider = self._make_provider(db)
        user_id = uuid.uuid4()
        token = set_current_user_id(user_id)
        try:
            key = UserProviderKey(
                user_id=str(uuid.uuid4()),
                provider_id=provider.id,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(key)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert key.created_by == user_id

    def test_updated_by_populated_on_update(self, db):
        provider = self._make_provider(db)
        key = UserProviderKey(
            user_id=str(uuid.uuid4()),
            provider_id=provider.id,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(key)
        db.commit()

        updater_id = uuid.uuid4()
        token = set_current_user_id(updater_id)
        try:
            key.label = "renamed"
            db.commit()
        finally:
            reset_current_user_id(token)

        assert key.updated_by == updater_id


class TestCustomerAiDefaultsMutable:
    def test_created_by_populated_on_insert(self, db):
        user_id = uuid.uuid4()
        token = set_current_user_id(user_id)
        try:
            defaults = CustomerAiDefaults(customer_id=str(uuid.uuid4()), updated_at=_now())
            db.add(defaults)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert defaults.created_by == user_id

    def test_updated_by_populated_on_update(self, db):
        defaults = CustomerAiDefaults(customer_id=str(uuid.uuid4()), updated_at=_now())
        db.add(defaults)
        db.commit()

        updater_id = uuid.uuid4()
        token = set_current_user_id(updater_id)
        try:
            defaults.platform_fallback_enabled = True
            db.commit()
        finally:
            reset_current_user_id(token)

        assert defaults.updated_by == updater_id


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
                path="/api/v1/ai/settings",
                created_at=_now(),
            )
            db.add(log)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert log.created_by == actor_id
        assert str(log.actor_user_id) == str(actor_id)

    def test_updated_by_stays_null_with_no_update_path(self, db):
        log = PrivilegedAccessLog(
            actor_user_id=str(uuid.uuid4()),
            customer_id=str(uuid.uuid4()),
            method="GET",
            path="/api/v1/ai/settings",
            created_at=_now(),
        )
        db.add(log)
        db.commit()

        assert log.updated_by is None
