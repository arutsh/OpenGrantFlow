# Tasks

Workflow rule: one task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

## 1. Remove personal details before retrieval and the model

- [ ] 1.0 Run `scripts/flow.py start ai-feat-site-assistant-feedback 1` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 1.1 Add `app/services/pii_redaction.py` with `redact(text) -> RedactionResult(text, counts)` using the pattern order and placeholders in design.md Decision 1; verify with a table test covering each type, the three `Personal details are removed from questions` scenarios, and the boundary cases `1,000,000`, `2026`, `3 currencies`, `+44 20 7946 0958`, an IBAN with spaces, a card with dashes, an IPv6 address and `https://x.org/p?token=abc`.
- [ ] 1.2 Call `redact` in `ask_route` right after the length check and pass the redacted text to `site_assistant.ask`; put the per-type counts on the `site_assistant.ask` span as integers. Verify with route tests: the scripted model's prompt contains `[email]` and not the address, a 501-character question is still rejected before redaction, and the span attributes contain counts but no text.
- [ ] 1.3 Run `pytest tests/` (with `AI_TEST_POSTGRES_URL`) and `black --check ./app`, `mypy ./app`, `flake8 ./app --max-line-length=100` in `services/ai` clean, and confirm the site-assistant evals still pass; PR merged.

## 2. Privacy wording, box notice and banner — ticket depends on 1

- [ ] 2.0 Run `scripts/flow.py start ai-feat-site-assistant-feedback 2` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 2.1 Update `content/site/legal/privacy-info-collected.md`, `privacy-how-we-use.md`, `privacy-retention.md` and `privacy-processors.md` per the `privacy-policy` delta: stored fields including country and no IP, purpose, review and test-case use, legitimate interest, the 90 days, adapted test cases kept, removal before Anthropic, best-effort wording, and the DB-IP credit. Verify with `Legal.test.tsx` assertions for each scenario, and that no text says questions are not stored.
- [ ] 2.2 Change the box notice in `SiteAssistantBox.tsx` to state the 90-day retention and removal of personal details; verify with `SiteAssistantBox.test.tsx` for both `Visitors are told where questions go` scenarios, with the privacy-policy link still present.
- [ ] 2.3 Flip `frontend-typescript/src/content/notices/privacy-banner.md` (shipped as `status: draft` by `frontend-feat-394-public-site-refresh` group 5) to `status: published`, ahead of question storage in group 3. Check its wording matches the policy from 2.1; if the wording changes, bump `version` so visitors who dismissed the draft see it again. Update the shipped-notice assertion in `privacyNotice.test.ts`, and verify `PrivacyNoticeBanner.test.tsx` passes and the banner renders in a production build (`npm run build && npm run preview`).
- [ ] 2.4 Re-run the retrieval evals, since the legal sections are indexed, and adjust `golden_dataset.yaml` only if an expected source genuinely moved.
- [ ] 2.5 Run `npm test`, `npm run lint:ci` and `npx tsc --noEmit -p tsconfig.json` in `frontend-typescript`, and `pytest tests/evals` in `services/ai`, clean; PR merged and the new wording verified live on opengrantflow.com.

## 3. Question records, country lookup and 90-day purge — ticket depends on 1, 2

- [ ] 3.0 Run `scripts/flow.py start ai-feat-site-assistant-feedback 3` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 3.1 Change `site_assistant.ask` to return `AskOutcome` and make `_generate` report `failed` separately from a model refusal (design.md Decision 2); update the route, `scripts/eval_site_assistant.py` and existing tests. Verify with unit tests that each of `short_circuited`, `answered`, `refused` and `failed` is reported, and that existing site-assistant route and eval tests pass unchanged in behavior.
- [ ] 3.2 Add the `SiteAssistantQuestion` model and migration `021_create_site_assistant_questions.py` (design.md Decision 3); verify `alembic upgrade head` then `alembic downgrade -1` round-trips on a scratch DB.
- [ ] 3.3 Add `app/services/geoip.py` (DB-IP Lite through `maxminddb`, opened once, `None` on a missing file or no match, one startup warning) and add `maxminddb` to `requirements.txt`. Add the `GEOIP_MONTH` build arg and the download with previous-month fallback to the ai `Dockerfile`, and pass the month from `deploy.yml` (design.md Decision 5). Verify with unit tests using a stub reader (known IP → code, missing file → `None` plus one warning) and a local `docker build` showing the file present.
- [ ] 3.4 Add the fail-open record write in the route and `answer_id` on `AskResponse` (design.md Decision 4). Verify with Postgres-backed route tests:
  - an answered question writes one row with the redacted question and country, and no IP or hash
  - a short-circuit is recorded
  - 422/429/403/503 write nothing
  - an insert failure still returns the answer with `answer_id: null` and logs only the error type
