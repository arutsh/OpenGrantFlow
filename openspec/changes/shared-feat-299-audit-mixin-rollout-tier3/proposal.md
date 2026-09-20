## Why

11 models across `ai`, `chat`, and `users` already track their own `created_at`/`updated_at` but have no `created_by`/`updated_by` — there's no way to answer "who created/changed this row" for AI prompts, provider keys, conversations, messages, or privileged-access logs. With automatic population now in place (`audit-mixin-auto-population`), rolling `AuditMixin`/`AuditColumnsMixin` out to these models is now just a schema + inheritance change — no CRUD wiring needed — making this a natural next slice.

## What Changes

- Add `created_by`/`updated_by` columns (via `AuditMixin` or `AuditColumnsMixin`, as appropriate to each model's primary key) to: `AIAuditLog`, `AIPrompt`, `UserProviderKey` (service `ai`); `Conversation`, `Message` (service `chat`); `CustomerAiDefaults`, `UserProfileModel` (service `ai`/`budget` respectively — non-`id` PKs, use `AuditColumnsMixin`); `PrivilegedAccessLog` ×4 (one per service).
- For append-only models (`AIAuditLog`, `PrivilegedAccessLog` ×4) — rows are never updated — `updated_by` will remain permanently `NULL` by design; only `created_by` is meaningful. No update path is added for these.
- `UserProfileModel` is a read-through cache of user data synced from the `users` service, not a source of truth — decide during implementation whether audit columns are meaningful here or whether it should be an explicit, documented exemption from the coverage guard (`audit-mixin-coverage-guard`) instead.
- Each model change requires an Alembic migration in its owning service (`ai`, `budget`, `chat`, `users`) adding the new nullable columns — no backfill, no data migration.
- **BREAKING**: none — new columns are nullable, existing rows get `NULL`.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `model-audit-trail`: extends the existing automatic-population requirements to the 11 Tier 3 models; adds the append-only-model exception (created_by populated, updated_by intentionally always NULL, no update path).

## Impact

- Model files: `services/ai/app/models/{audit_log.py, prompt.py, user_provider_key.py, customer_ai_defaults.py, privileged_access_log.py}`, `services/chat/app/models/{conversation.py, message.py, privileged_access_log.py}`, `services/budget/app/models/{user_cache.py, privileged_access_log.py}`, `services/users/app/models/privileged_access_log.py`.
- New Alembic migration per affected service (4 services).
- Depends on `audit-mixin-auto-population` being implemented first (needs `AuditColumnsMixin` and the automatic population listener in place).
