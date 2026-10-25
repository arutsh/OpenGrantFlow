# Design

## Context

See proposal.md for motivation; requirements are in `specs/ai-release-evaluation`. Facts from the current code that shape the approach:

- `services/ai/scripts/eval_site_assistant.py` runs the probe set against the configured provider and prints `format_report` from `tests/evals/site_assistant_eval.py`. It patches `site_assistant.retrieve` and `resolve_citations` to see raw output. It doesn't measure tokens, latency or cost, and doesn't run the golden dataset.
- `site_assistant._generate` reads `result.usage` only to set span attributes; `ask()` returns `AskResponse` with no usage.
- Production generation is pinned: `provider._PLATFORM_FUNDED_MODEL = "claude-haiku-4-5-20251001"`, overridable by `SITE_ASSISTANT_MODEL`.
- Prompts are seeded by Alembic data migrations. `020_seed_site_assistant_prompt.py` defines `SITE_ASSISTANT_SYSTEM_PROMPT` and `SITE_ASSISTANT_USER_TEMPLATE` as module constants, but the version `'v1'` is a literal inside the SQL. `seeded_prompt()` loads that one file by path.
- The golden dataset (`tests/evals/data/golden_dataset.yaml`, 58 entries) has `expected_content_ids`, `category` and `answerable`, but no reference answers. The probe set has 14 probes.
- `.github/workflows/ai.yml` already runs `pytest tests/` with Postgres (including retrieval and deterministic site-assistant evals) on PRs touching site content. `reindex-content.yml` runs on push to `main` and restarts the ai service with no checks. `deploy.yml` ignores content-only pushes.
- The repo already holds the platform key as the `ANTHROPIC_API_KEY` Actions secret (used by `deploy.yml`).
- `pydantic-ai-slim==2.1.0` provides `WrapperModel` and per-request `RequestUsage`.

## Goals / Non-Goals

**Goals:**
- No production code path changes. All measurement lives in the eval runner and `tests/evals/`.
- A labelled run costs about $0.40 on Haiku (about 60 generation calls plus about 40 judge calls), so two runs fit the $1 month.
- Everything except the model and judge calls is unit-testable with scripted models.

**Non-Goals:**
- Reference-answer correctness. There are no reference answers. Correctness is covered by citation hit rate plus judge completeness.
- Making the answer-eval check a required GitHub status check. It only runs on label; the free baseline-identity test is what forces a re-measure.
- Gating `deploy.yml`. A push changing both backend code and content still ingests content on deploy without the content gate. That's an existing path, left as is.
- Multiple runs per question or statistical significance tests. The budget allows one pass; the tolerance band absorbs noise.

## Decisions

1. **Library in `tests/evals/answer_eval.py`, CLI in `scripts/eval_site_assistant.py`.**
   - Metrics, cost, caps, gate and baseline I/O are pure functions in the library and tested in the free suite.
   - The script becomes subcommands: `run` (optionally `--gate`, `--write-baseline`, `--result <path>`) and `compare --candidate-model/--candidate-prompt`.
   - The existing probe checks (`answer_violations`, `model_violations`) are reused unchanged.
   - *Alternative:* a new script. Rejected: the probe runner already has the patched pipeline.

2. **Usage and latency through an eval-only `WrapperModel`.** The runner wraps `resolved.model` in a `MeteredModel(WrapperModel)` that records each request's `RequestUsage` and wall-clock duration into a ledger the runner owns. The judge model is wrapped the same way.
   - *Alternative:* make `ask()` return usage. Rejected: it changes the production API for a test need.

3. **Prompt versions discovered from migrations.**
   - Task: add a module constant `PROMPT_VERSION = "v1"` to migration 020 and use it as the SQL bind value. The applied SQL is identical, so no new revision is needed.
   - A site-assistant prompt migration is any module defining `SITE_ASSISTANT_SYSTEM_PROMPT`, `SITE_ASSISTANT_USER_TEMPLATE` and `PROMPT_VERSION`.
   - The **production prompt** is the one from the highest-numbered such migration. Migrations are append-only, so older versions stay loadable.
   - `compare` loads production by the baseline's recorded version and the candidate by `--candidate-prompt <version>`.
   - *Alternative:* move prompts to standalone versioned files. Rejected: it duplicates what migrations already seed into `ai_prompts`.

