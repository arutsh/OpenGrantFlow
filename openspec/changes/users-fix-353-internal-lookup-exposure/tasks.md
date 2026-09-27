# Tasks

Workflow rule: one task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

## 1. Close public exposure of user lookups

- [ ] 1.0 Run `scripts/flow.py start users-fix-internal-lookup-exposure 1` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 1.1 Add deny rules for `/api/v1/users/by_ids` and `/api/v1/customers/by_ids` (with and without a trailing slash) to `Caddyfile`, `nginx/nginx.conf`, and `nginx/nginx-dev.conf`, placed before the generic users/customers handlers; verify through local nginx-dev that `curl -X POST .../api/v1/users/by_ids/ -d '[]'` returns 404/403.
- [ ] 1.2 Make `build_users_select([])` and `get_customers_by_ids([])` match nothing (keep `None` meaning "unfiltered"), and short-circuit `[]` in both routes; verify with tests that `[]` returns `[]` from both endpoints.
- [ ] 1.3 Require `get_validated_user` on `GET /api/users/{user_id}` and allow only self or a same-company admin (claims-based), returning 404 otherwise; verify with tests for anonymous (401), cross-tenant (404), self (200), and same-company admin (200).
- [ ] 1.4 Correct the gateway-exclusion comment in `services/budget/app/api/budget_routes.py`; verify by reading the diff.
- [ ] 1.5 Run `pytest services/users services/budget` and `flake8 --max-line-length=100` clean; after the prod deploy, confirm via curl that the Caddy deny rule is live; PR merged.

## 2. Service credential on internal lookups — ticket depends on 1

- [ ] 2.0 Run `scripts/flow.py start users-fix-internal-lookup-exposure 2` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 2.1 Add `shared/security/internal_service.py` with a `require_internal_service` dependency (constant-time compare, 401 on missing/wrong/unset) and `INTERNAL_SERVICE_TOKEN` settings in users and budget; verify with unit tests for valid, wrong, missing, and unset cases.
- [ ] 2.2 Apply it to `POST /api/users/by_ids/` and `POST /api/customers/by_ids/`, and accept it as an alternative credential on `GET /api/users/{user_id}`; verify with route tests.
- [ ] 2.3 Send the header from `services/budget/app/services/user_client.py` and `customer_client.py`; verify budget tests covering user/customer name resolution pass, plus one test asserting the header is sent.
- [ ] 2.4 Add the `INTERNAL_SERVICE_TOKEN` variable name to the users and budget env templates, `.github/workflows/*.yml` test env, and the deploy config. Ask the user to set the real secret values (don't read or write secret files yourself); verify CI passes.
- [ ] 2.5 On staging/dev, confirm that budget pages show creator and company names, and that a direct unauthenticated call to `users:8000/api/users/by_ids/` from inside the network returns 401.
- [ ] 2.6 Run `pytest services/users services/budget` and `flake8 --max-line-length=100` clean; PR merged.
