## Why

A security review found, and we verified, three ways to gain privileges or tenant membership in the users service:

1. **Anonymous superuser creation.** `POST /api/users/` is publicly routed (Caddy `/api/v1/users/*`), unauthenticated, and writes `UserCreate` (including `role` and `status`) straight into `UserModel`. An attacker can create `role=superuser` with their own email, call `/auth/resend-verification`, and `/auth/verify-email` then mints a superuser access and refresh token.
2. **Unauthorized tenant membership.** `POST /register` accepts any `customer_id`. `PATCH /users/{id}/` lets any user set `customer_id` to any existing company: the `elif user_update.customer_id` branch runs for non-superusers, and its result is written back after `filter_dict_keys`. The user's existing role is kept, so an admin of company A who switches to company B becomes an admin of B. The same line also sets `customer_id = None` when the field is left out, so an ordinary profile edit removes the user from their company. Non-superusers can also set their own `status`.
3. **Impersonation scope escape.** `deactivate_company_service` accepts `is_impersonating` for *any* `customer_id`. `update_user_endpoint` authorizes from the real actor's database role (`is_superuser(db, user_id)`), so a token scoped to tenant A still gets global user-edit powers. This is not an escalation (only superusers mint these tokens), but it breaks the scoping in `customer-impersonation` and `superuser-tenant-administration`.

## What Changes

- **BREAKING:** remove `POST /api/users/`. No frontend or service caller uses it. Accounts are created only through `/register` (always `role=user`, no company) and admin invitations.
- **BREAKING:** `/register` stops accepting `customer_id`. The only ways into an existing company are an admin invitation or a superuser action.
- **BREAKING:** self-service `PATCH /users/{id}/` accepts only `first_name`/`last_name`, plus `new_customer_name` for founder onboarding while the account is `pending`. It rejects `customer_id`, `role`, `status` and `email`, and it never clears membership when a field is omitted.
- Remove the "join an existing company by `customer_id` during onboarding" path from `company-onboarding`. The frontend only ever sends `new_customer_name`.
- **BREAKING:** `PATCH /users/{id}/` becomes self-service only (caller must be the target). The superuser cross-user branch is removed: it read the actor's database role, so it also worked under an impersonation token, against the existing `customer-impersonation` rule on blanket bypasses.
- Company deactivation authorizes from the token's effective claims (`role`, `customer_id`, `is_impersonating`). A direct superuser token can deactivate any company. An impersonation token can deactivate only the company it is scoped to. Audit attribution still records the real superuser `user_id`.
- Adversarial tests for every path above.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `auth-hardening`: no anonymous account-creation path may set role, status or company; registration ignores client-supplied company membership.
- `company-onboarding`: removes the join-existing-company-by-id requirement; profile edits preserve membership and role.
- `customer-impersonation`: impersonation tokens are bound to their effective role and tenant on every users-service write.
- `superuser-tenant-administration`: deactivation under impersonation is limited to the impersonated company.

## Impact

- `services/users/app/api/user_routes.py` (`create_user_endpoint` removed, `update_user_endpoint` rewritten)
- `services/users/app/api/auth_routes.py`, `shared/schemas/auth_schema.py` (`RegisterRequest.customer_id` removed)
- `shared/schemas/user_schema.py` (`UserCreate`/`UserUpdate` narrowed or split into self-service and superuser shapes)
- `services/users/app/services/admin_management_services.py` (`deactivate_company_service`)
- Superusers lose the generic cross-user PATCH. Role changes still work through impersonation plus `PATCH /users/{id}/role`. Moving users between companies and changing status move to the planned `superuser-admin-console` endpoints.
- Related: `users-fix-internal-lookup-exposure` covers the same file's unauthenticated read endpoints.
