# Design

## Context

See proposal.md - Why. Two providers exist today: `AnthropicAdapter` (keyed, hosted, `key_prefix="sk-ant-"`, no `base_url`) and `OllamaAdapter` (keyless, custom `base_url`, `key_prefix=None`). `settings_routes.py` conflates "no `key_prefix`" with "is a local base-url provider" in two places:

- `_validate_key_with_provider`: only enforces "key required" `if key_prefix and not key`.
- `create_ai_key`: only defaults `base_url` to `_DEFAULT_OLLAMA_BASE_URL` `if not provider.key_prefix and not base_url`.

Both were written when "no `key_prefix`" and "is Ollama" were the same set of one provider. Mistral breaks that: it requires a key (confirmed — Mistral API keys are opaque tokens with no fixed prefix) but is a hosted API like Anthropic, not a custom endpoint. The frontend already anticipated this split — `AiIntegrationsSection.tsx`'s local `PROVIDERS` array has a `requires_key: boolean` independent of `key_prefix` — but the backend has no equivalent column; it only has `key_prefix` and `is_active`.

## Goals / Non-Goals

**Goals:**
- Add Mistral as a third `ProviderAdapter`, following the Anthropic shape (keyed, hosted, no `base_url`).
- Replace the `key_prefix`-as-proxy checks in `settings_routes.py` with an explicit `AIProvider.requires_key` column, so the mechanism is correct for any future prefix-less keyed provider, not just Mistral.

**Non-Goals:**
- Not building the `ai-provider-model-catalog-api` change (dynamic model list endpoint) — this change still edits the hardcoded frontend `MODELS_BY_PROVIDER`/`PROVIDERS` maps, same as Ollama's addition did.
- Not touching `ai-fix-provider-ssrf`'s egress policy — that policy governs custom/operator-approved `base_url` destinations (Ollama-shaped providers). Mistral's endpoint is fixed by the `mistralai` SDK, never user-supplied, so it's out of scope for that policy.
- Not adding admin UI/CRUD for the provider or model catalog — still migration-seeded, matching the existing pattern.

## Decisions

**Explicit `requires_key` column over continuing to infer from `key_prefix`.** Alternative considered: give Mistral a synthetic/fake `key_prefix` check (e.g. accept any non-empty string) so the existing `if key_prefix and ...` branches keep working. Rejected — that's encoding "has a key requirement" as "has a prefix-format constraint," which are genuinely different facts about a provider (Ollama: neither; Anthropic: both; Mistral: key required, no fixed format). A future provider with the same shape as Mistral would hit the identical bug. The explicit column also lets `key_prefix` go back to meaning only "format hint for client-side/UX validation," which is what the frontend already treats it as.

**Migration backfills `requires_key` for existing rows in the same migration**, not a follow-up: `anthropic.requires_key = true`, `ollama.requires_key = false`, `mistral.requires_key = true` (new row). No nullable-then-backfill window needed since it's set atomically alongside the new row.

**Mistral adapter mirrors `AnthropicAdapter`'s `validate_key`**: a live, cheap call against Mistral's API (its models-list endpoint is a reasonable low-cost validation ping, cheaper than a chat completion) using the `mistralai` SDK directly, catching its auth-error type the way `AnthropicAdapter` catches `anthropic_sdk.AuthenticationError`.

**Model catalog IDs**: exact current Mistral model API identifiers (e.g. the Large/Medium/Small generation live at implementation time) are confirmed against Mistral's own model listing when the migration is written, not guessed here — Mistral's naming has moved through several dated releases and pinning a wrong string in a spec/design doc would go stale silently. Tasks note this explicitly.

## Risks / Trade-offs

- [New non-nullable column on `ai_providers`] → Backfilled in the same migration as it's added; no window where existing rows are invalid, no application code path exercises the column before the migration that adds it runs.
- [Mistral model IDs pinned in a migration go stale if Mistral renames/retires them] → Same risk that already exists for Anthropic's and Ollama's seeded rows; `is_active` on `ai_provider_models` is the existing mitigation (flip inactive rather than hard-delete).
- [`mistralai` is a new third-party dependency in `services/ai`] → Scoped to the one new adapter file; validated the same way `anthropic` SDK already is (pinned version in `requirements.txt`).

## Migration Plan

Single migration `019_add_mistral_provider.py`: add `ai_providers.requires_key` (non-nullable, backfilled), insert the `mistral` provider row with `requires_key=true`, insert its `ai_provider_models` rows. No data migration for `user_provider_keys` — no existing rows reference Mistral. Rollback: standard `downgrade()` dropping the column and the seeded rows.
