"""Tests for scripts/flow.py's parsing and tasks.md rewriting (no network)."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location("flow", Path(__file__).with_name("flow.py"))
flow = importlib.util.module_from_spec(spec)
sys.modules["flow"] = flow  # dataclasses resolves annotations through sys.modules
spec.loader.exec_module(flow)


TASKS = """# Tasks

Workflow rule: one task group = one GitHub sub-issue = one PR.

## 1. Export endpoint scaffolding — Issue #316

- [x] 1.1 Do the thing

## 2. Dashboard sheet — depends on 1 — Issue #318

- [ ] 2.1 Do the other thing

## 3. Frontend button — depends on 1, 2
"""


@pytest.mark.parametrize(
    "name,service,type_,issue,desc",
    [
        ("budget-feat-313-excel-export", "budget", "feat", 313, "excel-export"),
        ("shared-feat-292-audit-mixin", "shared", "feat", 292, "audit-mixin"),
        ("budget-feat-customer-profile-cache", "budget", "feat", None, "customer-profile-cache"),
        ("users-fix-2fa-enrolment", "users", "fix", None, "2fa-enrolment"),
    ],
)
def test_parse_change(name, service, type_, issue, desc):
    change = flow.parse_change(name)
    assert (change.service, change.type, change.issue, change.desc) == (service, type_, issue, desc)


@pytest.mark.parametrize(
    "name", ["ai-provider-model-catalog-api", "async-privileged-access-audit", "nope-feat-x"]
)
def test_parse_change_rejects_non_conforming(name):
    assert flow.parse_change(name, strict=False) is None
    with pytest.raises(SystemExit):
        flow.parse_change(name)


def test_parse_groups_reads_numbers_titles_and_issues():
    groups = flow.parse_groups(TASKS.splitlines())
    assert [g.number for g in groups] == [1, 2, 3]
    assert [g.issue for g in groups] == [316, 318, None]
    assert groups[1].title == "Dashboard sheet — depends on 1"
    assert groups[1].github_title == "Dashboard sheet"


def test_subissue_title_drops_the_depends_suffix():
    change = flow.parse_change("budget-feat-313-excel-export")
    group = flow.parse_groups(TASKS.splitlines())[1]
    assert flow.subissue_title(change, group) == "excel-export: Dashboard sheet (group 2)"


def test_branch_name():
    change = flow.parse_change("budget-feat-313-excel-export")
    group = flow.parse_groups(TASKS.splitlines())[0]
    assert flow.branch_name(change, group) == "Budget/feat/Issue-316/excel-export-group1"


def _write(tmp_path, monkeypatch, text=TASKS):
    monkeypatch.chdir(tmp_path)
    change = flow.parse_change("budget-feat-313-excel-export")
    change.tasks_file.parent.mkdir(parents=True)
    change.tasks_file.write_text(text)
    return change


def test_write_tasks_inserts_tracking_block_before_the_first_group(tmp_path, monkeypatch):
    change = _write(tmp_path, monkeypatch)
    lines = flow.read_tasks(change)
    groups = flow.parse_groups(lines)
    flow.write_tasks(change, lines, groups, {316: "closed", 318: "open"})

    out = change.tasks_file.read_text()
    assert out.index(flow.TRACK_START) < out.index("## 1.")
    assert "| 1. Export endpoint scaffolding | [#316]" in out
    assert "`Budget/feat/Issue-316/excel-export-group1`" in out
    assert "| 3. Frontend button | — | — | not created |" in out
    assert "Workflow rule:" in out
    assert "\n\n\n" not in out, "tracking block left a blank-line run behind"


def test_write_tasks_is_idempotent_and_replaces_a_stale_block(tmp_path, monkeypatch):
    change = _write(tmp_path, monkeypatch)
    for states in ({316: "closed", 318: "open"}, {316: "closed", 318: "closed"}):
        lines = flow.read_tasks(change)
        groups = flow.parse_groups(lines)
        flow.write_tasks(change, lines, groups, states)

    out = change.tasks_file.read_text()
    assert out.count(flow.TRACK_START) == 1
    assert out.count("## 1. Export endpoint scaffolding — Issue #316") == 1
    assert "| [#318](" in out and "| closed |" in out


def test_write_tasks_records_newly_created_issue_numbers(tmp_path, monkeypatch):
    change = _write(tmp_path, monkeypatch)
    lines = flow.read_tasks(change)
    groups = flow.parse_groups(lines)
    groups[2].issue = 400
    flow.write_tasks(change, lines, groups, {400: "open"})
    assert "## 3. Frontend button — depends on 1, 2 — Issue #400" in change.tasks_file.read_text()


def test_parse_groups_requires_at_least_one_group():
    with pytest.raises(SystemExit):
        flow.parse_groups(["# Tasks", "", "no groups here"])


def test_write_tasks_refuses_a_half_deleted_tracking_block(tmp_path, monkeypatch):
    damaged = TASKS.replace("# Tasks", f"# Tasks\n\n{flow.TRACK_START}\n## Tracking\n")
    change = _write(tmp_path, monkeypatch, damaged)
    lines = flow.read_tasks(change)
    groups = flow.parse_groups(lines)
    with pytest.raises(SystemExit):
        flow.write_tasks(change, lines, groups, {316: "closed"})
    assert change.tasks_file.read_text() == damaged, "damaged file was rewritten anyway"


def _sub(number, group, state="open", desc="excel-export", title="Thing"):
    return {"number": number, "state": state, "title": f"{desc}: {title} (group {group})"}


def _match(monkeypatch, tasks, subs):
    monkeypatch.setattr(flow, "sub_issues", lambda parent: subs)
    change = flow.parse_change("budget-feat-313-excel-export")
    groups = flow.parse_groups(tasks.splitlines())
    return {n: s["number"] for n, s in flow.match_groups(change, groups).items()}


def test_match_groups_uses_the_title_suffix_when_no_number_is_recorded(monkeypatch):
    tasks = "## 1. A\n\n## 2. B\n"
    assert _match(monkeypatch, tasks, [_sub(316, 1), _sub(318, 2)]) == {1: 316, 2: 318}


def test_match_groups_prefers_the_recorded_number_over_a_stale_suffix(monkeypatch):
    # group 2 was renumbered to 3 in tasks.md; its sub-issue still says "(group 2)"
    tasks = "## 1. A — Issue #316\n\n## 3. B — Issue #318\n"
    assert _match(monkeypatch, tasks, [_sub(316, 1), _sub(318, 2)]) == {1: 316, 3: 318}


def test_match_groups_never_claims_one_sub_issue_twice(monkeypatch):
    # a group left pointing at its neighbour's issue must not steal it
    tasks = "## 1. A — Issue #316\n\n## 2. B — Issue #316\n"
    assert _match(monkeypatch, tasks, [_sub(316, 1), _sub(318, 2)]) == {1: 316, 2: 318}


def test_match_groups_recovers_a_recorded_unlinked_issue(monkeypatch):
    tasks = "## 1. A — Issue #999\n"
    monkeypatch.setattr(flow, "gh_json", Mock(return_value=_sub(999, 1)))
    link = Mock()
    monkeypatch.setattr(flow, "link_sub_issue", link)
    assert _match(monkeypatch, tasks, [_sub(316, 1)]) == {1: 999}
    link.assert_called_once_with(313, 999)


def test_match_groups_leaves_an_unmatched_group_for_creation(monkeypatch):
    tasks = "## 1. A — Issue #316\n\n## 2. B\n"
    assert _match(monkeypatch, tasks, [_sub(316, 1)]) == {1: 316}


def test_change_marker_is_stable_across_the_init_rename():
    before = flow.change_marker(flow.parse_change("budget-feat-excel-export"))
    after = flow.change_marker(flow.parse_change("budget-feat-313-excel-export"))
    assert before == after == "<!-- flow:change:budget-feat-excel-export -->"


@pytest.mark.parametrize("failure", ["link", "board"])
def test_reconcile_retries_without_creating_another_issue(tmp_path, monkeypatch, failure):
    change = _write(tmp_path, monkeypatch, "## 1. A\n")
    subs = []
    monkeypatch.setattr(flow, "sub_issues", lambda parent: list(subs))
    create = Mock(return_value=400)
    monkeypatch.setattr(flow, "create_issue", create)
    monkeypatch.setattr(flow, "gh_json", Mock(return_value=_sub(400, 1)))
    monkeypatch.setattr(flow, "board_ensure", Mock())

    def link(parent, child):
        assert flow.parse_groups(flow.read_tasks(change))[0].issue == child
        subs.append(_sub(child, 1))

    monkeypatch.setattr(flow, "link_sub_issue", Mock(side_effect=SystemExit(1)))
    if failure == "board":
        monkeypatch.setattr(flow, "link_sub_issue", link)
    monkeypatch.setattr(flow, "board_status", Mock(side_effect=SystemExit(1)))
    with pytest.raises(SystemExit):
        flow.reconcile(change, flow.parse_groups(flow.read_tasks(change)))

    monkeypatch.setattr(flow, "link_sub_issue", link)
    states = flow.reconcile(change, flow.parse_groups(flow.read_tasks(change)))
    assert states == {400: "open"}
    assert len(subs) == 1
    create.assert_called_once()


def test_reconcile_stops_when_recorded_issue_cannot_be_linked(tmp_path, monkeypatch):
    change = _write(tmp_path, monkeypatch, "## 1. A — Issue #999\n")
    monkeypatch.setattr(flow, "sub_issues", Mock(return_value=[_sub(316, 1)]))
    monkeypatch.setattr(flow, "gh_json", Mock(return_value=_sub(999, 1)))
    monkeypatch.setattr(flow, "link_sub_issue", Mock(side_effect=SystemExit(1)))
    create = Mock()
    monkeypatch.setattr(flow, "create_issue", create)
    with pytest.raises(SystemExit):
        flow.reconcile(change, flow.parse_groups(flow.read_tasks(change)))
    create.assert_not_called()
    assert flow.parse_groups(flow.read_tasks(change))[0].issue == 999


@pytest.mark.parametrize(
    "siblings,close_parent",
    [
        ([_sub(316, 1), {"number": 318, "title": "Renamed", "state": "open"}], False),
        ([_sub(316, 1)], False),
        ([_sub(318, 2, state="closed")], False),
        ([_sub(316, 1), _sub(318, 2, state="closed")], True),
        ([_sub(316, 1), _sub(318, 2, state="closed"), _sub(320, 3)], False),
    ],
)
def test_pr_closes_parent_only_when_all_groups_are_linked_and_finished(
    tmp_path, monkeypatch, capsys, siblings, close_parent
):
    _write(tmp_path, monkeypatch, "## 1. A — Issue #316\n## 2. B — Issue #318\n")
    monkeypatch.setattr(flow, "sub_issues", Mock(return_value=siblings))
    flow.cmd_pr(SimpleNamespace(branch="Budget/feat/Issue-316/excel-export-group1"))
    lines = capsys.readouterr().out.splitlines()
    assert lines == (["Closes #316", "Closes #313"] if close_parent else ["Closes #316"])
