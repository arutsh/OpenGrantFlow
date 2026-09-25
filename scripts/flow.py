#!/usr/bin/env python3
"""OpenSpec change -> GitHub issues -> branch -> PR.

Subcommands:
  init <change> [--title T]  create the parent issue, fold its number into the
                             change directory name, create every group's
                             sub-issue, write the tracking block
  sync <change>              reconcile groups against GitHub (idempotent)
  start <change> <group>     parent + group to In Progress, branch from main
  pr [--branch B]            print the Closes trailer for a group's PR
  issue "<title>" ["<body>"] create a standalone issue on the board
  cleanup [--yes]            delete local branches whose remote was deleted

GitHub is the source of truth: a group is matched to the sub-issue number
tasks.md records, falling back to the "(group N)" title suffix, and every
sub-issue can be claimed only once — so re-running can never create a duplicate
even when tasks.md is stale, renumbered, or on the wrong branch.

See docs/development/WORKFLOW.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = "arutsh/OpenGrantFlow"
PROJECT_NUMBER = "8"
PROJECT_OWNER = "arutsh"
PROJECT_ID = "PVT_kwHOAQDyGs4A-5Lx"
STATUS_FIELD_ID = "PVTSSF_lAHOAQDyGs4A-5LxzgyKO-Q"
STATUS_OPTIONS = {
    "Backlog": "3dbf10e0",
    "Todo": "f75ad846",
    "In Progress": "47fc9ee4",
    "Done": "98236657",
}

CHANGES_DIR = Path("openspec/changes")
TYPES = ("feat", "fix", "chore", "refactor")
SERVICES = {
    "ai": "AI",
    "backend": "Backend",
    "budget": "Budget",
    "chat": "Chat",
    "feature": "Feature",
    "frontend": "Frontend",
    "infra": "Infra",
    "platform": "Platform",
    "shared": "Shared",
    "users": "Users",
}

ISSUE_URL = f"https://github.com/{REPO}/issues"
BOARD_URL = f"https://github.com/users/{PROJECT_OWNER}/projects/{PROJECT_NUMBER}"

TRACK_START = "<!-- flow:tracking:start -->"
TRACK_END = "<!-- flow:tracking:end -->"
GROUPS_START = "<!-- flow:groups:start -->"
GROUPS_END = "<!-- flow:groups:end -->"

CHANGE_RE = re.compile(
    r"^(?P<service>[a-z]+)-(?P<type>" + "|".join(TYPES) + r")-(?:(?P<issue>\d+)-)?(?P<desc>.+)$"
)
HEADER_RE = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$")
ISSUE_SUFFIX_RE = re.compile(r"\s+—\s+Issue\s+#(\d+)$")
DEPENDS_RE = re.compile(r"\s+—\s+depends on .*$", re.IGNORECASE)
GROUP_TITLE_RE = re.compile(r"\(group (\d+)\)$")
BRANCH_RE = re.compile(r"^[A-Z][A-Za-z]*/(?:" + "|".join(TYPES) + r")/Issue-(\d+)/")

DRY_RUN = False


# --------------------------------------------------------------------------- shell


def die(msg: str) -> "NoReturn":  # noqa: F821
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def run(args: list[str], *, mutating: bool = False, check: bool = True) -> str:
    """Run a command, returning stdout. Mutating commands are skipped on --dry-run."""
    if mutating and DRY_RUN:
        print(f"[dry-run] {' '.join(args)}")
        return ""
    result = subprocess.run(args, capture_output=True, text=True)
    if check and result.returncode != 0:
        die(f"`{' '.join(args)}` failed:\n{(result.stderr or result.stdout).strip()}")
    return (result.stdout or "").strip()


def gh_json(args: list[str]):
    out = run(args)
    return json.loads(out) if out else None


# --------------------------------------------------------------------------- model


@dataclass
class Change:
    name: str
    service: str
    type: str
    issue: int | None
    desc: str

    @property
    def path(self) -> Path:
        return CHANGES_DIR / self.name

    @property
    def tasks_file(self) -> Path:
        return self.path / "tasks.md"

    @property
    def service_title(self) -> str:
        return SERVICES[self.service]


@dataclass
class Group:
    number: int
    line: int
    title: str
    issue: int | None

    @property
    def github_title(self) -> str:
        """The group title without the '— depends on N' planning suffix."""
        return DEPENDS_RE.sub("", self.title).strip()


def parse_change(name: str, *, strict: bool = True) -> Change | None:
    """Parse a change directory name. Returns None for a non-conforming name unless strict."""
    name = name.strip().strip("/").removeprefix("openspec/changes/")
    match = CHANGE_RE.match(name)
    if match and match["service"] not in SERVICES:
        match = None
    if not match:
        if not strict:
            return None
        die(
            f"change name '{name}' doesn't match <service>-<type>[-<issue>]-<description>\n"
            f"       service: {', '.join(SERVICES)}\n"
            f"       type:    {', '.join(TYPES)}"
        )
    return Change(
        name=name,
        service=match["service"],
        type=match["type"],
        issue=int(match["issue"]) if match["issue"] else None,
        desc=match["desc"],
    )


def load_change(name: str, *, require_issue: bool = False) -> Change:
    change = parse_change(name)
    if not change.tasks_file.is_file():
        die(f"{change.tasks_file} not found (run from the repo root)")
    if require_issue and change.issue is None:
        die(f"change '{change.name}' has no parent issue yet — run `{sys.argv[0]} init` first")
    return change


def read_tasks(change: Change) -> list[str]:
    return change.tasks_file.read_text().splitlines()


def parse_groups(lines: list[str]) -> list[Group]:
    groups: list[Group] = []
    for index, line in enumerate(lines):
        match = HEADER_RE.match(line)
        if not match:
            continue
        title = match.group(2)
        issue = None
        suffix = ISSUE_SUFFIX_RE.search(title)
        if suffix:
            issue = int(suffix.group(1))
            title = title[: suffix.start()]
        groups.append(Group(int(match.group(1)), index, title.strip(), issue))
    if not groups:
        die("no '## <N>. <title>' group headers found in tasks.md")
    return groups


def branch_name(change: Change, group: Group) -> str:
    return (
        f"{change.service_title}/{change.type}/Issue-{group.issue}/"
        f"{change.desc}-group{group.number}"
    )


def subissue_title(change: Change, group: Group) -> str:
    return f"{change.desc}: {group.github_title} (group {group.number})"


def change_marker(change: Change) -> str:
    """Stable id for a change, so a re-run of `init` can find a parent it already made."""
    return f"<!-- flow:change:{change.service}-{change.type}-{change.desc} -->"


# --------------------------------------------------------------------------- github


def sub_issues(parent: int) -> list[dict]:
    return gh_json(["gh", "api", f"repos/{REPO}/issues/{parent}/sub_issues", "--paginate"]) or []


def find_parent_issue(marker: str) -> int | None:
    """An existing parent carrying this marker — i.e. one an earlier `init` left behind."""
    found = (
        gh_json(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                REPO,
                "--state",
                "all",
                "--search",
                f'"{marker}" in:body',
                "--json",
                "number",
                "--limit",
                "5",
            ]
        )
        or []
    )
    return found[0]["number"] if found else None


def create_issue(title: str, body: str) -> int | None:
    url = run(
        ["gh", "issue", "create", "--repo", REPO, "--title", title, "--body", body],
        mutating=True,
    )
    if not url:
        return None
    return int(url.rsplit("/", 1)[-1])


def link_sub_issue(parent: int, child: int) -> None:
    child_id = run(["gh", "api", f"repos/{REPO}/issues/{child}", "--jq", ".id"])
    run(
        [
            "gh",
            "api",
            f"repos/{REPO}/issues/{parent}/sub_issues",
            "--method",
            "POST",
            "-F",
            f"sub_issue_id={child_id}",
        ],
        mutating=True,
    )


PROJECT_ITEM_QUERY = """
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      projectItems(first: 20) {
        nodes {
          id
          project { number }
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
        }
      }
    }
  }
}
"""


def board_item(issue: int) -> tuple[str, str | None] | None:
    """This issue's (item id, status) on the project board, or None if it isn't on it.

    Queried per issue rather than via `gh project item-list`, which silently
    truncates on a board this size and would report a present item as missing.
    """
    owner, repo = REPO.split("/")
    nodes = (
        gh_json(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={PROJECT_ITEM_QUERY}",
                "-f",
                f"owner={owner}",
                "-f",
                f"repo={repo}",
                "-F",
                f"number={issue}",
                "--jq",
                ".data.repository.issue.projectItems.nodes",
            ]
        )
        or []
    )
    for node in nodes:
        if node.get("project", {}).get("number") == int(PROJECT_NUMBER):
            return node["id"], (node.get("fieldValueByName") or {}).get("name")
    return None


def board_add(issue: int) -> str | None:
    """Add the issue to the project board, returning its item id.

    Not `check=True`: the board's own auto-add workflow races us, and once it
    wins, `item-add` fails with "Content already exists in this project". Only
    a re-query can tell that apart from a real failure, so ask before dying.
    """
    out = run(
        [
            "gh",
            "project",
            "item-add",
            PROJECT_NUMBER,
            "--owner",
            PROJECT_OWNER,
            "--url",
            f"{ISSUE_URL}/{issue}",
            "--format",
            "json",
        ],
        mutating=True,
        check=False,
    )
    if out:
        return json.loads(out)["id"]
    if DRY_RUN:
        return None
    found = board_item(issue)
    if found:
        return found[0]
    die(f"could not add #{issue} to project board {PROJECT_NUMBER}")


def board_status(issue: int, status: str, *, keep: tuple[str, ...] = ()) -> None:
    """Put the issue on the board and set its status, leaving `keep` statuses alone."""
    found = board_item(issue)
    if found is None:
        item_id, current = board_add(issue), None
        if item_id:
            print(f"  board: added #{issue}")
    else:
        item_id, current = found
    if not item_id or current == status or current in keep:
        return
    run(
        [
            "gh",
            "project",
            "item-edit",
            "--id",
            item_id,
            "--project-id",
            PROJECT_ID,
            "--field-id",
            STATUS_FIELD_ID,
            "--single-select-option-id",
            STATUS_OPTIONS[status],
        ],
        mutating=True,
    )
    print(f"  board: #{issue} -> {status}")


def board_ensure(issue: int) -> None:
    """Add the issue to the board if missing, without disturbing an existing status."""
    board_status(issue, "Todo", keep=tuple(STATUS_OPTIONS))


# --------------------------------------------------------------------------- tasks.md


def short(title: str, limit: int = 58) -> str:
    title = DEPENDS_RE.sub("", title).strip()
    return title if len(title) <= limit else title[: limit - 1].rstrip() + "…"


def render_tracking(change: Change, groups: list[Group], states: dict[int, str]) -> list[str]:
    rows = [
        "| Group | Sub-issue | Branch | State |",
        "| --- | --- | --- | --- |",
    ]
    for group in groups:
        if group.issue:
            issue_cell = f"[#{group.issue}]({ISSUE_URL}/{group.issue})"
            branch_cell = f"`{branch_name(change, group)}`"
            state_cell = states.get(group.issue, "unknown")
        else:
            issue_cell = branch_cell = "—"
            state_cell = "not created"
        rows.append(
            f"| {group.number}. {short(group.title)} | {issue_cell}"
            f" | {branch_cell} | {state_cell} |"
        )
    return [
        TRACK_START,
        "## Tracking",
        "",
        f"Parent issue: [#{change.issue}]({ISSUE_URL}/{change.issue})"
        f" · [Project board]({BOARD_URL})",
        "",
        *rows,
        "",
        f"_Generated by `scripts/flow.py sync {change.name}` — do not edit by hand._",
        TRACK_END,
    ]


def write_tasks(
    change: Change, lines: list[str], groups: list[Group], states: dict[int, str]
) -> None:
    for group in groups:
        if group.issue:
            lines[group.line] = f"## {group.number}. {group.title} — Issue #{group.issue}"

    block = render_tracking(change, groups, states)
    start = lines.index(TRACK_START) if TRACK_START in lines else -1
    end = lines.index(TRACK_END) + 1 if TRACK_END in lines else -1
    if start >= 0 and end > start:
        lines[start:end] = block
    elif start >= 0 or end >= 0:
        # a lone marker means a bad merge ate part of the block; what survived is unknowable
        die(
            f"{change.tasks_file} has a damaged tracking block (one marker only) — "
            f"delete both markers and the lines between them, then re-run sync"
        )
    else:
        header_at = next((i for i, line in enumerate(lines) if HEADER_RE.match(line)), len(lines))
        start = header_at
        while start > 0 and not lines[start - 1].strip():
            start -= 1
        lines[start:header_at] = ["", *block, ""]

    text = "\n".join(lines).rstrip() + "\n"
    if DRY_RUN:
        print(f"[dry-run] would write {change.tasks_file}")
        return
    change.tasks_file.write_text(text)
    print(f"  wrote {change.tasks_file}")


# --------------------------------------------------------------------------- reconcile


def retitle_sub_issue(change: Change, group: Group, sub: dict) -> None:
    """Move a sub-issue's '(group N)' suffix onto the group that now records it."""
    current = GROUP_TITLE_RE.search(sub["title"])
    if current and int(current.group(1)) == group.number:
        return
    title = subissue_title(change, group)
    run(
        ["gh", "issue", "edit", str(sub["number"]), "--repo", REPO, "--title", title],
        mutating=True,
    )
    print(f"  group {group.number}: retitled #{sub['number']} — {title}")