4. **Two committed files: hand-edited config vs machine-written baseline.**
   - `tests/evals/data/answer_eval.yaml` holds:
     - the per-run cap ($0.50) and the monthly cap ($1.00)
     - tolerances (0.05 each)
     - the judge model (`claude-haiku-4-5-20251001`) and judge prompt version
     - the default tokens per question for the first estimate
     - the price table (USD per million input and output tokens, with an `as_of` date)
   - `tests/evals/answer_baseline.yaml` is written only by `run --write-baseline` from a complete run. It records:
     - configuration and judge identity
     - the dataset fingerprint (SHA-256 of the golden and probe files)
     - every metric overall and per category
     - average tokens per model-reaching question
   - *Alternative:* one file. Rejected: `yaml.safe_dump` drops the hand-written comments.

5. **The gate compares against the committed baseline, not a live production run.** A labelled run measures one configuration, which halves cost.
   - The free test `test_answer_baseline_matches_runtime_config` asserts:
     - baseline model == `SITE_ASSISTANT_MODEL or _PLATFORM_FUNDED_MODEL` (with the CI default env)
     - baseline prompt version == the production prompt version

     It mirrors the existing `test_runtime_threshold_matches_retrieval_baseline`.
   - A PR changing either must therefore commit a new baseline. Producing one honestly means running the eval, and the labelled CI run shows the gate result against the previous baseline in the job summary.
   - *Alternative:* run production and candidate live on every labelled PR. Rejected on cost.

6. **Judge design.**
   - The judge prompt lives in `tests/evals/data/judge_prompt.yaml` (version, system, user template). It wraps `<question>`, `<answer>` and each cited `<site_content id=...>` as data, applying the same `<`/`>` escaping the site-assistant user template applies to the question.
   - Output type is `JudgeVerdict(grounded: bool, complete: bool, reason: str)`, built with `build_agent` at temperature 0.
   - A validation failure or provider error is recorded as a judge error.
   - The judge model name must match `-\d{8}$` (dated) or the run refuses to start.
   - The same provider as generation is an accepted trade-off (see Risks).

7. **Cost cap mechanics.**
   - The estimate is (questions that reach the model, found by running retrieval first, which is free) × baseline tokens per question × price, plus the judge share.
   - The runner checks running cost after every call and stops at the cap.
   - An incomplete run sets `complete: false` in its result; `--gate` and `--write-baseline` both refuse it.

8. **Monthly ledger as workflow artifacts.**
   - Every CI run that made a call uploads `eval-cost.json` (cost and timestamp) as an artifact, under `if: always()`.
   - A pre-step lists this month's runs of the workflow (`gh run list --workflow answer-evals.yml --created ">=YYYY-MM-01"`), downloads their cost artifacts, sums them, and passes `--month-spent` to the runner, which applies the monthly cap.
   - Needs `actions: read`. Artifacts are retained 90 days, longer than a month.
   - Local runs use the developer's own key and the per-run cap only.
   - *Alternatives:* a committed ledger (CI can't commit), or a repo variable (needs a PAT with variables write).

9. **Trigger:** a `pull_request` `types: [labeled]` job runs only when `github.event.label.name == 'answer-evals'`, plus `workflow_dispatch`.
   - `synchronize` is not listed, so later pushes don't spend.
   - To re-run, remove and re-add the label.
   - Same-repo branches get secrets on `pull_request`; `pull_request_target` is not used.

10. **Reindex gate inside `reindex-content.yml`.** A new `content-evals` job (Postgres service, `pytest tests/evals -v`) runs first, and `reindex` gets `needs: content-evals`.
    - *Alternative:* `workflow_run` after "AI Service CI". Rejected: that workflow also runs for non-content pushes and on `develop`, and its path filter isn't visible to the follower.

## Risks / Trade-offs

- **[Haiku judging Haiku shares blind spots]** → The judge model is one config line. The design allows a different provider once `ai-feat-364-mistral-provider` lands. Judging stays limited to two binary checks.
- **[About 45 judged answers is a small sample: one question is about 2.2 points]** → A 0.05 tolerance allows about two questions of drift. Served violations have zero tolerance because they are deterministic. If gates flap, widen the tolerance in `answer_eval.yaml` rather than adding runs.
- **[Price table goes stale]** → It carries an `as_of` date, and unknown models refuse to run. Recommend also setting a workspace spend limit in the Anthropic console as a backstop outside the repo.
- **[A hand-edited baseline could bypass the gate]** → It's a single-maintainer repo. The baseline records its run timestamp and the labelled run's summary is visible on the PR. Accepted.
- **[Eval spend shares the production key's account limits]** → Two capped runs a month are far below the assistant's own daily caps.
- **[Content gate adds about 2 minutes before a content change goes live]** → Acceptable; content is not time-critical.

## Migration Plan

Group 4 writes the first `answer_baseline.yaml` from one live run (about $0.40, by hand) in the same PR that adds the identity test, so `main` never has the test without a baseline. Rollback is reverting the workflow files; nothing touches the production database or API.
