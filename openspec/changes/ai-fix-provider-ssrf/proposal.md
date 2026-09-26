## Why

Any company admin, including a self-registered founder, who becomes `admin` on onboarding, can save an Ollama config with an arbitrary `base_url` through `POST /ai/settings/keys`. The AI service then sends model requests to `{base_url}/v1/chat/completions` from inside the Docker network (`services/ai/app/services/adapters/ollama.py`). Nothing validates the scheme, host, or resolved address. The OpenAI SDK client it uses also follows redirects by default. The result is a tenant-controlled SSRF into internal services (`users:8000`, `budget:8000`, Redis, Postgres, cloud metadata endpoints). This is verified in code; no live exploit was attempted.

## What Changes

- Add an **operator-controlled destination policy** for custom provider endpoints, set through AI-service configuration, never through tenant APIs. It holds a list of approved origins. Each origin is flagged as either public-only or allowed-to-be-private (for an operator-run Ollama such as `http://ollama:11434`).
- `POST /ai/settings/keys` rejects a `base_url` that is not an approved origin (422). It also rejects `base_url` for providers that don't use one.
- Requests are checked again when they are made. The adapter fails closed for stored rows that no longer match the policy, including rows saved before this change.
- Outbound model requests to custom endpoints don't follow redirects. For origins not flagged private-OK, the client resolves the host, rejects non-public addresses (loopback, RFC1918, link-local/metadata, CGNAT, ULA, IPv4-mapped forms), and connects to the IP it validated. A DNS answer that changes between check and connect cannot redirect the connection.
- The Settings UI offers the approved endpoints as choices instead of a free-text URL.
- The current hard-coded default `http://localhost:11434` becomes the operator-configured default.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `ai-provider-settings`: custom provider endpoints are restricted to an operator-approved destination policy, enforced at save and at request time.

## Impact

- `services/ai/app/api/settings_routes.py`, `app/services/adapters/ollama.py`, `app/core/config.py`, a new `app/services/egress_policy.py`
- The provider catalog response gains the approved endpoints, used by `frontend-typescript/src/pages/Settings/components/AiIntegrationsSection.tsx`
- **BREAKING** for any tenant whose saved Ollama URL isn't approved: those configs stop resolving until an operator approves the origin. Existing rows get a pre-deploy audit (see tasks).
- New AI-service env var for the policy; it must be set in every environment that uses Ollama.