def match_groups(change: Change, groups: list[Group]) -> dict[int, dict]:
    """Group number -> its sub-issue, for the groups that already have one.

    Two passes, because the two signals disagree whenever groups are renumbered:
    the number recorded in tasks.md wins, and the '(group N)' title suffix is
    only the fallback for groups that record none. A sub-issue can be claimed
    once, so no two groups can end up pointing at the same one.
    """
    existing = sub_issues(change.issue)
    by_number = {s["number"]: s for s in existing}
    by_suffix: dict[int, list[dict]] = {}
    for sub in existing:
        suffix = GROUP_TITLE_RE.search(sub["title"])
        if suffix:
            by_suffix.setdefault(int(suffix.group(1)), []).append(sub)

    matched: dict[int, dict] = {}
    claimed: set[int] = set()

    for group in groups:
        sub = by_number.get(group.issue) if group.issue else None
        if group.issue and sub is None:
            sub = gh_json(["gh", "api", f"repos/{REPO}/issues/{group.issue}"])
            if not sub or "pull_request" in sub:
                die(f"#{group.issue} is not an issue that can be linked to #{change.issue}")
            # Without reparenting permission, GitHub rejects issues owned by another parent.
            link_sub_issue(change.issue, group.issue)
            by_number[group.issue] = sub
        if sub and sub["number"] not in claimed:
            matched[group.number] = sub
            claimed.add(sub["number"])

    for group in groups:
        if group.number in matched:
            continue
        candidates = [
            s
            for s in sorted(by_suffix.get(group.number, []), key=lambda s: s["number"])
            if s["number"] not in claimed
        ]
        if not candidates:
            continue
        matched[group.number] = candidates[0]
        claimed.add(candidates[0]["number"])
        if group.issue:
            warn(
                f"group {group.number} pointed at #{group.issue}, which is not a sub-issue "
                f"of #{change.issue}; repointing at #{candidates[0]['number']}"
            )

    known = {g.number for g in groups}
    for number, subs in sorted(by_suffix.items()):
        loose = [f"#{s['number']}" for s in subs if s["number"] not in claimed]
        if not loose:
            continue
        listed = ", ".join(loose)
        if number in known:
            warn(f"sub-issue(s) {listed} also claim group {number}, which matched another issue")
        else:
            warn(
                f"sub-issue(s) {listed} reference group {number}, "
                f"which no longer exists in tasks.md"
            )
    return matched


