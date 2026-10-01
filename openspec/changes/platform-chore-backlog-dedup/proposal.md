# Proposal

## Why

Work gets tracked, but nothing checks for overlap before new work is filed.
New proposals and issues are written without a required look at open changes
and issues, so the same problem can be raised twice. Deferred code-review
findings currently live outside GitHub (in agent memory), where only one tool
can see them and nothing links them to the PR that produced them.

## What Changes

- **Triage rule** documented in `docs/development/WORKFLOW.md`: an OpenSpec
  change only when work alters required behavior, spans services, or needs a
  design decision; otherwise a plain issue. Every piece of work has an issue;
  changes are the heavier path, not the only path.
- **Service labels**: `svc:<service>` for each key in `flow.py`'s `SERVICES`,
  plus `review-followup`, created by a new idempotent `flow.py labels`
  subcommand and applied automatically by `init`, `sync`, `issue` and `defer`.
  `issue` gains a required `--service`.
- **Related-work search**: new read-only `flow.py related "<text>"` lists open
  issues and in-flight changes that match the text.
  - `issue` and `defer` run it first. If there are matches, they ask y/N; when
    no terminal is attached, they refuse unless `--force` is passed.
  - `init` runs it as a warning only.
- **Proposal rule** in `openspec/config.yaml`: before drafting, run
  `flow.py related`, and end every proposal with a `## Related` section that
  classifies each overlap (absorbs / depends on / supersedes / independent).
- **Absorbed issues**: tasks.md groups may carry an `Absorbs: #n, #m` line.
  `flow.py pr` emits `Closes #n` for each one. A tasks rule links this to the
  proposal's Related section.
- **Deferred review findings**: new
  `flow.py defer "<title>" --pr N [--file path:line] [--comment URL]` creates a
  `review-followup` issue in Backlog. It is deliberately *not* a sub-issue, so it
  never blocks the parent's `Closes`. It prints a `Deferred: #n` line for the PR
  body. Fixed findings stay as PR review comments.

## Related

- `openspec list`: no in-flight change touches `scripts/flow.py` or the
  workflow docs. **Independent.**
- Issue #320 (flow workflow rework): built the current `init`/`sync`/`start`/`pr`
  flow. This change **depends on** it (it extends that tool) and does not reopen
  its scope.

## Capabilities

### New Capabilities

None. This is developer tooling and process; no product behavior changes, so
the change sets `skip_specs: true`.

### Modified Capabilities

None.

## Impact

- `scripts/flow.py`, `scripts/test_flow.py`
- `openspec/config.yaml` (proposal and tasks rules)
- `docs/development/WORKFLOW.md`, `CLAUDE.md` (flow section pointer)
- GitHub repo labels (new `svc:*` and `review-followup`); a one-off backfill
  labels the existing open issues
- After merge, review backlogs held only in agent memory move to
  `review-followup` issues
