# Design

## Context

See proposal.md for motivation; requirements are in `specs/`. Facts from the current code that shape the approach:

- `app/api/site_assistant_routes.py` `ask_route` does these steps in order: strip and length-check, per-IP cap (`enforce_daily_cap` on `hash_client_ip(request.client.host)`), human verification, `resolve_site_assistant_model()`, then `site_assistant.ask(...)`. It returns `AskResponse{answer, answerable, citations}`.
- `site_assistant.ask` knows the retrieved chunks and scores, whether it short-circuited, and the prompt version (inside `_generate`), but returns only `AskResponse`. `_generate` turns model failures into the fallback answer without telling the caller.
- `request.client.host` is the real client address: Caddy overwrites `X-Forwarded-For` and uvicorn runs with `--proxy-headers`.
- Worker pattern: `services/worker/tasks/ai/cleanup_sessions.py` deletes from the ai database with a sync psycopg2 engine built from `settings.AI_DATABASE_URL`. It runs on `beat_schedule` at 03:00 UTC and is listed in `include=[]`, which `tests/test_celery_task_registration.py` guards. `tasks.feedback.*` already exists for bug reports, so new names avoid "feedback".
- `site_content_ingestion.load_site_chunks` and `guide_doc_ingestion.load_guide_chunks` build every `ChunkInput` from files without a database, which is enough to validate content IDs offline.
- `services/ai/.env.ai.prod` is the committed non-secret prod config. `SITE_ASSISTANT_ENABLED=true` was switched on there.
- Frontend: `src/api/siteAssistantApi.ts` holds the config and ask types and hooks. The box renders the notice at `SiteAssistantBox.tsx:85`.
- The latest ai migration is `020_seed_site_assistant_prompt.py`. `ai-feat-site-assistant-release-gates` adds none.

## Goals / Non-Goals

**Goals:**
- The privacy wording, notice and banner ship before storage, so the policy never lags behind what is stored. There is no storage switch: once the records group deploys, every question is recorded.
- Visitor text never reaches logs or spans, as today. Only the database holds the redacted question.
- Redaction is pure and table-tested.

**Non-Goals:**
- Name and free-text PII detection (no NER model).
- An HTTP review endpoint or an admin-console screen. Review is CLI-only until `superuser-admin-console` exists.
- Data-subject access or deletion for records. They are not linked to anyone, so they can't be found per person; the policy says so.
- Re-running a promoted case automatically. Promotion edits the dataset; the release-gates change measures it.

## Decisions

1. **Redact in the route, before `ask`.**
   - `app/services/pii_redaction.py` `redact(text) -> RedactionResult(text, counts)` runs right after the length check, so the limit applies to the submitted text.
   - The redacted text then feeds retrieval, the model and the record. The counts per type go on the span as integers.
   - **Pattern order:** email, then URL query string (keep scheme, host and path; replace `?...` with `?[query]`), then IBAN, then card-like runs of 13–19 digits with optional spaces or dashes, then IPv4/IPv6, then phone (an optional `+`, at least 9 digits, spaces/dots/dashes/brackets allowed, no commas).
   - Requiring 9+ digits and excluding commas keeps amounts like `1,000,000` and short counts.
   - *Alternative:* redact only before storage. Rejected per the user's decision: Anthropic shouldn't see the details either.

2. **`ask` returns an outcome object.** `site_assistant.ask` returns `AskOutcome(response, chunks, outcome, provider, model, prompt_version)`.
   - `outcome` is `short_circuited`, `answered`, `refused` (the model or citation checks gave `answerable: false`) or `failed`.
   - `failed` means the model call raised or the output was invalid. `_generate` reports it instead of collapsing it into the fallback.
   - The route builds the record from it. `AskResponse` gains `answer_id: UUID | None`.
   - *Alternative:* write the record inside `ask`. Rejected: the eval runner and tests call `ask` directly and must not write records.