def reconcile(change: Change, groups: list[Group]) -> dict[int, str]:
    """Match every group to a sub-issue of the parent, creating what's missing.

    The sub-issue number recorded in tasks.md is the source of truth; the
    '(group N)' title suffix is the fallback (see `match_groups`). Either way a
    sub-issue is matched before anything is created, so a stale or branch-local
    tasks.md can never cause a duplicate.
    """
    matched = match_groups(change, groups)

    states: dict[int, str] = {}
    for group in groups:
        chosen = matched.get(group.number)
        if chosen:
            group.issue = chosen["number"]
            retitle_sub_issue(change, group, chosen)
            board_ensure(chosen["number"])  # it may predate us, or have been auto-added
            states[chosen["number"]] = chosen["state"]
            print(f"  group {group.number}: #{chosen['number']} ({chosen['state']})")
            continue

        title = subissue_title(change, group)
        body = (
            f"Group {group.number} of the `{change.name}` OpenSpec change "
            f"(parent: #{change.issue}).\n\n"
            f"{group.title}\n\n"
            f"See `openspec/changes/{change.name}/tasks.md`, group {group.number}.\n\n"
            f"Branch: `{change.service_title}/{change.type}/Issue-<this issue>/"
            f"{change.desc}-group{group.number}`"
        )
        number = create_issue(title, body)
        if number is None:
            print(f"  group {group.number}: [dry-run] would create sub-issue")
            continue
        group.issue = number
        # Save the recovery handle before either subsequent GitHub mutation can fail.
        lines = read_tasks(change)
        lines[group.line] = f"## {group.number}. {group.title} — Issue #{number}"
        if not DRY_RUN:
            change.tasks_file.write_text("\n".join(lines) + "\n")
        link_sub_issue(change.issue, number)
        board_status(number, "Todo")
        states[number] = "open"
        print(f"  group {group.number}: created #{number} — {title}")
    return states


