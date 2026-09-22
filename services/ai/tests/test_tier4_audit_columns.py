"""audit-mixin-rollout-tier4 group 1: created_by/updated_by population for
AIProvider, AIProviderModel."""

import uuid

from app.models.ai_provider import AIProvider
from app.models.ai_provider_model import AIProviderModel
from shared.security.current_user_context import reset_current_user_id, set_current_user_id


class TestAIProviderMutable:
    def test_created_by_populated_on_insert(self, db):
        user_id = uuid.uuid4()
        token = set_current_user_id(user_id)
        try:
            provider = AIProvider(name="anthropic", display_name="Anthropic")
            db.add(provider)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert provider.created_by == user_id

    def test_created_by_stays_null_for_unauthenticated_seed_insert(self, db):
        provider = AIProvider(name="ollama", display_name="Ollama")
        db.add(provider)
        db.commit()

        assert provider.created_by is None

    def test_updated_by_populated_on_update(self, db):
        provider = AIProvider(name="anthropic", display_name="Anthropic")
        db.add(provider)
        db.commit()

        updater_id = uuid.uuid4()
        token = set_current_user_id(updater_id)
        try:
            provider.is_active = False
            db.commit()
        finally:
            reset_current_user_id(token)

        assert provider.updated_by == updater_id


class TestAIProviderModelMutable:
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
            model = AIProviderModel(
                provider_id=provider.id, name="claude-haiku-4-5", display_name="Claude Haiku 4.5"
            )
            db.add(model)
            db.commit()
        finally:
            reset_current_user_id(token)

        assert model.created_by == user_id

    def test_created_by_stays_null_for_unauthenticated_seed_insert(self, db):
        provider = self._make_provider(db)
        model = AIProviderModel(
            provider_id=provider.id, name="claude-haiku-4-5", display_name="Claude Haiku 4.5"
        )
        db.add(model)
        db.commit()

        assert model.created_by is None
