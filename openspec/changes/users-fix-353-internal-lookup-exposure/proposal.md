## Why

We confirmed that the users service leaks its whole user directory to anonymous internet callers:

- `POST /api/users/by_ids/` and `POST /api/customers/by_ids/` have no authentication ("internal service use only"), yet they are publicly routed by Caddy (`/api/v1/users/*`, `/api/v1/customers/*`) and both nginx configs. A comment in `budget_routes.py` claims a gateway exclusion protects `by_ids`. No such exclusion exists in any of the three configs.
- `build_users_select([])` treats an empty list as "no filter", so `POST /api/v1/users/by_ids/` with body `[]` returns **every user**: email, name, role, status, `customer_id`, and the embedded customer.
- `GET /api/users/{user_id}` is also unauthenticated and returns the same full profile for any id. Those ids are exactly what the empty-list dump hands out.

## What Changes

- Deny `/api/v1/users/by_ids*` and `/api/v1/customers/by_ids*` at the gateway in **all three** configs (Caddyfile, `nginx/nginx.conf`, `nginx/nginx-dev.conf`).
- An empty id list returns an empty result for both `by_ids` endpoints.
- `GET /api/users/{user_id}` requires authentication. It is allowed for the user themself, an admin of the same company, or a caller holding the internal service credential. Everyone else gets 404.
- Add a shared internal-service credential. Services send an `X-Internal-Service-Token` header, users-side routes verify it with a constant-time comparison, and they fail closed when it is unset. Require it on both `by_ids` endpoints. Update the budget service callers (`user_client.py`, `customer_client.py`) to send it.
- Correct the misleading gateway-exclusion comment in `budget_routes.py`.

## Capabilities

### New Capabilities
- `user-directory-access`: who may read user and customer records, how internal service-to-service lookups are authenticated, and what must never be routed publicly.

### Modified Capabilities
(none)

## Impact

- `services/users/app/api/user_routes.py`, `customer_routes.py`, `app/crud/user_crud.py`, `app/crud/customer_crud.py`
- New `shared/security/internal_service.py` dependency
- `services/budget/app/services/user_client.py`, `customer_client.py`, `app/api/budget_routes.py` (comment)
- `Caddyfile`, `nginx/nginx.conf`, `nginx/nginx-dev.conf`
- New secret `INTERNAL_SERVICE_TOKEN` for users and budget, in every environment (local/dev env files, prod env files, GitHub Actions secrets, and the Terraform/Hetzner deploy). This is a deploy-ordering concern; see design.md.
- Related: `users-fix-account-tenant-authz` covers the write-side holes in the same router.
