# Design

## Context

- Budget calls the users service directly on the Docker network (`USER_ALL_SERVICES_URL` → `http://users:8000/api/`), never through the gateway. Blocking the paths at the gateway therefore cannot break a service caller.
- Budget forwards the end user's bearer token on `get_users_by_ids`/`get_customers_by_ids`. `customer_client.get_customer` sends no token, because it runs where there is no user context.
- Budget legitimately resolves users and customers **across tenants**: donors see grantee creator names, and the donor/grantee dashboards look up the counterparty company. So the users service cannot tenant-scope `by_ids` by the forwarded user token without breaking those flows. Authorization for *which* ids to resolve stays with the calling service, as today. The fix is to make sure only services can call it.
- Three gateway configs exist and must stay in sync (Caddy is prod).

## Goals / Non-Goals

**Goals:** no anonymous internet path to any user or customer record; defense in depth on the internal network.

**Non-Goals:**
- mTLS or per-service identities. One shared secret is proportionate for four services on one Docker network.
- Tenant-scoping `GET /api/customers/` (any authenticated user can list/search customers). That is used for donor-to-grantee discovery; it is a separate product question and not part of this finding.

## Decisions

1. **Gateway deny first (group 1), shared secret second (group 2).** The deny rules plus the empty-list fix close the internet-facing exposure with no secret rollout, so they can ship today. The shared secret is defense in depth against anything else on the network, such as an SSRF from the AI service (see `ai-fix-provider-ssrf`).
2. **Header `X-Internal-Service-Token` checked by a shared FastAPI dependency** (`shared/security/internal_service.py`) using `hmac.compare_digest`. It raises 401 when the header is missing or wrong, and also when the setting is empty (fail closed). *Alternative:* a signed service JWT. Rejected as heavier than needed, since there is no need for claims.
3. **`GET /api/users/{id}` accepts either credential.** A user token is checked for self or same-company admin via token claims. A service token is allowed so future internal callers don't need a separate route. Cross-tenant reads return 404, not 403, to avoid confirming that the id exists.
4. **Empty list → return `[]` in the route and the CRUD helper.** Both guard it, because `build_users_select(None)` is legitimately "all users" for the admin list route. Make `build_users_select` treat `[]` as "match nothing" (`false()`), distinct from `None`.

## Risks / Trade-offs

- [Secret missing in one environment breaks budget's user and customer name resolution] → deploy the secret to users and budget *before* merging group 2; users logs `internal_service_token_unset` at startup; group 2 includes a staging check.
- [Gateway rule typo] → group 1 adds a curl check through each gateway (local nginx-dev, prod Caddy after deploy).
- [e2e or other tests call `by_ids` anonymously] → grep and update in group 2.

## Migration Plan

Group 1: deploy normally. Group 2: add `INTERNAL_SERVICE_TOKEN` to users and budget env files and secrets in all environments (the user manages secret values; the implementer only references the variable names), then deploy. Rollback: revert the PR. The gateway deny rules stay regardless.
