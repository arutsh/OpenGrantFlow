# Working in this repo

## Branch / issue workflow — mandatory

Every OpenSpec task group gets its own branch and its own GitHub sub-issue,
created together by one command. Full details: `docs/development/WORKFLOW.md`.

**Never create a branch with `git checkout -b` / `git switch -c` / `git branch` by
hand.** Always run:

```
scripts/start-group.sh <change-name> <group-number>
```

This creates the sub-issue, links it under the parent issue, adds it to the
project board, and checks out a correctly-named branch:
`<Service>/<type>/Issue-<sub-issue>/<description>`.

This is enforced, not just documented:
- `.claude/hooks/block_manual_branch_creation.py` (a `PreToolUse` hook on `Bash`)
  blocks manually-created branches whose name doesn't match the convention.
- `scripts/git-hooks/pre-push` refuses to push a branch with a non-conforming
  name (requires `git config core.hooksPath scripts/git-hooks` — see
  WORKFLOW.md §6, which also covers this hook's lint-mirroring behavior).
- `.github/workflows/branch-naming.yml` re-checks the branch name on every
  push and PR as a backstop.

If a task genuinely doesn't fit an OpenSpec change/group (rare — e.g. a
one-off doc fix), ask the user before improvising a branch name outside the
convention.
