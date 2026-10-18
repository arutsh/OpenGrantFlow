# Proposal

## Why

Prompt, model and content changes to the site assistant go live without any measurement of answer quality: a prompt or model swap is a config edit, and a content push restarts the ai service with an un-evaluated index. This change makes each of those a measured release decision, within a budget that fits a site with no real users yet.

## What Changes

- **Candidate vs production comparison:** the eval runner runs two configurations (prompt version and/or model) over the same golden dataset and probe set. It reports groundedness, answer correctness, refusal correctness, hallucination rate, P95 latency, tokens and cost side by side.
- **LLM-as-judge, semantic checks only:** groundedness and completeness are scored by an Anthropic judge with a pinned, dated model and a versioned judge prompt. Everything code can check (citations, links, refusals, injection) stays deterministic.
- **On-change runs only, no schedule:** answer evals run when a PR carries an eval label, or by hand. There is no nightly or periodic run until real traffic produces new cases; a schedule stays a disabled config switch. Pinned model versions remove the drift a schedule would catch.
- **Spend caps:** the runner computes cost from actual token counts, aborts a run whose estimate exceeds the per-run cap, and refuses to start when the month's recorded spend would exceed the monthly cap (default $1/month).
- **Committed answer baseline and release gate:** production's last measured results are committed with the configuration they came from (model, prompt version, judge version). A gated run measures only the branch's configuration and compares it to that baseline, so it pays for one configuration, not two. A tolerance band per metric fails a regression. A free CI test fails any PR whose model or prompt no longer matches the baseline's configuration, so promoting a change requires a fresh measured baseline.
- **Gated content reindex:** `reindex-content.yml` runs the free checks (retrieval evals and the deterministic injection tests) against the new content before restarting the ai service, and stops the deploy on failure. Paid answer evals are not part of this path.

## Capabilities

### New Capabilities
- `ai-release-evaluation`: candidate-vs-production comparison, judge usage rules, spend caps, gate semantics and the content reindex gate. Written to be reusable by other AI features, not only the site assistant.

### Modified Capabilities
None.

## Impact

- **ai service:** extensions to `scripts/eval_site_assistant.py` and `tests/evals/` (second configuration, judge, cost accounting, comparison report). No runtime API change.
- **CI:** a label-triggered answer-eval workflow, needing the platform Anthropic key as a GitHub secret; `reindex-content.yml` gains an eval step before the restart.
- **Spend tracking:** each CI run records its cost as a workflow artifact, so the monthly cap holds across runs.
- **New committed file:** an answer baseline next to the retrieval baseline.
- **Python dependencies:** none expected. Judge calls reuse `pydantic-ai`.
- **Followed by:** `ai-feat-site-assistant-feedback`, which feeds production-sourced cases into the dataset this change evaluates against.
