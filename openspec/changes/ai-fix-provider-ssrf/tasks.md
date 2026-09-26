# Tasks

Workflow rule: one task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

## 1. Approved-origin policy at save and use time

- [ ] 1.0 Run `scripts/flow.py start ai-fix-provider-ssrf 1` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 1.1 Draft a read-only SQL count of `user_provider_keys.base_url` grouped by origin and hand it to the user to run on prod; record which origins should be approved before merging.
- [ ] 1.2 Add `AI_PROVIDER_APPROVED_ORIGINS` to AI settings and an `egress_policy` module (parse, normalize, `is_approved(url) -> ApprovedOrigin | None`, reject non-http(s) schemes and userinfo); verify with unit tests covering case, default ports, trailing slashes, userinfo, and `file://`/`gopher://` schemes.
- [ ] 1.3 Enforce it in `POST /ai/settings/keys` (422 for unapproved origins or a `base_url` on providers that don't take one) and replace `_DEFAULT_OLLAMA_BASE_URL` with the configured default; verify with route tests for `http://users:8000`, `http://169.254.169.254`, and an approved origin.
- [ ] 1.4 Enforce it in `OllamaAdapter.build` (return `None` and log `ai_egress_denied`) and pass an `httpx.AsyncClient(follow_redirects=False)` via `http_client`; verify with tests that a stored unapproved row resolves to "no provider" and, using `respx`, that a 302 to an internal address is not followed.
- [ ] 1.5 Add the variable to AI env templates and CI; ask the user to set the prod values. Run `pytest services/ai` and `flake8 --max-line-length=100` clean; PR merged.

## 2. Connect-time address pinning and endpoint picker — ticket depends on 1

- [ ] 2.0 Run `scripts/flow.py start ai-fix-provider-ssrf 2` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 2.1 Implement the pinned-address transport for public-only origins (async resolve, `ipaddress` validation including CGNAT, link-local, ULA and IPv4-mapped addresses, connect to the validated IP while keeping Host/SNI); verify with mocked-resolver tests for a private answer, mixed public and private answers, and a rebinding sequence (public, then private).
- [ ] 2.2 Wire it into `OllamaAdapter` for origins without `allow_private`; verify that an approved private-allowed origin still works against a local stub server.
- [ ] 2.3 Expose `approved_endpoints` in the provider catalog response and replace the free-text URL input in `AiIntegrationsSection.tsx` with a picker; verify with the component test and a manual check on local dev.
- [ ] 2.4 Run `pytest services/ai`, `flake8 --max-line-length=100`, and frontend `npm test`/`npm run lint` clean; PR merged.
