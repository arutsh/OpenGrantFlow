One task group = one GitHub ticket = one PR, merged before the next group starts.

## 1. ai service — depends on audit-mixin-auto-population being merged — Issue #301

- [x] 1.1 Add Alembic migration adding nullable `created_by`/`updated_by` to `AIAuditLog`, `AIPrompt`, `UserProviderKey`, `CustomerAiDefaults` (via `AuditColumnsMixin`, non-`id` PK), `PrivilegedAccessLog`.
- [x] 1.2 Update each model class to inherit `AuditMixin`/`AuditColumnsMixin` as appropriate.
- [x] 1.3 For `PrivilegedAccessLog`, check whether an existing actor/subject field already captures the acting user; if so, assert it matches the auto-populated `created_by` in a test rather than treating them as unrelated.
- [x] 1.4 Add/update tests confirming `created_by` is populated on creation for each of the 5 models, and `updated_by` behaves per the model's mutability (populated on update for mutable models, stays `NULL` for the append-only `AIAuditLog`/`PrivilegedAccessLog`).
- [x] 1.5 Run `services/ai`'s test suite clean; PR merged.

## 2. chat service — depends on 1 — Issue #303

- [x] 2.1 Add Alembic migration adding nullable `created_by`/`updated_by` to `Conversation`, `Message`, `PrivilegedAccessLog`.
- [x] 2.2 Update each model class to inherit `AuditMixin`.
- [x] 2.3 Repeat the `PrivilegedAccessLog` actor-field check from task 1.3 for chat's copy.
- [x] 2.4 Add/update tests confirming `created_by`/`updated_by` population for `Conversation`/`Message`, and `created_by`-only for `PrivilegedAccessLog`.
- [x] 2.5 Run `services/chat`'s test suite clean; PR merged.

## 3. budget service — depends on 1 — Issue #305

- [x] 3.1 Decide whether `UserProfileModel` (read-through cache, PK `user_id`) adopts `AuditColumnsMixin` or is documented as an intentional exemption for `audit-mixin-coverage-guard`; record the decision. **Decided: exempt** — see design.md Decision 2. `event_handlers.py`'s RabbitMQ consumer has no request/actor context (permanently `NULL`); `user_cache.py::get_users_by_ids_cached`'s live request-context write would misattribute the row to the viewer, not the cached user. Removed `get_user_from_cache`/`get_user_from_cache_or_fallback` (dead code, same misattribution shape) and their now-orphaned `user_client.get_user`/`UserServiceError`.
- [x] 3.2 Add Alembic migration adding nullable `created_by`/`updated_by` to `PrivilegedAccessLog`.
- [x] 3.3 Update model class(es) to inherit the appropriate mixin.
- [x] 3.4 Repeat the `PrivilegedAccessLog` actor-field check from task 1.3 for budget's copy.
- [x] 3.5 Add/update tests confirming the decided behavior.
- [x] 3.6 Run `services/budget`'s test suite clean; PR merged.

## 4. users service — depends on 1

- [x] 4.1 Add Alembic migration adding nullable `created_by`/`updated_by` to `PrivilegedAccessLog`.
- [x] 4.2 Update the model class to inherit `AuditMixin`.
- [x] 4.3 Repeat the `PrivilegedAccessLog` actor-field check from task 1.3 for users' copy.
- [x] 4.4 Add/update a test confirming `created_by` population, `updated_by` stays `NULL`.
- [x] 4.5 Run `services/users`'s test suite clean; PR merged.
