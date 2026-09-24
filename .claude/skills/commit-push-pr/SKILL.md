---
name: commit-push-pr
description: Commit currently staged changes, push the current branch, and create a PR if one doesn't exist yet. Use when the user explicitly asks to commit/push/open a PR right now. One-time action for the changes staged at invocation time — it never stages files itself and never authorizes committing/pushing/PR-creation for later changes.
---

Commit the changes the user has already staged, push the current branch, and open a PR if one doesn't exist. This skill acts **only** on what is staged at the moment it's invoked — it is not a standing authorization for future commits/pushes/PRs.

**Scope guardrail (read first)**

- This is a single-shot action over the diff staged right now. Do not treat this invocation as blanket approval to commit, push, or open PRs on later changes in this session — each new batch of changes needs the user to invoke this skill again.
- Never run `git add` / `git add -A` / `git add .` or otherwise stage files yourself. Staging is the user's job (often done mid-review via their IDE). If nothing is staged, stop and tell them so instead of staging it for them.

**Steps**

1. **Check staged state**

   Run in parallel:
   - `git status`
   - `git diff --cached` (staged changes that will be committed)
   - `git diff` (unstaged changes, to detect anything left behind)
   - `git log --oneline -10` (commit message style)
   - `git branch --show-current`

   - If `git diff --cached` is empty, stop and tell the user nothing is staged — do not stage anything yourself.
   - If there are also unstaged or untracked changes not part of the staged diff, tell the user what's being left out of this commit so they aren't surprised later.

2. **Secret scan**

   Look at the staged files for anything env-like (`.env*`, credentials, keys) or that otherwise looks like it could contain secrets. If found, show the user the relevant file/lines and get explicit confirmation before committing — don't silently include it.

3. **Commit**

   Draft a concise commit message (why > what) matching the repo's existing style from `git log`. Commit only the staged changes — never broaden the commit with `git add`. Use a HEREDOC so formatting is preserved, and end the message with:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   ```
   Commit onto the **current branch** — do not create a new branch.

   If the pre-commit hook fails, fix the underlying issue, re-stage only what's needed to fix it (confirm with the user if that means staging new files), and commit again as a new commit. Never use `--no-verify`.

4. **Push**

   Push the current branch. If it has no upstream yet, push with `-u origin <branch>`. Never force-push.

5. **PR: check, then create if missing**

   Run `gh pr view --json url,number,state 2>/dev/null` (or `gh pr list --head <branch> --json url,number`) to see if a PR already exists for this branch.

   - If one exists: report its URL, do not create a duplicate.
   - If none exists: gather the branch's full commit history vs. the base branch (`git log <base>..HEAD`, `git diff <base>...HEAD`), run `scripts/flow.py pr` to get the issue-closing trailer for this branch, and create the PR with `gh pr create`, using a HEREDOC body:
     ```
     ## Summary
     <1-3 bullets>

     ## Test plan
     <checklist>

     🤖 Generated with [Claude Code](https://claude.com/claude-code)

     <the `Closes #...` lines printed by scripts/flow.py pr>
     ```
     Keep the title under ~70 characters. Use the trailer exactly as printed — it emits `Closes #<parent>` alongside `Closes #<sub-issue>` only when this is the last open group, and that is what closes the parent tracking issue and fires the board's Done automation. If `flow.py pr` errors (e.g. the branch isn't a task-group branch), say so and open the PR without a trailer rather than guessing issue numbers.

6. **Report**

   Give the user: commit hash + message, push result, and the PR URL (existing or newly created). Nothing further is authorized beyond this — the next round of changes needs a fresh invocation.
