## Why

The site assistant must answer from Open Grant Flow's own pages. Answer quality can't exceed what retrieval returns, so retrieval is built and measured on its own, before any LLM is involved. This change adds ingestion, lexical retrieval and a deterministic evaluation harness that gates CI. Retrieval regressions then become test failures instead of subjective impressions.

## What Changes

- **Ingestion:** reads the `site-content` section files (published only) plus `docs/user-guide/*.md` and `docs/PRODUCT.md`. It writes one row per section into a new `site_chunks` table in the ai database with `content_id`, `url`, `page_title`, `heading`, `personas`, `text`, `content_version`, and a generated `tsvector`. Guide docs have no frontmatter, so their chunks are split by H2 heading and published at `/guides/<slug>` (extending `public-site`) so each chunk cites a real public URL.
- **Retrieval:** Postgres full-text search ranked with `ts_rank_cd`. There is an optional persona boost (grantee / funder / technical, matching the redesign's toggle). No LLM and no embeddings.
- **Golden dataset:** about 50 realistic questions, authored by the user, each with its expected `content_id`(s), tagged by persona and category, including unanswerable questions that expect no confident match.
- **Eval harness:** reports Recall@1/3/5 and MRR per category, plus unanswerable-question accuracy via a retrieval-score threshold (below threshold = correctly flagged unanswerable). It includes a **full-context baseline**: how many tokens the whole corpus costs versus top-k, so retrieval has to justify itself.
- **CI gate:** retrieval evals run on every PR that touches content, the retriever or the dataset. The build fails when a metric drops below a committed absolute floor per metric (e.g. Recall@3 ≥ 0.9).
- **Reindexing:** the ai service reindexes on startup; a dedicated GitHub Actions workflow triggered on content paths also reindexes/redeploys, since `deploy.yml` currently ignores `**/*.md`, `docs/**` and `frontend-typescript/**` and a content-only merge would otherwise never reach prod.
- **Embeddings / hybrid search:** designed in as a later experiment inside this harness (a sibling `chunk_embeddings(chunk_id, embedding_model, embedding)` table so models can be compared side by side), not built here.

## Capabilities

### New Capabilities
- `site-knowledge-index`: ingestion contract, chunk provenance and index freshness.
- `site-retrieval`: query → ranked sections, with persona boost.
- `retrieval-evaluation`: golden dataset format, metrics, baseline file and CI gate semantics.

### Modified Capabilities
(none expected)

## Impact

- **Depends on:** `frontend-feat-public-site-content` (hard; it is the content contract).
- **Extends:** `public-site` with new `/guides/<slug>` public routes for guide docs, so guide chunks have a citable URL.
- **Related:** `chat-fix-prompt-injection-provenance`, whose opt-in live-eval layout should be reused so there is one eval-harness shape across the repo.
- **ai service:** new `site_chunks` model and Alembic migration, an ingestion command run on startup, a retrieval service, and `tests/evals/`. `Dockerfile` must `COPY` the content and docs directories.
- **Python dependencies:** `pyyaml` (frontmatter). No vector dependency yet.
- **Infra:** none for lexical search. The later `pgvector/pgvector:pg15` image swap is recorded, not done.
- **CI:** `ai.yml` already runs Postgres, so retrieval evals need no new service. The workflow needs path triggers for `frontend-typescript/src/content/site/**`, `docs/user-guide/**` and `docs/PRODUCT.md`.
- **Deploy:** new/updated workflow to reindex on content-path changes, since `deploy.yml` doesn't trigger on those paths today.
