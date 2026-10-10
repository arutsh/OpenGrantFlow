# Design

## Context

See proposal.md for motivation and the resolved decisions. Requirements are in `specs/site-assistant`, `specs/site-assistant-ui` and `specs/privacy-policy`. Facts from the current code that shape the approach:

- `app/services/site_retrieval.py` `retrieve(db, query, top_k, persona)` returns `RetrievedChunk`s with `content_id`, `url`, `page_title`, `heading`, `text` and `score`. The unanswerable score threshold lives in `services/ai/tests/evals/baseline.yaml` and is not yet a runtime setting.
- `app/services/rate_limiter.py` `check_and_increment` is a fixed **hourly** window keyed by `(scope, customer_id)` and **fails open** when Redis is down. Both are wrong for an anonymous, platform-funded endpoint.
- `app/services/provider.py` `build_agent` sets `agent.instrument = True`. PydanticAI's default instrumentation records message content on spans, which would put visitor questions in Grafana.
- `resolve_platform_funded_model()` hard-codes Anthropic Haiku. `OllamaAdapter.build(user_key)` reads `base_url` and `model_name` from a BYOK key row and applies the `AI_PROVIDER_APPROVED_ORIGINS` egress check.
- Prompts are seeded into `ai_prompts` by Alembic data migrations (see `010_seed_excel_extraction_prompt.py`) and loaded with `prompt_loader.load_prompt(name)`.
- The ai container runs `uvicorn --proxy-headers --forwarded-allow-ips='*'`. Caddy's `reverse_proxy` replaces any client-sent `X-Forwarded-For` with the real peer address unless `trusted_proxies` is set, and the ai port is not published publicly.

## Goals / Non-Goals

**Goals:**
- One fixed pipeline: validate → cap → verify → retrieve → generate → resolve citations. No agent tools and no loop.
- Every guarantee about URLs and citations is enforced by deterministic server code, so it is testable without an LLM.
- Moving the assistant from Anthropic to a self-hosted Ollama is a configuration change.

**Non-Goals:**
- Streaming, multi-turn memory and Turnstile (deferred; see proposal.md, Resolved Decisions).
- Changes to retrieval ranking. This change consumes `site-retrieval` as-is.
- A monthly spend counter. The global daily cap is the spend ceiling.

## Decisions

1. **Separate router, no shared auth dependency.** `app/api/site_assistant_routes.py` mounts at `/api/ai/site-assistant` with `ask` and `config`. It does not use `get_validated_user` or `get_resolved_model`. Both depend on a logged-in user, and keeping them out makes it impossible to reach tenant data from this route.
   - *Alternative:* add the route to the chat service. Rejected in proposal.md: chat is an authenticated agent host with write tools.