def refresh_parent_body(change: Change, groups: list[Group]) -> None:
    body = gh_json(["gh", "issue", "view", str(change.issue), "--repo", REPO, "--json", "body"])
    text = (body or {}).get("body", "")
    if GROUPS_START not in text or GROUPS_END not in text:
        return
    listing = "\n".join(
        f"- Group {g.number}: {g.github_title}" + (f" — #{g.issue}" if g.issue else "")
        for g in groups
    )
    head, rest = text.split(GROUPS_START, 1)
    _, tail = rest.split(GROUPS_END, 1)
    updated = f"{head}{GROUPS_START}\n{listing}\n{GROUPS_END}{tail}"
    if updated == text:
        return
    run(
        ["gh", "issue", "edit", str(change.issue), "--repo", REPO, "--body", updated], mutating=True
    )
    print(f"  refreshed #{change.issue} body")


# --------------------------------------------------------------------------- commands


def cmd_init(args) -> None:
    change = load_change(args.change)
    if change.issue is not None:
        die(f"'{change.name}' already carries parent issue #{change.issue} — use `sync` instead")

    lines = read_tasks(change)
    groups = parse_groups(lines)
    title = args.title or f"{change.desc.replace('-', ' ')}"

    listing = "\n".join(f"- Group {g.number}: {g.github_title}" for g in groups)
    marker = change_marker(change)
    body = (
        f"Tracking issue for the `{change.service}-{change.type}-<this issue>-{change.desc}` "
        f"OpenSpec change.\n\n"
        f"One task group = one sub-issue = one PR, merged before the next group starts. "
        f"This issue holds no task list of its own — see the sub-issues below.\n\n"
        f"{GROUPS_START}\n{listing}\n{GROUPS_END}\n\n"
        f"Artifacts: `openspec/changes/{change.service}-{change.type}-<this issue>-{change.desc}/` "
        f"(proposal.md, design.md, tasks.md).\n\n"
        f"{marker}"
    )

    if DRY_RUN:
        print(f"[dry-run] parent issue: {title}")
        print(
            f"[dry-run] rename:       {change.path} -> "
            f"{CHANGES_DIR}/{change.service}-{change.type}-<issue>-{change.desc}"
        )
        for group in groups:
            print(f"[dry-run] sub-issue:    {subissue_title(change, group)}")
        return

    parent = find_parent_issue(marker)
    if parent:
        print(f"Resuming '{change.name}' — parent #{parent} already exists")
    else:
        print(f"Creating parent issue for '{change.name}' ({len(groups)} groups)")
        parent = create_issue(title, body)
        print(f"  parent: #{parent} — {title}")

    # the rename comes first: until it lands, only the marker search can find this parent
    new_name = f"{change.service}-{change.type}-{parent}-{change.desc}"
    new_path = CHANGES_DIR / new_name
    try:
        tracked = run(["git", "ls-files", str(change.path)], check=False)
        if tracked:
            run(["git", "mv", str(change.path), str(new_path)], mutating=True)
        else:
            change.path.rename(new_path)
        print(f"  renamed {change.path} -> {new_path}")

        change = parse_change(new_name)
        board_status(parent, "Todo")
        run(
            [
                "gh",
                "issue",
                "edit",
                str(parent),
                "--repo",
                REPO,
                "--body",
                body.replace("<this issue>", str(parent)),
            ],
            mutating=True,
        )

        lines = read_tasks(change)
        groups = parse_groups(lines)
        states = reconcile(change, groups)
        write_tasks(change, lines, groups, states)
        refresh_parent_body(change, groups)
    except (Exception, SystemExit):
        recovery = (
            f"{sys.argv[0]} sync {new_name}"
            if change.name == new_name
            else f"{sys.argv[0]} init {args.change}"
        )
        print(
            f"\nparent #{parent} exists. Resume with:\n  {recovery}",
            file=sys.stderr,
        )
        raise

    print(f"\nParent #{parent}: {ISSUE_URL}/{parent}")
    print(f"Commit the rename + tasks.md on main, then: {sys.argv[0]} start {new_name} 1")


