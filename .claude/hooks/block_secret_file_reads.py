#!/usr/bin/env python3
"""PreToolUse hook (Bash): blocks any command referencing a known secret-bearing file."""
import json
import re
import sys

SECRET_FILES = [".devrc", ".env", ".env.github-secrets", ".env.ovh-secrets.prod"]
BOUNDARY = r"(?:^|[\s/\"'`])"
END_BOUNDARY = r"(?:$|[\s/\"'`])"
PATTERN = re.compile(
    BOUNDARY + "(" + "|".join(re.escape(f) for f in SECRET_FILES) + ")" + END_BOUNDARY
)


def main():
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")

    match = PATTERN.search(command)
    if not match:
        return

    filename = match.group(1)
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Blocked: command references {filename}, a real-secret-bearing file "
                        "(gitignored, unlike the committed .env.*.dev/.env.*.local templates). "
                        "Do not cat/grep/sed/head/tail or otherwise print its contents. Use a "
                        "presence-only check instead (e.g. `grep -c '^VARNAME=' " + filename + "`"
                        ", which confirms a key exists without ever printing its value), or ask "
                        "the user directly."
                    ),
                }
            }
        )
    )


if __name__ == "__main__":
    main()
