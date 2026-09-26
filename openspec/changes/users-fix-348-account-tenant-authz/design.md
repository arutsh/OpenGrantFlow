# Design

## Context

See proposal.md for the verified findings. Relevant current state:

- `POST /api/users/` (`create_user_endpoint`) has no auth dependency and no caller in the frontend, e2e suite, or other services. Only unit tests may reference it.
- `/auth/verify-email` mints tokens from whatever `role`/`customer_id` the row holds. It is correct as long as no anonymous path can write those columns, so the fix belongs at account creation, not at verification.
- `update_user_endpoint` mixes three flows: self-service name edits, founder onboarding (`new_customer_name`), and a superuser cross-user edit. The superuser branch reads `is_superuser(db, user_id)`, which is also true under an impersonation token because that token keeps the superuser's real `user_id`.
- `UserUpdate` (in `shared/schemas/user_schema.py`) defaults `status` to `pending` and carries `role`/`customer_id`. It is used only by this endpoint.
- The frontend calls this PATCH only from onboarding (`userOnboarding` in `gatewayApi.ts`/`usersApi.ts`), sending `first_name`, `last_name` and `new_customer_name`.

## Goals / Non-Goals

**Goals:**
- Close every anonymous or self-service path to a privileged role, an active status, or another tenant's membership.
- Make impersonation tokens behave as exactly "admin of customer X" on every users-service write path touched here.

**Non-Goals:**
- `list_users_endpoint` returns all users for a direct superuser token. That also contradicts `customer-impersonation`'s no-blanket-bypass rule, but it is a read, and `superuser-admin-console` already plans to replace it with an explicit endpoint. Left for that change.
- A general cross-service claims builder (tracked by `users-fix-auth-claims-hardening`).
- Retroactively auditing production for rows created through the hole. That is a one-off ops query (task 1.5), not code.

## Decisions

1. **Delete `POST /api/users/` rather than guard it.** It has no legitimate caller, and a guarded generic "create any user" endpoint would duplicate `invite` and the planned `superuser-admin-console`. *Alternative:* superuser-only guard. Rejected because the endpoint also bypasses password, consent and verification-token setup.
2. **Remove `customer_id` from `RegisterRequest`; unknown fields stay ignored.** Pydantic's default `extra="ignore"` drops it silently, so old clients keep working and the field has no effect. *Alternative:* `extra="forbid"` → 422. Rejected: a loud break with no security gain, and it would also reject harmless extras.
3. **Split the PATCH schema.** A new `UserSelfUpdate(first_name?, last_name?, new_customer_name?)` with `extra="forbid"`, so `customer_id`/`role`/`status`/`email` return 422 instead of being silently dropped. For a privilege-bearing field, an explicit rejection is the clearer contract, and the frontend never sends these fields. `UserUpdate` is deleted if nothing else imports it. Only keys the caller actually sent are written (`exclude_unset`), which fixes the `customer_id = None` wipe.
4. **Self-only PATCH; no superuser branch.** The endpoint requires `token.user_id == path user_id`. Cross-user superuser edits go to `superuser-admin-console`, whose endpoints are explicitly superuser-gated and audited. Role changes already have `PATCH /users/{id}/role` (admin of the same company, including under impersonation).
5. **Deactivation authorizes from claims.** `is_impersonating` is true → require `token.customer_id == target`. Otherwise require `token.role == "superuser"`. This is the same `_require_same_company` pattern the other admin services already use. `is_superuser(db, …)` loses its only caller in this router, so delete it if nothing else imports it (the `donor_grantees_services` `is_superuser` is a different, claims-based helper).

## Risks / Trade-offs

- [A tester or ops script relies on `POST /api/users/` or superuser PATCH] → grep tests/e2e/scripts during group 1/2 and move them to `/register` + fixtures or the role endpoint. Call out as BREAKING in the PR.
- [Rows already created through the hole in production] → task 1.5 runs a read-only query for unexpected `superuser` rows and pending users with a `customer_id`, and reports the results to the user before any cleanup.
- [Existing tokens with elevated claims stay valid until expiry] → if 1.5 finds any, revoke those users' sessions manually. Otherwise nothing to do.

## Migration Plan

No schema migration. Deploy groups in order. Rollback is a plain revert of each group's PR.