def cmd_sync(args) -> None:
    change = load_change(args.change, require_issue=True)
    lines = read_tasks(change)
    groups = parse_groups(lines)
    print(f"Syncing '{change.name}' against parent #{change.issue}")
    board_ensure(change.issue)
    states = reconcile(change, groups)
    write_tasks(change, lines, groups, states)
    refresh_parent_body(change, groups)


def cmd_start(args) -> None:
    change = load_change(args.change, require_issue=True)
    groups = parse_groups(read_tasks(change))
    group = next((g for g in groups if g.number == args.group), None)
    if group is None:
        die(f"no '## {args.group}.' group in {change.tasks_file}")

    if group.issue is None:
        die(
            f"group {args.group} has no sub-issue recorded in tasks.md.\n"
            f"       Run `{sys.argv[0]} sync {change.name}` on main and commit it first, so the\n"
            f"       issue number is on main rather than only on a feature branch."
        )
    if not any(s["number"] == group.issue for s in sub_issues(change.issue)):
        die(
            f"#{group.issue} is recorded for group {args.group} but is not a sub-issue of "
            f"#{change.issue}.\n       Run `{sys.argv[0]} sync {change.name}` on main to repair it."
        )

    branch = branch_name(change, group)
    if run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], check=False):
        die(f"branch {branch} already exists — `git switch {branch}` to resume it")
    if run(["git", "status", "--porcelain"]):
        die("working tree is not clean — commit or stash before starting a group")

    print(f"Change:    {change.name}")
    print(f"Group:     {group.number}. {group.github_title}")
    print(f"Parent:    #{change.issue}   Sub-issue: #{group.issue}")
    print(f"Branch:    {branch}  (from {args.base})\n")

    run(["git", "fetch", "origin", args.base], mutating=True)
    run(["git", "checkout", args.base], mutating=True)
    run(["git", "pull", "--ff-only", "origin", args.base], mutating=True)
    run(["git", "checkout", "-b", branch], mutating=True)
    print(f"  on {branch}")

    board_status(change.issue, "In Progress", keep=("Done",))
    board_status(group.issue, "In Progress", keep=("Done",))

    print(f"\nWhen the group is done, open the PR with:  {sys.argv[0]} pr")


