# Design

## Context

See proposal.md for motivation. Additional facts that shape the approach:

- `frontend-typescript/src/content/site/**` sections already have globally unique `id` (`<page>.<slug>`), a canonical URL (`<page route>#<anchor>`), optional `personas`, and a `status` of `published`/`draft` (see that directory's README.md). This is most of the `site_chunks` schema already.
- `docs/user-guide/*.md` (`ngo-guide.md`, `donor-guide.md`) and `docs/PRODUCT.md` have no frontmatter and no public URL today.
- `.github/workflows/deploy.yml` is a single SSH job that runs `docker compose up --build` for the whole stack on push to `main`, gated by `paths-ignore` that excludes `**/*.md`, `docs/**`, `frontend-typescript/**`. A content-only merge is invisible to it.
- `.github/workflows/ai.yml` already runs Postgres and `pytest tests/ -v` for the ai service, gated by a `dorny/paths-filter` step scoped to `services/ai/**` and `shared/**`.
- `chat-fix-prompt-injection-provenance`'s `scripts/eval_prompt_injection.py` is an opt-in, not-in-CI live eval against real providers. This change's harness is the opposite shape — deterministic, no LLM, CI-gating — but reuses its reporting layout (per-category breakdown, a committed baseline file) so the repo has one eval-report shape.

## Goals / Non-Goals

**Goals:**
- A self-contained, deterministic retrieval layer and eval harness that needs no LLM and no live API calls.
- Regressions in retrieval quality fail CI the same way a broken test does.
- Guide docs become citable with a real URL without duplicating their content into `site-content`.

**Non-Goals:**
- Embeddings, hybrid search, or any ranking signal beyond Postgres full-text search — tracked as a later experiment (see proposal.md).
- Generation/answering quality — this change stops at ranked chunks, not LLM answers.
- A general-purpose docs-publishing system. `/guides/<slug>` renders `docs/user-guide/*.md` only; it does not become a CMS.

## Decisions

1. **`site_chunks` row per section, keyed by `content_id`.** For `site-content`, one row per published section file, copying `id` → `content_id`, `<page route>#<anchor>` → `url`, `personas`, and the rendered title/body text. For guide docs, one row per H2 section: `content_id` is `<doc-slug>.<heading-slug>` (mirroring the `<page>.<slug>` shape), `url` is `/guides/<doc-slug>#<heading-slug>`, `personas` is empty (guides aren't persona-scoped today).
   - *Alternative considered:* chunk guide docs by fixed token windows. Rejected — H2 sections are already a natural retrieval unit and keep citations human-readable, matching how `site-content` sections work.
2. **`/guides/<slug>` is a new frontend route**, `slug` being the guide doc's filename stem (`ngo-guide`, `donor-guide`). It reads the raw markdown via a Vite `?raw` import (same pattern already used for other static content) and renders it with the existing section-body markdown renderer. No new backend endpoint; the content ships in the frontend bundle like everything else under `src/content/`.
   - This is a `public-site` capability change, but `public-site` doesn't exist in `openspec/specs/` yet — it's still a delta inside the not-yet-archived `frontend-feat-372-public-site-content`. This change's tasks therefore add the route directly (small, mechanical) rather than writing a spec delta against a capability that doesn't exist in the main tree yet. Once `frontend-feat-372-public-site-content` archives, `/guides/<slug>` should be folded into `public-site`'s spec as a follow-up — noted so it isn't lost.
3. **`content_version` is a hash of the chunk's raw text** (`sha256` of the section body/guide-section text). Ingestion upserts by `content_id` and only rewrites a row (and its generated `tsvector`) when the hash changes; rows whose `content_id` no longer exists in the source (unpublished or deleted section) are deleted. This makes ingestion idempotent and cheap to run on every startup.
4. **Retrieval ranking:** `ts_rank_cd(tsvector, query)` as the base score; when a persona is supplied and the chunk has `personas`, a multiplicative boost (`1.0` no-match vs content with personas set, `1.2` match) nudges matching chunks up without hard-filtering, so a grantee's question can still surface an unscoped (no-persona) chunk.
5. **Golden dataset format:** a single YAML file, `services/ai/tests/evals/data/golden_dataset.yaml`, each entry `{id, question, expected_content_ids: [...], persona, category, answerable: bool}`. `answerable: false` entries carry `expected_content_ids: []`.
6. **Unanswerable scoring:** a configurable score threshold (initial value set from the observed score distribution once the dataset exists, recorded in the baseline file). A query is "correctly flagged unanswerable" when its top result's `ts_rank_cd` score falls below the threshold; the eval reports unanswerable accuracy as its own metric, not blended into Recall/MRR (which are computed over answerable questions only).
7. **CI gate:** a baseline file `services/ai/tests/evals/baseline.yaml` holding the floor per metric (overall and per category), e.g. `recall_at_3: 0.9`. The eval harness is a `pytest` module (`services/ai/tests/evals/test_retrieval_evals.py`) that asserts every reported metric against its floor, so it runs as part of the existing `pytest tests/ -v` step in `ai.yml` — no new CI job. Raising a floor after a genuine improvement is a one-line edit to `baseline.yaml` in the same PR.
8. **Reindex trigger in prod:** the ai service runs ingestion once at FastAPI startup (idempotent per Decision 3, so it's cheap even when nothing changed). Because a content-only push never reaches `deploy.yml`, a new dedicated workflow (`reindex-content.yml`) triggers on pushes to `main` touching `frontend-typescript/src/content/site/**`, `docs/user-guide/**`, or `docs/PRODUCT.md`, and restarts only the `ai` container over SSH (`docker compose restart ai`) so the startup hook re-runs against fresh content. It does not rebuild images, so it's fast and doesn't race `deploy.yml`'s full rebuild.
   - *Alternative considered:* a protected `/internal/reindex` HTTP endpoint callable from CI. Rejected for now — restarting the container is simpler and the ingestion is already idempotent and fast; an endpoint can be added later if restart latency becomes a problem.
9. **`ai.yml`'s `paths-filter`** gains the same three content paths, so the eval gate (and the rest of the ai test suite) runs on content-only PRs too.

## Risks / Trade-offs

- [Guide-doc H2 chunking produces uneven chunk sizes, hurting ranking for very short or very long sections] → the golden dataset's guide-doc questions will surface this during tuning; no mitigation beyond the eval loop itself.
- [`ts_rank_cd` lexical search misses paraphrased questions that share no vocabulary with the source text] → expected and acceptable for this change (see proposal.md's embeddings follow-up); the golden dataset should still include a few such questions so the baseline honestly reflects this gap rather than hiding it.
- [Restarting the `ai` container on every content push adds a brief availability gap for that service] → acceptable; it's scoped to the `ai` container only (chat/budget/users keep serving), and restarts are fast since no image rebuild happens.
- [Unanswerable-question threshold is picked from an initial dataset and may need retuning as the dataset grows] → it lives in the committed baseline file precisely so retuning is a reviewable one-line diff, not a code change.
