#!/usr/bin/env python3
"""PreToolUse hook (Bash): blocks manual branch creation that bypasses scripts/start-group.sh."""
import json
import re
import sys

# git checkout -b/-B <name>, git switch -c/-C <name>, or bare git branch <name>
CREATE_RE = re.compile(
    r"\bgit\s+(?:checkout\s+-[bB]|switch\s+-[cC]|branch)\s+(?:--\s+)?(\S+)"
)
# <Service>/<type>/Issue-<sub-issue>/<description>, see docs/development/WORKFLOW.md §2
VALID_BRANCH_RE = re.compile(r"^[A-Z][A-Za-z]*/(feat|fix|chore|refactor)/Issue-[0-9]+/.+$")


def main():
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")

    match = CREATE_RE.search(command)
    if not match:
        return

    name = match.group(1).strip("'\"")
    if name.startswith("-"):
        return  # a flag (e.g. `git branch -d foo`), not a branch name

    if VALID_BRANCH_RE.match(name):
        return

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Blocked: manual branch creation with name '{name}', which doesn't "
                        "match <Service>/<type>/Issue-<n>/<description>. Branches must be "
                        "created via `scripts/start-group.sh <change-name> <group-number>` "
                        "(docs/development/WORKFLOW.md) so the sub-issue gets created and "
                        "linked. Do not skip it, even for small/chore work."
                    ),
                }
            }
        )
    )


if __name__ == "__main__":
    main()
