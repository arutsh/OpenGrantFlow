# Tasks

Workflow rule: one task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

## 1. Gated content reindex

- [ ] 1.0 Run `scripts/flow.py start ai-feat-site-assistant-release-gates 1` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 1.1 Add a `content-evals` job to `.github/workflows/reindex-content.yml` (Postgres 15 service, Python 3.11, `pip install -r services/ai/requirements.txt`, the same env as `ai.yml`'s `ai-test`, `python -m pytest tests/evals -v` in `services/ai`), and add `needs: content-evals` to `reindex` (design.md Decision 10); verify with `actionlint` (or a YAML parse) that `reindex` depends on `content-evals`.
- [ ] 1.2 Run `actionlint` on the workflow clean; PR merged. Then, on the first content push to `main` after merge (the workflow file itself is outside the path filter), confirm in Actions that `content-evals` ran and `reindex` waited for it, and link that run in the sub-issue.

## 2. Answer eval runner with cost caps — ticket depends on none (independent of 1)

- [ ] 2.0 Run `scripts/flow.py start ai-feat-site-assistant-release-gates 2` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 2.1 Add `PROMPT_VERSION = "v1"` to `migrations/versions/020_seed_site_assistant_prompt.py` and bind it in the INSERT instead of the `'v1'` literal (design.md Decision 3). Generalise `seeded_prompt()` to discover site-assistant prompt migrations and load the production one or a named version. Verify with unit tests: production resolves to v1, an unknown version raises, and `alembic upgrade head` on a scratch DB still seeds `site_assistant` v1.
- [ ] 2.2 Add `tests/evals/data/answer_eval.yaml` (caps, tolerances, judge model and prompt version, default tokens per question, price table with `as_of`) per design.md Decision 4. Check the Haiku 4.5 per-token prices against Anthropic's current pricing page when filling the table. Add a loader that fails on a missing field or an undated judge model; verify with unit tests for both failures.
- [ ] 2.3 Add `MeteredModel` (a `WrapperModel` recording per-request usage and duration) and cost computation from the price table to `tests/evals/answer_eval.py` (design.md Decision 2); verify with a `FunctionModel`-backed test that usage is recorded per call and that an unpriced model raises before any request.
- [ ] 2.4 Implement the deterministic metrics (answer rate, refusal accuracy, citation hit rate, probe model-violation rate, probe served violations, P95 latency, tokens, cost), overall and per category, as pure functions over per-question results; verify with unit tests on hand-built results, including the two `Deterministic answer metrics` spec scenarios.
- [ ] 2.5 Implement the pre-run estimate and the running per-run cap: retrieval runs first to count model-reaching questions, the run refuses to start when the estimate exceeds the cap, and it stops and marks itself `complete: false` when actual cost reaches the cap (design.md Decision 7); verify with scripted-model tests for "estimate over cap" and "cap reached mid-run".
- [ ] 2.6 Rework `scripts/eval_site_assistant.py` into a `run` subcommand covering the golden dataset and probe set, writing `--result <json>` (configuration identity, dataset fingerprint, metrics, `complete`) and printing the report; verify with a Postgres-backed scripted-model test that the result file has every field and that short-circuited questions make no model call.
- [ ] 2.7 Run `pytest tests/` (with `AI_TEST_POSTGRES_URL`) and `black --check ./app`, `mypy ./app`, `flake8 ./app --max-line-length=100` in `services/ai` clean; PR merged.

## 3. Groundedness and completeness judge — ticket depends on 2

- [ ] 3.0 Run `scripts/flow.py start ai-feat-site-assistant-release-gates 3` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 3.1 Add `tests/evals/data/judge_prompt.yaml` (version, system prompt, user template wrapping question, answer and cited content as escaped delimited data) per design.md Decision 6; verify with a unit test that a rendered prompt containing `</answer>` or `<system>` in the answer keeps the tags balanced.
- [ ] 3.2 Add the judge (`JudgeVerdict` output, temperature 0, `MeteredModel`-wrapped, run only on served answers to answerable entries) and the groundedness and completeness rates plus judge-error count; verify with scripted-judge tests: refusals get no judge call, malformed judge output counts as a judge error and is excluded from the rates, and judge cost counts toward the run cap.
- [ ] 3.3 Include judge cost in the pre-run estimate and the judge identity in the result file; verify with a unit test that the estimate grows with the number of expected answered entries.
- [ ] 3.4 Run one live `run` locally with the platform key (expect about $0.40), record the report in the PR description, and confirm the reported cost is under the per-run cap.
- [ ] 3.5 Run `pytest tests/` and the `services/ai` lint (flake8 at 100) clean; PR merged.

## 4. Answer baseline, release gate and comparison — ticket depends on 3

- [ ] 4.0 Run `scripts/flow.py start ai-feat-site-assistant-release-gates 4` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 4.1 Implement baseline write and read (`run --write-baseline` writes `tests/evals/answer_baseline.yaml` only from a complete run; tokens per question feed the next estimate); verify with unit tests that an incomplete result is refused and leaves the file unchanged.
- [ ] 4.2 Implement the gate (`run --gate`): zero-tolerance served violations, tolerance bands from `answer_eval.yaml`, a failure on an incomplete run or a dataset-fingerprint mismatch, latency, tokens and cost report-only, and a per-metric table with baseline, tolerance and pass or fail; verify with unit tests for the three `Release gate with tolerance band` spec scenarios.
- [ ] 4.3 Implement `compare --candidate-model/--candidate-prompt`: production loaded by the baseline's prompt version, both runs under one combined cap, side-by-side report with differences; verify with a scripted-model test that the report has both columns and that a combined estimate over the cap refuses to start.
- [ ] 4.4 Add `test_answer_baseline_matches_runtime_config` to the free suite (design.md Decision 5); verify it fails when the baseline's model or prompt version is edited and passes when restored.
- [ ] 4.5 Write the first `answer_baseline.yaml` from one live complete run (about $0.40) and commit it in this PR; verify the identity test passes and `run --gate` against it passes locally.
- [ ] 4.6 Run `pytest tests/` and the `services/ai` lint (flake8 at 100) clean; PR merged.

## 5. Label-triggered CI answer evals with monthly cap — ticket depends on 4

- [ ] 5.0 Run `scripts/flow.py start ai-feat-site-assistant-release-gates 5` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 5.1 Create the `answer-evals` label (`gh label create answer-evals --description "Run paid site-assistant answer evals"`); verify it appears in `gh label list`.
- [ ] 5.2 Add `.github/workflows/answer-evals.yml`: `pull_request: types: [labeled]` gated on `github.event.label.name == 'answer-evals'` plus `workflow_dispatch`, no `schedule`, `permissions: {contents: read, actions: read}`, Postgres service, the `ANTHROPIC_API_KEY` secret, and `run --gate --result` with the report in the job summary (design.md Decision 9); verify with `actionlint` and a check that the file has no `schedule` and no `synchronize`.
- [ ] 5.3 Add the monthly ledger: a pre-step that sums this month's `eval-cost.json` artifacts via `gh run list`/`gh run download` into `--month-spent`; the runner refuses when spent plus estimate exceeds the monthly cap; an `if: always()` step uploads `eval-cost.json` whenever a call was made (design.md Decision 8). Verify the runner's monthly check with unit tests ("month already spent", "failed run still counts" through the cost file written on gate failure).
- [ ] 5.4 Add `services/ai/tests/evals/README.md` covering free vs paid evals, the label, both caps, how to promote a prompt or model change (run, write baseline, label the PR), and why there is no schedule; verify the commands in it run as written.
- [ ] 5.5 Verify end to end on this PR: add the `answer-evals` label once, confirm one run starts, the gate passes against the baseline, the job summary shows the table and cost, and the cost artifact is uploaded. Push a commit afterwards and confirm no new paid run starts.
- [ ] 5.6 Run `actionlint` on the new workflow and `pytest tests/` in `services/ai` clean; PR merged.
