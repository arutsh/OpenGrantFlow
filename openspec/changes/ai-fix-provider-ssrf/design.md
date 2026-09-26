# Design

## Context

- Only the Ollama adapter reads `base_url`. Other adapters ignore it, but the column is stored for every provider.
- `OpenAIProvider(base_url=…)` builds an `openai.AsyncOpenAI` client, which sets `follow_redirects=True` on its httpx client by default (openai 2.x `_base_client.py`). `OpenAIProvider` accepts a caller-supplied `http_client`, which is where the policy is enforced.
- `settings.OLLAMA_URL` (env) already exists as an operator default. `_DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"` is hard-coded in the route.
- The user-facing UI (`AiIntegrationsSection.tsx`) offers a free-text URL input for key-less providers.

## Goals / Non-Goals

**Goals:** tenants cannot direct the AI service's outbound traffic anywhere the operator hasn't approved; operator self-hosted Ollama keeps working.

**Non-Goals:**
- Network-level egress controls (a Docker network split or firewall). Worth doing, but that is infra and belongs in a separate change.
- Allowing arbitrary tenant-supplied public URLs. That is deferred until a tenant needs it. The connect-time guard built here is the precondition for it.

## Decisions

1. **Allowlist of origins, not a denylist of internal ranges.** A denylist alone can't express "our own `ollama` container is fine, `users:8000` isn't". Both resolve to private addresses on the Docker network. Config: `AI_PROVIDER_APPROVED_ORIGINS` as a JSON list of `{"origin": "http://ollama:11434", "allow_private": true}`. Matching is exact on normalized scheme, lowercased host and effective port. Path prefixes are allowed but not significant.
2. **Validate twice.** Save-time validation gives a clear 422. Use-time validation covers old rows and later policy tightening. The adapter returns `None` (the existing "unusable" path) on violation and logs `ai_egress_denied` with customer id and origin, never the full URL's userinfo.
3. **Pinned-address transport for public-only origins.** A custom `httpx.AsyncHTTPTransport` subclass (or httpcore network backend) resolves the host, validates every returned address with `ipaddress` (`is_global` plus explicit blocks for `100.64/10`, `169.254/16`, `fc00::/7`, IPv4-mapped IPv6), and connects to the first valid IP while keeping the `Host` header and TLS SNI set to the original hostname. It is passed to `OpenAIProvider(http_client=httpx.AsyncClient(transport=…, follow_redirects=False))`. *Alternative:* resolve-then-connect by hostname. Rejected because it is open to rebinding.
4. **Private-allowed origins skip the address check but still skip redirects.** The operator vouched for the host, not for wherever it redirects.
5. **The UI switches to a picker.** The provider catalog response adds `approved_endpoints` (origin plus label) for key-less providers. The free-text input is removed. If only one endpoint is approved, it is preselected.

## Risks / Trade-offs

- [Existing tenant configs with custom URLs break] → task 1.1 counts existing non-default `base_url` values per origin before merge. The user decides which origins to approve.
- [The pinned transport has subtle TLS/SNI bugs] → test against a local HTTPS server fixture with a mocked resolver; public-only origins are rare today (Ollama is typically private).
- [Blocking DNS lookups in async code] → use `loop.getaddrinfo` (async).

## Migration Plan

Set `AI_PROVIDER_APPROVED_ORIGINS` in every environment (at minimum the current operator Ollama) before deploying group 1. Rollback: revert. The env var is harmless without the code.
