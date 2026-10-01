# Proposal

## Why

The BYOK provider catalog currently offers only Anthropic (hosted, US) and Ollama (self-hosted). Customers who need an EU-hosted, cost-sensitive hosted option have no choice — Mistral AI (Paris, France) is the standard EU-based hosted-API provider and fits the existing BYOK adapter pattern (`ProviderAdapter`/`@register`) with no architectural change: it's a keyed hosted API like Anthropic, not a custom-endpoint provider like Ollama, so it doesn't interact with `ai-fix-provider-ssrf`'s egress policy.

## What Changes

- Add a `MistralAdapter` (`services/ai/app/services/adapters/mistral.py`) registered as `"mistral"`, using `pydantic_ai.models.mistral.MistralModel` and validating keys via a direct `mistralai` SDK call, mirroring `AnthropicAdapter`.
- Seed an `ai_providers` row for Mistral and `ai_provider_models` rows for its catalog (e.g. Large, Medium, Small) via a new migration.
- **Fix**: `settings_routes.py` currently infers "does this provider need a key" and "does this provider default to a local base URL" from whether `provider.key_prefix` is set. Mistral has no fixed key prefix but does require a key, which breaks both inferences (a keyless Mistral config could be saved, and it would wrongly default `base_url` to `http://localhost:11434`). Add an explicit `requires_key` column to `AIProvider` and use it in both checks instead of `key_prefix` presence. **BREAKING** for the `ai_providers` schema (new non-nullable column, backfilled for existing rows in the same migration — no behavior change for Anthropic/Ollama).
- Add Mistral to the frontend's hardcoded `PROVIDERS`, `MODELS_BY_PROVIDER`, and `PROVIDER_HELP` maps in `AiIntegrationsSection.tsx` (same hardcoding `ai-provider-model-catalog-api` already tracks replacing — not addressed here).
- Add `mistralai` to `services/ai/requirements.txt` and the `mistral` extra to the pinned `pydantic-ai-slim[...]` install.

## Capabilities

### New Capabilities
- `ai-provider-mistral`: Mistral as a BYOK hosted-API provider (key + model catalog), and the provider-requirements mechanism (explicit `requires_key` flag) that its addition exposes as broken for prefix-less keyed providers.

### Modified Capabilities
(none — `ai-provider-settings`'s existing requirements are provider-agnostic scoping/defaults behavior, unaffected by adding a provider)

## Impact

- `services/ai/app/models/ai_provider.py` (new `requires_key` column), `services/ai/app/services/adapters/mistral.py` (new), `services/ai/app/api/settings_routes.py`, `services/ai/migrations/versions/019_add_mistral_provider.py` (new)
- `services/ai/requirements.txt`
- `frontend-typescript/src/pages/Settings/components/AiIntegrationsSection.tsx`
- Tests: `services/ai` adapter/route tests, a migration backfill test, and a frontend component test for the new provider option
