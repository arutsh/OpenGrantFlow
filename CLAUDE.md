# Working in this repo

## OpenSpec → issue → branch → PR — mandatory

One OpenSpec change = one GitHub parent issue. One task group = one sub-issue =
one branch = one PR. All of it runs through `scripts/flow.py`. Full details:
`docs/development/WORKFLOW.md`.

There are three moments:

**1. After proposing a change** — create the tracking issues:

```
scripts/flow.py init <change-name> --title "<parent issue title>"
```

Creates the parent issue, folds its number into the change directory name
(`<service>-<type>-<issue>-<description>`), creates a sub-issue for **every**
task group up front, and writes the generated Tracking block into `tasks.md`.
Run it on `main` and commit the result before starting any group.

If `tasks.md` gains, loses, or renames a group later, re-run
`scripts/flow.py sync <change-name>` on `main` and commit that too.

**2. When starting a task group** — never create the branch by hand:

```
scripts/flow.py start <change-name> <group-number>
```

Moves the parent and that group to **In Progress**, then branches from a fresh
`main` as `<Service>/<type>/Issue-<sub-issue>/<description>-group<N>`. Pass
`--base <ref>` to branch from something other than `main`.

**Never** use `git checkout -b` / `git switch -c` / `git branch` directly.

**3. When opening the PR** — get the closing trailer from the branch:

```
scripts/flow.py pr
```

Prints `Closes #<sub-issue>`, plus `Closes #<parent>` when every sibling group
is already closed. Put those lines at the end of the PR body — that is what
fires the board's Done automation.

This is enforced, not just documented:
- `.claude/hooks/block_manual_branch_creation.py` (a `PreToolUse` hook on `Bash`)
  blocks manually-created branches whose name doesn't match the convention.
- `scripts/git-hooks/pre-push` refuses to push a branch with a non-conforming
  name (requires `git config core.hooksPath scripts/git-hooks` — see
  WORKFLOW.md §8, which also covers this hook's lint-mirroring behavior).
- `.github/workflows/branch-naming.yml` re-checks the branch name on every
  push and PR as a backstop.

For a ticket that isn't part of an OpenSpec change, use
`scripts/flow.py issue "<title>" "<body>"`. If such a task still needs a branch,
ask the user before improvising a name outside the convention.

## Comments — keep them short

Comments (line-comment runs, `/* */` blocks, docstrings) are at most 2 lines.
Longer rationale belongs in a commit message, PR description, or docs — not
in the code.

This is enforced, not just documented: `.claude/hooks/check_comment_brevity.py`
(a `PreToolUse` hook on `Write`/`Edit`) denies any write that introduces a
comment longer than that, so trim it before retrying rather than fighting the
hook.