2. **`SiteAssistantSettings` group in `config.py`:** `SITE_ASSISTANT_ENABLED` (default `false`), `SITE_ASSISTANT_PROVIDER` (`anthropic` | `ollama`, validated at startup), `SITE_ASSISTANT_MODEL` (unset uses the provider default: Haiku for `anthropic`, `OLLAMA_MODEL` for `ollama`), `SITE_ASSISTANT_PER_IP_DAILY_CAP` and `SITE_ASSISTANT_GLOBAL_DAILY_CAP` (`int | None`; `None` uses the profile, `0` is unlimited), `SITE_ASSISTANT_MAX_QUESTION_CHARS` (500), `SITE_ASSISTANT_TOP_K` (5), `SITE_ASSISTANT_MIN_SCORE` (copied from `baseline.yaml`'s threshold), and `SITE_ASSISTANT_HUMAN_VERIFIER` (`none`).

3. **Provider cap profiles are a code constant**, `CAP_PROFILES = {"anthropic": (20, 300), "ollama": (200, None)}`. Env overrides are applied on top. A provider without a profile fails startup validation, so adding a provider forces a decision about its caps.

4. **Model resolution: `resolve_site_assistant_model()` in `provider.py`.** For `anthropic` it reuses the platform key and returns `None` if the key is missing. For `ollama` it builds a lightweight key-like object (`base_url=OLLAMA_URL`, `model_name=...`) and calls `OllamaAdapter.build`, so the egress allow-list check is the existing one, not a copy. `None` becomes a 503.
   - *Alternative:* generalise `resolve_platform_funded_model` to take a provider. Rejected: that helper backs the Excel-import fallback, and its Anthropic-only behaviour is a documented carve-out (budget-export-from-excel Decision 5).

5. **Daily, fail-closed limiter.** `rate_limiter.py` gains `check_daily_cap(scope, subject, limit)`. It is keyed `rate_limit:{scope}:{subject}:{YYYYMMDD-UTC}` with a 48-hour TTL, and `Retry-After` gives the seconds to the next UTC midnight. It **raises** on Redis errors instead of allowing the request, and the route turns that into a 503. The existing hourly `check_and_increment` keeps its fail-open behaviour for BYOK routes.
   - The per-IP subject is `hmac_sha256(ENCRYPTION_KEY, ip)[:32]`, so Redis never holds raw IPs.
   - Ordering: per-IP increment after validation; global increment only once retrieval has passed the score threshold and a model call will happen.

6. **Client IP:** `request.client.host`. Uvicorn's proxy-headers already resolve it from the `X-Forwarded-For` header Caddy sets. Group 2 adds a test showing a client-sent `X-Forwarded-For` does not change the counted address behind Caddy. No Caddyfile change is needed because Caddy overwrites the header by default.

7. **Structured output:** `SiteAnswer(answer: str, cited_chunk_ids: list[str], answerable: bool)` as the agent's `output_type`. After the run, the route keeps only IDs in the retrieved set and builds citations from the `RetrievedChunk` objects already in memory (the same rows as `site_chunks`, with no second query). If `answerable` is true and no citation survives, the response becomes the fixed unanswerable answer. Validation errors and provider exceptions return that same fixed response.

8. **Prompt and untrusted data.** The system prompt is seeded as `ai_prompts` row `site_assistant` v1 by a data migration. The user template puts each chunk inside `<site_content id="...">…</site_content>` tags, after a line saying the content is reference data and not instructions. The persona, when given, is a single line naming the reader type. The question goes last, in its own tag.

9. **Telemetry without content.** The site assistant agent is built with `InstrumentationSettings(include_content=False)` instead of `instrument = True`. The route opens a `site_assistant.ask` span with attributes `site_assistant.prompt_version`, `gen_ai.system`, `gen_ai.request.model`, `site_assistant.retrieved_ids`, `site_assistant.retrieved_scores`, `site_assistant.answerable`, `site_assistant.citation_count`, `site_assistant.question_length`, and a child span per stage. Token usage comes from PydanticAI's own `gen_ai.usage.*` attributes.

10. **Human verification hook:** a `HumanVerifier` protocol with one `NoopVerifier` implementation, picked by `SITE_ASSISTANT_HUMAN_VERIFIER`. The request schema leaves room for an optional `verification_token` field, but v1 does not accept it yet, so the 422 for unknown fields stays strict. Adding Turnstile later means adding a verifier and that one field.

11. **Frontend:** `SiteAssistantBox` in `components/site/`, shown on `pages/site/Home.tsx`. It loads `config` with React Query (`retry: false`, `staleTime` of a few minutes) and calls `ask` with a mutation. The answer renders as plain text in a `<p>`, never through `SiteMarkdown`. Browse-instead links point at the existing public routes (How it works, Security, About, guides).

12. **Evals: two tiers.** Deterministic tests use PydanticAI's `TestModel`/`FunctionModel` against a seeded corpus. They cover schema, citation-subset filtering, URL allow-listing, the short-circuit on unanswerable golden-dataset entries, a malformed-output fallback and the cap paths, and they run in `ai.yml`. The live suite, `scripts/eval_site_assistant.py`, follows `scripts/eval_prompt_injection.py`: it is opt-in, not in CI, and runs hallucination probes plus planted-injection chunks against the configured provider, reporting per category in the same shape.

## Risks / Trade-offs

- [Per-IP caps are weak against rotating-IP bots] → The global cap bounds spend; Decision 10 leaves room to add Turnstile.
- [A fail-closed limiter makes the assistant unavailable during a Redis outage] → The intended trade: the UI falls back to browse links, and the rest of the site is unaffected.
- [Lexical retrieval misses paraphrases, so some answerable questions short-circuit as unanswerable] → Accepted for v1. The visitor still gets browse links, and the embeddings follow-up from retrieval-evals covers it.
- [UTC-midnight reset lets a burst span two days] → Acceptable at these cap sizes.
- [`--forwarded-allow-ips='*'` would trust spoofed headers if the ai port were ever exposed directly] → Group 2's test documents the dependency on Caddy, and a deployment note in `docs/deployment/` says not to publish the ai port.
- [Haiku quality varies with the persona and prompt] → The live eval suite exists to catch this before the flag is turned on.

## Migration Plan

1. Merge the groups with `SITE_ASSISTANT_ENABLED=false`. The endpoint returns 404 and the Home box stays hidden.
2. Run the live eval suite against the production provider configuration.
3. Get legal sign-off on the privacy-policy wording (launch blocker; see proposal.md).
4. Set `SITE_ASSISTANT_ENABLED=true` in `.env.ai.prod` and restart `ai`.

Rollback: set the flag back to `false` and restart `ai`. Nothing else needs undoing, because the prompt migration is additive.
