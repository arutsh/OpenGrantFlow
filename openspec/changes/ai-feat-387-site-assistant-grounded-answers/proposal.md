## Why

Once retrieval is measured, visitors can ask questions on the landing page and get grounded, cited answers. This is the first **anonymous, internet-facing** AI endpoint in the platform, funded by the platform's own key. Abuse resistance, output handling and grounding are therefore requirements, not polish.

## What Changes

- **Endpoint:** `POST /api/v1/ai/site-assistant/ask` in the ai service. It is unauthenticated and behind a feature flag (off by default, so self-hosters opt in). It follows a fixed workflow: query → retrieve (`site-retrieval`) → generate → cite. There are no tools, planner or loop. Single-turn and non-streaming: one question in, one JSON response out, with no conversation memory. It stays deliberately separate from the chat service, which is an authenticated agent host with write tools.
- **Model:** set by `SITE_ASSISTANT_PROVIDER` / `SITE_ASSISTANT_MODEL`, defaulting to `anthropic` and Haiku with the platform's own key. `ollama` is supported so an operator can serve answers from their own hardware, and it goes through the `ai-fix-361-provider-ssrf` egress allow-list. The system prompt is versioned in `ai_prompts`.
- **Structured output:** `{answer, cited_chunk_ids[], answerable: bool}`. The model **never emits URLs or titles**. The server resolves citations from `site_chunks` and drops any ID that was not in the retrieved set. That makes citation correctness and URL allow-listing a deterministic check.
- **Grounding policy:** answer only from the provided context, never invent pricing, partners, endorsements, guarantees or capabilities, and state plainly when information is unavailable. Retrieved text is wrapped and labelled as untrusted data, never as instructions.
- **Abuse controls:** a per-IP daily cap and a global daily cap from a **per-provider cap profile**, using the existing Redis limiter with new scopes. Defaults: `anthropic` 20 per IP and 300 global per day; `ollama` 200 per IP and no global cap. Env vars override each value; unset uses the profile default, and `0` means unlimited. The global cap is the spend ceiling: on Haiku, 300 a day is roughly $30–45 a month at worst. Also a question length limit and off-topic refusal. When a cap is exhausted, it fails closed to "browse instead" links. **Bot protection** (e.g. Cloudflare Turnstile) is deferred: the pipeline has a `verify_human()` step that does nothing by default, so it can be added later through config.
- **Observability:** OTEL GenAI span attributes (prompt version, model, retrieved IDs and scores, token usage, per-stage latency). Raw question text is **not** put on spans.
- **UI:** the redesign's assistant box on Home (persona toggle, answer with source links, "browse instead" fallback).
- **Evals:** deterministic checks (schema, citation subset, allow-listed URLs, refusal on the unanswerable set), plus an opt-in live suite: hallucination probes ("revenue last year", "government endorsement", "guaranteed funding") and injection fixtures planted in a test corpus.

## Capabilities

### New Capabilities
- `site-assistant`: the ask endpoint, grounding, citation resolution, refusal and abuse-control behaviour.
- `site-assistant-ui`: the landing-page assistant box.

### Modified Capabilities
- `privacy-policy`: the processors section discloses that visitor questions go to Anthropic.

The Home placement lives in `site-assistant-ui`, because `public-site` is still a delta in the unarchived `frontend-feat-372-public-site-content` change.

## Impact

- **Depends on:** `ai-feat-380-site-assistant-retrieval-evals` (hard), `frontend-feat-372-public-site-content` (hard, via Home).
- **Related:** `chat-fix-prompt-injection-provenance` (same untrusted-data principle and eval layout); `ai-fix-361-provider-ssrf` (egress policy must permit the platform Anthropic origin).
- **Gateway:** covered by the existing `/api/v1/ai/` routes in `nginx.conf`, `nginx-dev.conf` and the Caddyfile. The per-IP limit needs a trusted `X-Forwarded-For` from Caddy.
- **Python dependencies:** none new expected (`pydantic-ai-slim[anthropic]` is already present).
- **Docs:** `docs/security/subprocessors.md`: visitor questions go to Anthropic. The privacy policy needs a line about the assistant. That wording needs legal review before the feature flag is turned on in production. This blocks launch, not implementation.

## Resolved Decisions

1. **Caps:** per-provider profiles (`anthropic` 20 per IP and 300 global per day; `ollama` 200 per IP, no global cap), each overridable by env. Cost follows the model, so caps do too.
2. **Bot protection:** deferred; caps bound the worst case, and a no-op `verify_human()` hook leaves room for Turnstile.
3. **Streaming:** none in v1; citations are validated server-side before anything reaches the visitor.
4. **Conversation memory:** single-turn only; follow-ups add injection surface and cost, and the evals measure single questions.
5. **Legal copy:** privacy-policy review is a launch blocker (gates enabling the flag in production), not an implementation blocker.
