# OpenSpec → Issue → Branch → PR Workflow

How a piece of work moves from an OpenSpec change to merged code, and how the
naming and tracking stay consistent end to end.

Everything below is driven by one tool, `scripts/flow.py`:

| Command | When | What it does |
| --- | --- | --- |
| `flow.py init <change> --title T` | right after proposing | parent issue + directory rename + a sub-issue per task group + Tracking block |
| `flow.py sync <change>` | whenever `tasks.md` groups change | idempotent reconcile of groups ↔ sub-issues |
| `flow.py start <change> <group>` | starting a group | parent + group → In Progress, branch from `main` |
| `flow.py pr` | opening the PR | prints the `Closes` trailer |
| `flow.py issue "<t>" "<body>"` | one-off ticket | issue on the board, outside any change |

Sub-issues are matched to task groups by the issue number recorded in `tasks.md`,
falling back to the `(group N)` title suffix when no number is recorded.
New issue numbers are saved before linking or updating the board, so `sync`
can resume those steps after a failure without creating another ticket.

## 1. OpenSpec change naming

Change directories (`openspec/changes/<name>/`) are a flat identifier to the
`openspec` CLI, so the name stays a single kebab-case string — no slashes:

```
<service>-<type>-<issue>-<description>
```

Example: `shared-feat-292-audit-mixin-auto-population`

- **service** — lowercase, one of: `ai`, `backend`, `budget`, `chat`,
  `feature`, `frontend`, `infra`, `platform`, `shared`, `users` (the `SERVICES`
  map in `scripts/flow.py`; same set used in branch names, see §3).
- **type** — `feat` | `fix` | `chore` | `refactor`, matching the commit
  prefixes already used in this repo (not GitHub's `bug` label).
  - `feat` — new capability
  - `fix` — bug fix
  - `chore` — infra/tooling/deps, no behavior change users would notice
  - `refactor` — structural change, no behavior change
- **issue** — the GitHub issue number of the **parent** issue for this whole
  change. Its only job is to hold the per-group sub-issues (§2) — it doesn't
  carry its own task list.
- **description** — short kebab-case summary.

## 2. Creating the change's issues

A change is proposed before any ticket exists, so:

1. `/opsx:propose` with a name that has **no** issue number yet:
   `<service>-<type>-<description>`.
2. Once `tasks.md` is real, on `main`:

   ```
   scripts/flow.py init <service>-<type>-<description> --title "<parent title>"
   ```

   which, in one step:
   - creates the parent tracking issue and adds it to project board 8 as **Todo**;
   - `git mv`s the change directory to fold in the new issue number;
   - creates a sub-issue for **every** group in `tasks.md`, links each one under
     the parent through GitHub's native sub-issues API (so the parent shows a
     progress bar), and adds each to the board;
   - writes the group's number back onto its header (`## N. Title — Issue #<n>`)
     and generates the Tracking block at the top of `tasks.md`.
3. Commit the rename and the `tasks.md` edits **on `main`** before starting any
   group. This is the whole point: the group↔issue mapping must exist on `main`,
   not only on a feature branch.

Sub-issue titles are `<description>: <group title> (group N)`, with any
`— depends on N` planning suffix stripped.

If groups are added, removed or renamed afterwards, re-run
`scripts/flow.py sync <change-name>` on `main` and commit it. `sync` creates
what's missing, links a recorded issue if it is still unlinked,
refreshes the Tracking block and the parent issue's group list, and warns about
duplicates and orphaned sub-issues instead of silently papering over them.
If a recorded issue belongs to another parent, linking fails and `sync` stops
without moving it or creating a replacement.

### The Tracking block

`tasks.md` carries a generated block between `<!-- flow:tracking:start -->` and
`<!-- flow:tracking:end -->`, listing the parent issue, the board, and a
group → sub-issue → branch → state table. It is rewritten wholesale by `init`
and `sync` — don't hand-edit it.

## 3. Branch naming

```
<Service>/<type>/Issue-<sub-issue>/<description>-group<N>
```

`Service` is title-cased (`Shared`, `Budget`, `Frontend`, `AI`, ...); `type`
stays lowercase, taken straight from the OpenSpec change name. `<sub-issue>` is
that **group's own** sub-issue number, not the parent's — e.g.
`Shared/feat/Issue-301/audit-mixin-auto-population-group2`.

## 4. Starting a task group

```
scripts/flow.py start <change-name> <group-number>
```

- Moves the **parent** issue to In Progress (unless it's already Done) and the
  **group's** sub-issue to In Progress.
- Fetches `origin/main`, fast-forwards, and branches from it. Use
  `--base <ref>` to branch from something else.
- Refuses if the working tree is dirty, if the branch already exists, or if the
  group has no sub-issue recorded in `tasks.md` on the current checkout — in
  that last case it tells you to run `sync` on `main` and commit first, rather
  than creating a duplicate issue.

## 5. Opening the PR

```
scripts/flow.py pr
```

Reads the sub-issue out of the current branch name, finds the change and group
that own it, and prints:

```
Closes #<sub-issue>
```

plus `Closes #<parent>` when every other group's sub-issue is already closed —
so the parent closes itself with the last group's PR instead of relying on
someone remembering. Paste the output at the end of the PR body; it fires the
board's Done automation for each issue named.

## 6. One-off tickets

For work that isn't an OpenSpec change (a doc fix, a bug found in passing):

```
scripts/flow.py issue "<title>" "<body>"
```

Creates the issue and puts it on the board as Todo. If it needs a branch, agree
a name with a human first — the convention above assumes a sub-issue exists.

## 7. Local lint enforcement before push

`scripts/git-hooks/pre-push` mirrors each service's CI lint step
(`black --check`, `mypy`, `flake8`) locally, scoped to whichever service(s) the
push actually touches (a `shared/` change checks all four). A push touching
`scripts/*.py` runs `black --check`, `flake8 --max-line-length=100` and
`scripts/test_flow.py` over `scripts/` — the workflow tooling lints itself. The
hook also rejects a branch whose name doesn't match §3. One-time setup:

```
git config core.hooksPath scripts/git-hooks
```

Bypass with `git push --no-verify` when intentionally needed.

## 8. Testing the tool itself

`scripts/test_flow.py` covers the change-name/group parsing and the `tasks.md`
rewriting — the load-bearing, network-free parts:

```
python3 -m pytest scripts/test_flow.py -q
```

`.github/workflows/tooling.yml` runs the same tests plus `black`/`flake8` over
`scripts/` on any push or PR that touches `scripts/**`, and the pre-push hook
(§7) mirrors it locally.

`scripts/flow.py --dry-run <subcommand> ...` prints every mutating `gh`/`git`
call instead of running it, which is the safe way to preview `init` or `sync`.