- [ ] 3.5 Add `tasks/ai/purge_site_assistant_questions.py` (`SITE_ASSISTANT_RETENTION_DAYS`, default 90), its 03:15 UTC beat entry, and its `include=[]` entry (design.md Decision 7); verify with a worker test mirroring `test_cleanup_sessions.py` (91-day row deleted, 89-day row kept) and with `test_celery_task_registration.py` passing.
- [ ] 3.6 Run `pytest tests/` and the lint in `services/ai`, and `pytest tests/` in `services/worker`, clean; PR merged. After deploy, verify on prod that one test question creates one row with redacted text and a country code and no IP (presence-only query over SSH), and that the purge task appears in the worker's beat log the next day.

## 4. Feedback endpoint and answer controls — ticket depends on 3

- [ ] 4.0 Run `scripts/flow.py start ai-feat-site-assistant-feedback 4` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 4.1 Add `POST /ai/site-assistant/feedback` (design.md Decision 6) with `SITE_ASSISTANT_FEEDBACK_PER_IP_DAILY_CAP` (default 50); verify with route tests for every `Visitor feedback on an answer` scenario, 404 for an unknown ID, 404 when the assistant is disabled, and 429 over the feedback cap.
- [ ] 4.2 Add `answer_id` to `siteAssistantApi.ts` and a `useSiteAssistantFeedback` mutation (`retry: false`); verify with `siteAssistantApi.test.tsx` cases for the request body and error classification.
- [ ] 4.3 Add `AssistantFeedback` to the answer footer of `SiteAssistantBox` (design.md Decision 10); verify in `SiteAssistantBox.test.tsx` every `Feedback controls on answers` scenario (null `answer_id`, fallback reply, thumbs-down with reason, request failure keeps the answer).
- [ ] 4.4 Mention in `docs/user-guide/README.md` §4.2 that answers can be rated, update its review date, and re-run the retrieval evals since the guide is indexed.
- [ ] 4.5 Run `pytest tests/` and the lint in `services/ai`, and `npm test`, `npm run lint:ci` and `npx tsc --noEmit -p tsconfig.json` in `frontend-typescript`, clean; PR merged. After deploy, verify on prod that a thumbs-down sets the rating on its row.

## 5. Review CLI and production-sourced dataset entries — ticket depends on 3

- [ ] 5.0 Run `scripts/flow.py start ai-feat-site-assistant-feedback 5` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 5.1 Add the `source` field to the golden dataset loader (default `authored`, reject provenance fields on `production` entries, check expected IDs exist in `load_site_chunks` + `load_guide_chunks`) and a per-source block in the retrieval report (design.md Decision 9); verify with unit tests for each modified `Golden dataset format` scenario and the production-sourced breakdown, and that the existing 58 entries load as `authored` with retrieval evals still passing.
- [ ] 5.2 Add `scripts/site_assistant_review.py export` (read-only, JSON Lines on stdout, filters `--days`, `--rating`, `--outcome`) and the `*.site-review.jsonl` `.gitignore` entry; verify with a Postgres-backed test that the filters select the right rows and that the output holds no field beyond the record's stored ones.
- [ ] 5.3 Add `promote <file> <record-id>` (confirm or rewrite the question, validate expected IDs, text-append a `source: production` entry with no record ID, country or timestamp) per design.md Decision 8; verify with tests feeding scripted input: a promoted entry round-trips through the loader, an unknown content ID leaves the file byte-identical, and existing comments in `golden_dataset.yaml` survive.
- [ ] 5.4 Document the export → copy → promote flow, where exports may live, and the need for a new answer baseline after a batch of promotions in `services/ai/tests/evals/README.md` (or create it if release-gates group 5 hasn't landed); verify the commands run as written against a local database.
- [ ] 5.5 Run `pytest tests/` and the lint in `services/ai` clean; PR merged.
