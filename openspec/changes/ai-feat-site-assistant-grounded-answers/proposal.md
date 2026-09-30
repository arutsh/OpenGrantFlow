## Why

Once retrieval is measured, visitors can ask questions on the landing page and get grounded, cited answers. This is the first **anonymous, internet-facing** AI endpoint in the platform, funded by the platform's own key. Abuse resistance, output handling and grounding are therefore requirements, not polish.

> **Status: skeleton.** The open questions below must be resolved before specs, design and tasks are written.

## What Changes

- **Endpoint:** `POST /api/v1/ai/site-assistant/ask` in the ai service. It is unauthenticated and behind a feature flag (off by default, so self-hosters opt in). It follows a fixed workflow: query → retrieve (`site-retrieval`) → generate → cite. There are no tools, planner or loop. It stays deliberately separate from the chat service, which is an authenticated agent host with write tools.
- **Model:** the platform-funded Haiku path (`resolve_platform_funded_model`). The system prompt is versioned in `ai_prompts`.
- **Structured output:** `{answer, cited_chunk_ids[], answerable: bool}`. The model **never emits URLs or titles**. The server resolves citations from `site_chunks` and drops any ID that was not in the retrieved set. That makes citation correctness and URL allow-listing a deterministic check.
- **Grounding policy:** answer only from the provided context, never invent pricing, partners, endorsements, guarantees or capabilities, and state plainly when information is unavailable. Retrieved text is wrapped and labelled as untrusted data, never as instructions.
- **Abuse controls:** per-IP and global daily request caps (the existing Redis limiter with new scopes), a question length limit, and off-topic refusal. When caps are exhausted it fails closed to "browse instead" links.
- **Observability:** OTEL GenAI span attributes (prompt version, model, retrieved IDs and scores, token usage, per-stage latency). Raw question text is **not** put on spans.
- **UI:** the redesign's assistant box on Home (persona toggle, answer with source links, "browse instead" fallback).
- **Evals:** deterministic checks (schema, citation subset, allow-listed URLs, refusal on the unanswerable set), plus an opt-in live suite: hallucination probes ("revenue last year", "government endorsement", "guaranteed funding") and injection fixtures planted in a test corpus.

## Capabilities

### New Capabilities
- `site-assistant`: the ask endpoint, grounding, citation resolution, refusal and abuse-control behaviour.
- `site-assistant-ui`: the landing-page assistant box.

### Modified Capabilities
- `public-site`: Home gains the assistant box.

## Impact

- **Depends on:** `ai-feat-site-assistant-retrieval-evals` (hard), `frontend-feat-public-site-content` (hard, via Home).
- **Related:** `chat-fix-prompt-injection-provenance` (same untrusted-data principle and eval layout); `ai-fix-361-provider-ssrf` (egress policy must permit the platform Anthropic origin).
- **Gateway:** covered by the existing `/api/v1/ai/` routes in `nginx.conf`, `nginx-dev.conf` and the Caddyfile. The per-IP limit needs a trusted `X-Forwarded-For` from Caddy.
- **Python dependencies:** none new expected (`pydantic-ai-slim[anthropic]` is already present).
- **Docs:** `docs/security/subprocessors.md`: visitor questions go to Anthropic. The privacy policy needs a line about the assistant.

## Open Questions

1. **Cap values:** per-IP per day, global per day, and a monthly spend ceiling. What is the maximum acceptable monthly cost?
2. **Bot protection:** is Cloudflare Turnstile (or similar) required from day one, or are caps enough until abuse shows up?
3. **Streaming:** is a non-streaming response acceptable for v1? Structured output with citations is simpler without streaming.
4. **Conversation memory:** single-turn only (recommended for v1), or short follow-ups?
5. **Legal copy:** does the privacy policy wording need review before launch, given that anonymous questions are sent to a US subprocessor?
