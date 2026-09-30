## Why

After launch, the assistant will fail in ways the golden dataset didn't predict. This change closes the loop: production failure → review → new eval case → fix → permanent regression test. It also makes prompt or model changes a measured release decision (quality × latency × cost) instead of a config edit.

> **Status: skeleton.** The open questions below must be resolved before specs, design and tasks are written.

## What Changes

- **Feedback capture:** thumbs up/down on each answer, with optional reasons (incorrect, didn't answer, outdated, missing information, other). The stored record holds the question (redacted), retrieved IDs, answer, prompt version, model and feedback. It has a retention TTL and is purged automatically.
- **Review → dataset path:** a superuser-only way to list negative feedback and promote a record into the golden dataset as a new eval case, with its expected sources.
- **Candidate vs production comparison:** the eval harness runs two configurations (prompt version and/or model) over the same dataset. It reports groundedness, answer correctness, refusal correctness, hallucination rate, P95 latency, tokens and cost side by side.
- **LLM-as-judge:** only for semantic dimensions that code can't check (groundedness, completeness), with a pinned judge model and prompt version. Everything deterministic stays deterministic.
- **Release gates:** answer-level evals run nightly and on a PR label (they cost money and results vary run to run). A tolerance-band gate blocks promotion of a candidate prompt version or model that regresses.
- **Content reindex pipeline:** a content change triggers extract → chunk → index → retrieval evals → answer evals before the new index goes live.

## Capabilities

### New Capabilities
- `site-assistant-feedback`: capture, storage, retention and review of visitor feedback.
- `ai-release-evaluation`: candidate-vs-production comparison, judge usage rules and release gate semantics. This is written to be reusable by other AI features, not only the site assistant.

### Modified Capabilities
- `site-assistant-ui`: feedback controls on answers.
- `retrieval-evaluation`: the dataset gains production-sourced cases.

## Impact

- **Depends on:** `ai-feat-site-assistant-grounded-answers` (hard).
- **Related:** `gdpr-iso27001-priority-2`, whose `data-retention-policy` should own the feedback purge job if it has landed; otherwise this change adds its own Celery beat task and registers it in the worker's `include=[]`. Also related: `platform-chore-328-compliance-guardrails` (the PII-in-logs rule applies to stored questions).
- **ai service:** feedback model and migration, a superuser review endpoint, eval-runner extensions.
- **CI:** a new scheduled workflow for nightly answer evals, needing the platform Anthropic key as a GitHub secret.
- **Python dependencies:** none expected. Judge calls reuse `pydantic-ai`.

## Open Questions

1. **Retention period** for stored questions and feedback: 30 days to match the AI-session job, or 90 days to allow meaningful review?
2. **Redaction approach:** regex for emails, phones and names, or no raw question storage at all (store only the question embedding or a hash)?
3. **Where review happens:** inside the planned superuser admin console (`superuser-admin-console`), or a script/CLI for now?
4. **Nightly eval budget:** the maximum spend per run and per month on the platform key.
5. **Judge model:** same provider as generation (cheaper, correlated blind spots) or a different one (for example the Mistral BYOK path, which adds cost and a key)?
