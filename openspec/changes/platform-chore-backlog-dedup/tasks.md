# Tasks

Workflow rule: one task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

## 1. Service labels on every created issue, and the proposal rule

- [ ] 1.0 Run `scripts/flow.py start platform-chore-backlog-dedup 1` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 1.1 Add a `labels` subcommand that runs `gh label create <name> --force` for `svc:<key>` (each `SERVICES` key) and `review-followup` (D1). Verify with a test asserting the exact `gh` argument lists, and with `--dry-run labels` printing one command per label.
- [ ] 1.2 Change `create_issue(title, body)` to `create_issue(title, body, labels)` and pass one `--label` per entry. Pass `svc:<change.service>` from `init` and `reconcile` (D2). Verify with tests that `init` and `reconcile` pass the label arguments to `gh issue create`.
- [ ] 1.3 Add a required `--service` to `issue`, validated against `SERVICES`, and pass `svc:<service>`. Verify with tests: an unknown service exits non-zero, and a valid one reaches `gh issue create` with the label.
- [ ] 1.4 Add the proposal rule to `rules.proposal` in `openspec/config.yaml`: run `openspec list` and `gh issue list --state open --search` before drafting, and end with a `## Related` section classifying each overlap as absorbs / depends on / supersedes / independent. If an existing change covers the same scope, update it instead. (Group 2 switches the command to `flow.py related`.) Verify that `openspec instructions proposal --change platform-chore-backlog-dedup --json` shows the rule under `rules`.
- [ ] 1.5 Update `docs/development/WORKFLOW.md`: add the triage section (issue vs change), `labels` and `issue --service` in the command table, and the `svc:` labels. Update the `flow.py issue` line in `CLAUDE.md` to include `--service`. Verify every documented command runs under `--dry-run`.
- [ ] 1.6 Run `scripts/flow.py labels` once, then add `svc:` labels to the existing open issues by hand. Verify that `gh issue list --state open --json labels` shows no issue without an `svc:` label.
- [ ] 1.7 Run `python3 -m pytest scripts/test_flow.py -q`, `black --check scripts/` and `flake8 --max-line-length=100 scripts/` clean; PR merged.

## 2. Related-work search and the duplicate gate — ticket depends on 1

- [ ] 2.0 Run `scripts/flow.py start platform-chore-backlog-dedup 2` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 2.1 Implement keyword extraction (D3: lowercase, stopwords removed, words of 4+ characters, de-duplicated, at most 6). Verify with a parametrized test covering stopword removal, the length cutoff, de-duplication and the cap.
- [ ] 2.2 Implement `find_related(text)` (D3): issue search as one query per keyword pair, merged by number; a `proposal.md` scan of `openspec/changes` excluding `archive/`, with score ≥ 2; ranked and capped at 10. Verify with tests using a `tmp_path` changes fixture and a monkeypatched `gh_json`, covering the archived-change exclusion, the score threshold, merging by issue number and the cap.
- [ ] 2.3 Add a read-only `related "<text>"` subcommand that prints the matches and always exits 0. Verify with a test that it makes no mutating `run` call.
- [ ] 2.4 Add `confirm_no_duplicate(text, force)` and a `--force` flag to `issue`, gating it as in D4 (terminal → y/N defaulting to No; no terminal → die; `--force` → continue; `--dry-run` → print and stop). Verify with one test per D4 branch, monkeypatching `sys.stdin.isatty` and `input`.
- [ ] 2.5 Make `init` warn with the `find_related` matches for the change description and the proposal's first heading, without prompting. Verify with a test that `init` continues when there are matches and prints them to stderr.
- [ ] 2.6 Point the `openspec/config.yaml` proposal rule at `scripts/flow.py related "<keywords>"`. Document `related`, the gate and `--force` in `docs/development/WORKFLOW.md`. Verify that `openspec instructions proposal ... --json` shows the updated rule.
- [ ] 2.7 Run `python3 -m pytest scripts/test_flow.py -q`, `black --check scripts/` and `flake8 --max-line-length=100 scripts/` clean, plus a manual `scripts/flow.py related "provider ssrf"` that lists the in-flight `ai-fix-361-provider-ssrf` change; PR merged.

## 3. Deferred review findings and absorbed issues — ticket depends on 1, 2

- [ ] 3.0 Run `scripts/flow.py start platform-chore-backlog-dedup 3` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 3.1 Parse an `Absorbs: #n, #m` line directly under a `## N.` heading into `Group.absorbs` (D5) and ignore it anywhere else. Verify with `parse_groups` tests: present, absent, placed elsewhere (ignored), and a Tracking block written by `write_tasks` leaving the line intact.
- [ ] 3.2 Make `cmd_pr` print `Closes #n` for each absorbed issue of the current group, before the parent's trailer. Verify by extending the existing `test_pr_closes_parent_only_when_all_groups_are_linked_and_finished` fixtures with an absorbed issue.
- [ ] 3.3 Add `defer "<title>" --pr N [--file path:line] [--comment URL] [--service S] [--force] [body]` (D6): service taken from the branch or `--service`; the D4 gate; the D6 body template; labels `svc:<service>` and `review-followup`; board status **Backlog**; no sub-issue link; prints `Deferred: #n`. Verify with tests for body rendering (with and without `--file`/`--comment`), deriving the service from the branch, failing on a non-conforming branch without `--service`, the label list, and that no sub-issue call is made.
- [ ] 3.4 Add the tasks rule to `openspec/config.yaml`: when the proposal's Related section says a change absorbs #n, put `Absorbs: #n` under the group that fixes it. Document `defer`, `Absorbs:` and the review-findings policy (fixed findings stay as PR comments, deferred ones go through `defer`) in `docs/development/WORKFLOW.md`, and add a one-line pointer in `CLAUDE.md`. Verify with `openspec instructions tasks ... --json` and a read-through of the docs.
- [ ] 3.5 Run `python3 -m pytest scripts/test_flow.py -q`, `black --check scripts/` and `flake8 --max-line-length=100 scripts/` clean, plus a manual `--dry-run defer` from a group branch showing the expected `gh` calls; PR merged.
- [ ] 3.6 After merge: move the review backlogs held only in agent memory (chat-migration, donor-dashboard, donor-grantee) into issues with `flow.py defer --force`. Verify each appears on the board as Backlog with `review-followup`, then trim those memory entries to issue pointers.