def find_change_for_issue(sub: int) -> tuple[Change, Group, list[Group]] | None:
    for tasks_file in sorted(CHANGES_DIR.glob("*/tasks.md")):
        if "archive" in tasks_file.parts:
            continue
        change = parse_change(tasks_file.parent.name, strict=False)
        if change is None or change.issue is None:
            continue
        groups = parse_groups(tasks_file.read_text().splitlines())
        group = next((g for g in groups if g.issue == sub), None)
        if group:
            return change, group, groups
    return None


USER_FACING_ROOT = "frontend-typescript/src/"
USER_FACING_EXCLUDE_RE = re.compile(r"\.(test|spec|stories)\.[jt]sx?$|/__tests__/|/__mocks__/")


def warn_if_user_guide_stale(branch: str) -> None:
    base = run(["git", "merge-base", "main", branch], check=False)
    if not base:
        return
    changed = run(["git", "diff", "--name-only", base, branch], check=False).splitlines()
    user_facing = [
        f
        for f in changed
        if f.startswith(USER_FACING_ROOT) and not USER_FACING_EXCLUDE_RE.search(f)
    ]
    if user_facing and not any(f.startswith("docs/user-guide/") for f in changed):
        warn(
            "touches user-facing frontend code but not docs/user-guide/ — update the guide "
            "(and its 'Last reviewed' line) if this changes what users see"
        )


