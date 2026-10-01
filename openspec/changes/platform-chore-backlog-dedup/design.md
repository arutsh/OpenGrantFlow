# Design

## Context

`scripts/flow.py` already owns every GitHub write in the workflow. All shell
calls go through `run()`, which skips mutating calls on `--dry-run`, and
`gh_json()`. Issues are created in one place, `create_issue(title, body)`, which
`init`, `sync` (via `reconcile`) and `issue` share. Groups are parsed by
`parse_groups()`, and `cmd_pr()` builds the `Closes` trailer. Tests in
`scripts/test_flow.py` monkeypatch `run`/`gh_json` and use `tmp_path` change
fixtures. The repo has only GitHub's default labels.

See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- A duplicate check at the point where each new ticket is created: proposal,
  `init`, `issue`, `defer`.
- A single path for deferred review findings, from the PR to the board.
- Every new change keeps working with the existing `init`/`sync`/`start`/`pr`
  flow unchanged.

**Non-Goals:**
- Exact or semantic duplicate detection. The search is keyword-based and
  advisory; a human or agent decides.
- Searching closed issues or archived changes. The check is about open work.
- Severity labels. Priority stays on the board and in `.openspec.yaml`.
- Automating the one-off label backfill or the migration of memory backlogs.

## Decisions

### D1. Label names: `svc:<key>` from `SERVICES`

The labels are derived from the `SERVICES` map, so one list drives change names,
branch names and labels. The `svc:` prefix keeps them apart from GitHub's
default `bug`/`enhancement` labels. `flow.py labels` runs
`gh label create <name> --force`, which creates or updates the label and so is
idempotent.

*Alternative:* `area:<key>`. Equivalent; `svc` matches the "service" vocabulary
the workflow docs already use.

### D2. `create_issue(title, body, labels)` is the only place labels are applied

It passes one `--label` per entry.
- `init` and `reconcile` pass `svc:<change.service>`.
- `issue` passes `svc:<--service>`.
- `defer` passes `svc:<service>` plus `review-followup`.

Putting it in the shared function means no path can create an unlabeled
ticket.

`--service` on `issue` is required and validated against `SERVICES`. An
optional flag would let unlabeled issues back in, and search by service would
quietly miss them.

### D3. `find_related(text)`: keyword search over two sources

- **Keywords:** lowercase the words of `text`, drop a small stopword set and
  words shorter than 4 characters, de-duplicate, and keep at most 6.
- **Issues:** `gh issue list --state open --search "<kw…> in:title,body"
  --json number,title,labels --limit 15`. GitHub's search treats the terms as
  AND, so this runs as one query per keyword pair (at most 3 queries), merged by
  issue number. That keeps recall reasonable without spamming the API.
- **Changes:** scan `openspec/changes/*/proposal.md`, excluding `archive/`.
  Score = keyword hits in the change name plus hits in the proposal text. Keep
  changes with score ≥ 2.
- **Output:** issues and changes ranked by hits, capped at 10, each printed as
  `#n title [labels]` or `change <name>`.

*Alternative:* embeddings or LLM similarity. Rejected, because it adds a
dependency and a network cost to a CLI tool, and keyword recall is enough for a
single-maintainer backlog.

### D4. Gate behavior

`issue` and `defer` call `confirm_no_duplicate(text, force)`:
- no matches → continue
- matches and `--force` → print them and continue
- matches and a terminal → print them and ask y/N (default No)
- matches and no terminal → print them and `die()` telling the caller to
  re-run with `--force`. Agents run without a terminal, so an agent has to act
  on the list rather than skip past it.
- `--dry-run` → print the matches and stop before any mutating call

`init` only warns. The proposal's Related section has already done the real
check, and `init` must stay non-interactive.

`related` is read-only and always exits 0.

### D5. `Absorbs:` line in tasks.md

The format is `Absorbs: #12, #34` on the line directly under a
`## N.` heading. `parse_groups` reads it into `Group.absorbs: list[int]` and
ignores it anywhere else. `cmd_pr` adds `Closes #n` for each absorbed issue of
the current group, before the parent's `Closes`. `sync` leaves the line alone.

The data lives in tasks.md, not on GitHub, because tasks.md is already what
`pr` reads, and it keeps the link reviewable in the change itself.

### D6. `defer` creates related issues, not sub-issues

A sub-issue would keep the parent open until the deferred finding is fixed,
which defeats the purpose of deferring it. Linking is done by mentioning the PR
in the issue body ("From review of #N"), which GitHub turns into a
cross-reference on both sides.

The service comes from the current branch's first segment (matched
case-insensitively against `SERVICES`). If the branch doesn't conform,
`--service` is required.

The issue goes on the board as **Backlog**, so it doesn't compete with Todo work.

The body template:

```
From review of #<pr>[ — <comment URL>]

**Location:** `<path:line>`   (omitted if not given)

**Finding:** <body arg or "TODO: describe">

**Why deferred:** TODO
```

### D7. Proposal and tasks rules live in `openspec/config.yaml`

The rules are injected into every artifact generation, which makes them the
one enforcement point that covers AI-authored proposals. The rules refer to
`flow.py related` rather than raw `gh` commands, so the search logic lives in
one place.

## Risks / Trade-offs

- [Keyword search misses a rephrased duplicate] → It's advisory; the monthly
  grooming pass still catches the rest. Tune the stopwords and thresholds only
  if misses show up in practice.
- [Noisy matches train users to always pass `--force`] → The change-score
  threshold (≥ 2) and the 10-result cap keep the list short. Revisit if
  `--force` becomes a reflex.
- [Extra `gh` calls slow `issue`/`defer`] → At most 3 search calls, only
  on commands that create tickets.
- [Existing open issues have no `svc:` label, so `related` misses nothing but
  label filtering does] → A one-off backfill as part of group 1.

## Migration Plan

1. Group 1 merges → run `flow.py labels` once, then backfill labels on open
   issues.
2. Group 3 merges → move the review backlogs held only in agent memory into
   issues with `flow.py defer --force`, then trim those memory entries to issue
   pointers.

Rollback: revert the commits. The labels and issues created along the way are
harmless to leave.