3. **One table, feedback as columns.** Migration `021_create_site_assistant_questions.py` creates `site_assistant_questions` with these columns:
   - `id` UUID PK, `created_at` timestamptz (indexed)
   - `question` text, `persona`, `country` char(2) null
   - `retrieved` JSON list of `{content_id, score}`, `outcome`, `answer` text null, `cited_ids` JSON
   - `provider`, `model`, `prompt_version` (all null when the model wasn't called)
   - `rating` null, `reason` null, `rated_at` null

   Replacing feedback is an `UPDATE`, and purging one row removes its feedback.
   - No `AuditMixin`: there's no user actor, and `created_by` would be meaningless.
   - *Alternative:* a separate feedback table. Rejected: there's one rating per answer, and a second table only adds a join and a cascade.

4. **The write is fail-open, after the response is built.**
   - The route always inserts the record in its own session and commits; there is no storage switch.
   - *Alternative:* an operator switch. Rejected: the wording ships first, so nothing needs to be held back.
   - Any exception is logged as `site_assistant_record_failed` with `error_type` only, and the response goes out with `answer_id: null`.
   - Requests that end in 422, 429, 403 or 503 return before this point.

5. **Country from DB-IP Lite through `maxminddb`.**
   - `app/services/geoip.py` opens `SITE_ASSISTANT_GEOIP_PATH` once at startup (default `/app/geoip/dbip-country-lite.mmdb`). It logs one warning if the file is missing and then returns `None` for every lookup.
   - The ai `Dockerfile` downloads `dbip-country-lite-<YYYY-MM>.mmdb.gz`, falling back to the previous month, behind `ARG GEOIP_MONTH`. A failed download doesn't fail the build.
   - `deploy.yml` passes the current month as a build arg, so the layer refreshes monthly instead of being cached forever.
   - DB-IP Lite is CC BY 4.0 and needs no account; the privacy policy credits it.
   - *Alternative:* MaxMind GeoLite2. Rejected: it needs an account, a licence key secret and EULA acceptance. *Alternative:* a hosted lookup API. Rejected: it sends every visitor IP to another processor.

6. **Feedback endpoint.**
   - `POST /ai/site-assistant/feedback` uses a pydantic body with `extra="forbid"`, and a validator that rejects a `reason` with `up`.
   - It runs behind `_require_enabled`.
   - It applies `enforce_daily_cap("site-assistant-feedback-ip", hash_client_ip(ip), SITE_ASSISTANT_FEEDBACK_PER_IP_DAILY_CAP)` (default 50).
   - It sets the rating with `UPDATE ... WHERE id = :answer_id` and returns 404 when no row matched, otherwise 204.

7. **Purge task in the worker.**
   - `tasks/ai/purge_site_assistant_questions.py` is named `tasks.ai.purge_site_assistant_questions`. It mirrors `cleanup_sessions.py`: `DELETE FROM site_assistant_questions WHERE created_at < now() - :days`.
   - `SITE_ASSISTANT_RETENTION_DAYS` in the worker config defaults to 90.
   - It runs on beat at 03:15 UTC, is added to `include=[]`, and is covered by the registration test.

8. **Review CLI: export on prod, promote locally.** `services/ai/scripts/site_assistant_review.py`:
   - **`export`** runs inside the prod ai container (`docker compose ... exec ai python scripts/site_assistant_review.py export --days 30 --rating down --outcome short_circuited`). It is read-only and writes JSON Lines to stdout. Records go to the operator's machine only. The repo gitignores `*.site-review.jsonl`, and the README tells operators to keep exports outside the repo.
   - **`promote <file> <record-id>`** runs locally and interactively:
     - It shows the record and asks the operator to confirm or rewrite the question.
     - It asks for expected content IDs, validated against `load_site_chunks` + `load_guide_chunks`, plus category, persona and answerability.
     - It appends a YAML block (text append, so comments survive) to `golden_dataset.yaml` with `id: prod-<slug>`, `source: production`, and no record ID, country or timestamp.
   - *Alternative:* promote straight from the prod DB into a checkout on the server. Rejected: it puts repo writes on the production host.

9. **Dataset `source` field.**
   - `retrieval_eval.load_dataset` defaults `source` to `authored`, rejects `production` entries carrying `record_id`, `country`, `created_at` or `answer_id`, and checks expected IDs exist.
   - The report adds a per-source block.
   - Promotions change the dataset fingerprint the release-gates change records, so a fresh answer baseline is needed. Promote in batches to keep that to about one paid run per batch.

10. **Frontend.**
    - Types gain `answer_id`; a `useSiteAssistantFeedback` mutation posts the rating.
    - A small `AssistantFeedback` component sits in the answer footer:
      - thumbs buttons with `aria-pressed`
      - reason chips after thumbs-down
      - a thank-you on success; on failure, the controls come back
    - The notice text states the 90-day retention unconditionally; it ships with the privacy wording, ahead of storage.
    - `frontend-feat-public-site-refresh` reworks this footer. Whichever lands second moves the component into the new `AnswerBlock` footer row.

## Risks / Trade-offs

- **[Regex misses names and odd formats, so stored questions may still hold personal data]** → The notice and policy say it's best effort and ask visitors to leave details out. Retention is 90 days, records are unlinked, and review is maintainer-only.
- **[Phone regex false positives on long reference numbers]** → They're redacted to `[phone]`, which costs one detail in an answer. Table tests pin the boundary cases (`1,000,000`, `2026`, `+44 20 7946 0958`).
- **[Country plus timestamp plus question could identify someone in a tiny country]** → Country is the only location field. No IP, hash, user agent or session is stored, and exports are kept off the repo.
- **[Promoted questions outlive the 90 days]** → The operator must confirm or rewrite them, provenance fields are rejected by the loader, and the policy discloses it.
- **[Unauthenticated feedback could be spammed with guessed IDs]** → IDs are random UUIDs returned only to the asker, the endpoint has a per-IP cap, and there's one rating per row.
- **[GeoIP download breaks or goes stale]** → The build doesn't fail and lookups return unknown. The monthly build arg refreshes it.
- **[Wording live before storage starts]** → It over-discloses for a short window, which is harmless. The reverse order would under-disclose, so the wording group lands first.

## Migration Plan

1. Group 1 ships redaction. It is live immediately and only reduces what Anthropic receives.
2. Group 2 ships the privacy wording and the box notice, and publishes the draft banner from `frontend-feat-394-public-site-refresh`. The frontend deploys on Vercel.
3. Group 3 deploys migration 021 and starts recording every question. It's an empty table, and its downgrade drops it.
4. Rollback means reverting the record write and redeploying. Existing rows age out through the purge, or can be removed with `TRUNCATE`. If storage is withdrawn for good, the wording is reverted too.
