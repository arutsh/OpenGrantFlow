## Why

Two independent findings on the same auth surface (`services/users/app/api/auth_routes.py`, `services/users/app/crud/user_crud.py`):

1. **No shared claims builder.** `register_endpoint`, `login`, and `refresh_token` each independently build their own inline JWT claims dict literal, with no shared schema pinning claim key names/types across the Python producer, the hand-written `TokenClaims` TS interface in `AuthContext.tsx`, and the budget service's `require_donor` check that reads the same decoded payload. Only 3 call sites exist today, but nothing enforces staying in sync as more are added (admin impersonation, magic-link login, password-reset auto-login), and a claim-name typo would silently break consumers rather than erroring.
2. **Cross-tenant email enumeration.** `create_invited_user` checks `UserModel.email == email` with no company/deleted_at/status scoping — an authenticated company admin can probe any email via the invite form and learn from the 400/success split whether it's registered anywhere on the platform, including at a company they have no relationship to.

Grouped together because they're the same file area and both auth-hardening debt, not because they're the same kind of fix.

## What Changes

- Centralize JWT claims construction into one `_build_access_token_claims(db, user, session)` function called from all token-issuance sites; consider a shared schema/type pinning the claim shape between backend and frontend.
- Decide the desired behavior for invite-time uniqueness checking: scope to same-company only (and give a generic non-committal response for other-company/global collisions), or explicitly accept and document the current cross-tenant signal. **This is a product/security tradeoff, not just a bug — needs an explicit decision recorded in design.md before implementation, not a silent fix.**

## Capabilities

### New Capabilities
(none — this is a hardening/refactor of the existing auth-claims and invite-uniqueness mechanisms)

## Status

Proposal only — no design.md/tasks.md yet. The claims-builder centralization is a straightforward refactor; the enumeration item needs a product decision first.