def cmd_pr(args) -> None:
    branch = args.branch or run(["git", "branch", "--show-current"])
    match = BRANCH_RE.match(branch)
    if not match:
        die(f"branch '{branch}' doesn't match <Service>/<type>/Issue-<n>/<description>")
    sub = int(match.group(1))
    warn_if_user_guide_stale(branch)

    found = find_change_for_issue(sub)
    closes = [sub]
    if found is None:
        warn(f"no change in {CHANGES_DIR} records sub-issue #{sub}; closing it alone")
    else:
        change, group, groups = found
        # Include groups added since branching, even if their titles were edited.
        siblings = sub_issues(change.issue)
        unfinished = [
            f"#{s['number']}" for s in siblings if s["number"] != sub and s["state"] != "closed"
        ]
        linked = {s["number"] for s in siblings}
        uncreated = [
            f"group {g.number} (no linked sub-issue)" for g in groups if g.issue not in linked
        ]
        unfinished += uncreated
        total = len(siblings) + len(uncreated)
        tail = f"; still open: {', '.join(unfinished)}" if unfinished else "; last open group"
        print(f"# {change.name} — group {group.number} of {total}{tail}", file=sys.stderr)
        if not unfinished:
            closes.append(change.issue)

    print("\n".join(f"Closes #{n}" for n in closes))


def cmd_cleanup(args) -> None:
    run(["git", "fetch", "--prune", "origin"], mutating=True)

    current = run(["git", "branch", "--show-current"])
    worktree_branches = {
        line.removeprefix("branch refs/heads/")
        for line in run(["git", "worktree", "list", "--porcelain"]).splitlines()
        if line.startswith("branch ")
    }

    gone = []
    for line in run(
        ["git", "for-each-ref", "refs/heads", "--format=%(refname:short) %(upstream:track)"]
    ).splitlines():
        branch, _, track = line.partition(" ")
        if "[gone]" in track and branch != current and branch not in worktree_branches:
            gone.append(branch)

    if not gone:
        print("no local branches with a deleted remote")
        return

    print(f"{len(gone)} local branch(es) with a deleted remote:")
    for branch in gone:
        print(f"  {branch}")

    if not args.yes:
        answer = input("\nDelete these branches? [y/N] ").strip().lower()
        if answer != "y":
            print("aborted")
            return

    for branch in gone:
        run(["git", "branch", "-D", branch], mutating=True)
        print(f"  deleted {branch}")


def cmd_issue(args) -> None:
    number = create_issue(args.title, args.body or "")
    if number is None:
        return
    board_status(number, "Todo")
    print(f"{ISSUE_URL}/{number}")


# --------------------------------------------------------------------------- cli


def main() -> None:
    global DRY_RUN
    parser = argparse.ArgumentParser(
        prog="scripts/flow.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", help="print mutating commands only")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create parent issue + every group sub-issue")
    p.add_argument("change")
    p.add_argument("--title", help="parent issue title (default: derived from the change name)")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("sync", help="reconcile groups against GitHub (idempotent)")
    p.add_argument("change")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("start", help="move to In Progress and branch")
    p.add_argument("change")
    p.add_argument("group", type=int)
    p.add_argument("--base", default="main", help="branch off this ref instead of main")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("pr", help="print the Closes trailer for this branch")
    p.add_argument("--branch", help="inspect this branch instead of the current one")
    p.set_defaults(func=cmd_pr)

    p = sub.add_parser("issue", help="create a standalone issue on the board")
    p.add_argument("title")
    p.add_argument("body", nargs="?")
    p.set_defaults(func=cmd_issue)

    p = sub.add_parser("cleanup", help="delete local branches whose remote was deleted")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.set_defaults(func=cmd_cleanup)

    args = parser.parse_args()
    DRY_RUN = args.dry_run
    if not Path(".git").exists():
        die("run from the repository root")
    args.func(args)


if __name__ == "__main__":
    main()
