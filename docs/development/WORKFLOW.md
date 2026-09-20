# OpenSpec → Issue → Branch Workflow

How a piece of work moves from an OpenSpec change to merged code, and how the
naming stays consistent end to end.

## 1. OpenSpec change naming

Change directories (`openspec/changes/<name>/`) are a flat identifier to the
`openspec` CLI, so the name stays a single kebab-case string — no slashes:

```
<service>-<type>-<issue>-<description>
```

Example: `shared-feat-292-audit-mixin-auto-population`

- **service** — lowercase, one of: `ai`, `backend`, `budget`, `chat`,
  `feature`, `frontend`, `platform`, `shared`, `users` (same set used in
  branch names, see below).
- **type** — `feat` | `fix` | `chore` | `refactor`, matching the commit
  prefixes already used in this repo (not GitHub's `bug` label).
  - `feat` — new capability
  - `fix` — bug fix
  - `chore` — infra/tooling/deps, no behavior change users would notice
  - `refactor` — structural change, no behavior change
- **issue** — the GitHub issue number of the **parent** issue for this
  whole change. Its only job is to hold the per-group sub-issues (§3) — it
  doesn't carry its own task list.
- **description** — short kebab-case summary.

**Ordering with the issue:** a change is often proposed before a ticket
exists. Flow is:

1. `/opsx:propose` with a temporary kebab-case name (no issue number yet).
2. Once `tasks.md` exists and the scope is real, create the parent ticket:
   `scripts/new-issue.sh "<title>" "<body>"`.
3. Rename the change directory to fold in the issue number:
   `mv openspec/changes/{<temp-name>,<service>-<type>-<issue>-<description>}`.

## 2. Branch naming

```
<Service>/<type>/Issue-<sub-issue>/<description>[-group<N>]
```

`Service` is title-cased (`Shared`, `Budget`, `Frontend`, `AI`, ...); `type`
stays lowercase, taken straight from the OpenSpec change name. `<sub-issue>`
is that **group's own** sub-issue number (§3), not the parent's — e.g.
`Shared/feat/Issue-301/audit-mixin-auto-population-group2`.

## 3. Task groups get their own sub-issue

Each `tasks.md` group is tracked as a real GitHub sub-issue of the parent
(GitHub's native sub-issue relationship, not just a text mention) — created
automatically the first time a group is started via `scripts/start-group.sh`:

- Title: `<description>: <group title> (group N)`.
- Body links back to the parent issue and the group's `tasks.md` section.
- Linked to the parent through GitHub's sub-issues API, so it shows up as a
  checklist/progress bar on the parent issue.
- Added to project board 8.
- The sub-issue number is written back onto the group's header line in
  `tasks.md` (`## N. Title — Issue #<sub-issue>`), so re-running the script
  for the same group reuses it instead of creating a duplicate.

## 4. Triggering a task group's branch

Don't rely on remembering to create the sub-issue and branch correctly at
each group boundary — run:

```
scripts/start-group.sh <change-name> <group-number>
```

First run for a group: creates its sub-issue (as in §3), links it under the
parent, and derives the branch from it. Later runs for the same group: reads
the sub-issue back out of `tasks.md` instead of recreating it. Either way it
creates and checks out the branch and flips the sub-issue's project item to
**In Progress**. Refuses to run if the change name doesn't parse or the
group doesn't exist in `tasks.md`.

## 5. PR / issue-closing convention

Each group's PR closes its own sub-issue: `Closes #<sub-issue>` (fires the
board's Done automation for that item). Once every sub-issue under the
parent is closed, close the parent too — it's just a tracking issue at that
point.

## 6. Local lint enforcement before push

`scripts/git-hooks/pre-push` mirrors each service's CI lint step
(`black --check`, `mypy`, `flake8`) locally, scoped to whichever
service(s) the push actually touches (a `shared/` change checks all four).
One-time setup:

```
git config core.hooksPath scripts/git-hooks
```

Bypass with `git push --no-verify` when intentionally needed.
