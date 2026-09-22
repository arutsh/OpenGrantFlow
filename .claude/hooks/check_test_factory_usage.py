#!/usr/bin/env python3
"""PostToolUse hook: nudge a touched test file toward factory_boy over hand-rolled fixtures."""

import json
import re
import sys
from pathlib import Path

MAX_FILE_BYTES = 2 * 1024 * 1024
FACTORY_DEF_RE = re.compile(
    r"class\s+(\w+)\(factory\.\w+\):\s*class Meta:\s*model\s*=\s*(\w+)", re.DOTALL
)


def _factories_dir_for(file_path: Path):
    for parent in file_path.parents:
        if parent.name == "tests" and (parent / "factories").is_dir():
            return parent / "factories"
    return None


def _model_to_factory_map(factories_dir: Path) -> dict:
    mapping: dict = {}
    for factory_file in factories_dir.glob("*.py"):
        try:
            text = factory_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for factory_name, model_name in FACTORY_DEF_RE.findall(text):
            mapping.setdefault(model_name, factory_name)
    return mapping


def find_violations(text: str, model_to_factory: dict):
    violations = []

    if re.search(r"\bmake_valid_user\(", text):
        violations.append(
            "make_valid_user(...) — decided convention: it stays for untouched tests, "
            "but files being touched should switch to ValidUserFactory."
        )

    for model_name, factory_name in model_to_factory.items():
        if re.search(rf"(?<!class )(?<!\w){model_name}\(", text):
            violations.append(
                f"raw {model_name}(...) construction — {factory_name} already exists for this "
                f"model, prefer {factory_name}.build(...)."
            )

    return violations


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or (payload.get("tool_response") or {}).get("filePath")
    if not file_path or not file_path.endswith(".py"):
        return 0

    path = Path(file_path)
    if "tests" not in path.parts or "factories" in path.parts:
        return 0

    factories_dir = _factories_dir_for(path)
    if not factories_dir:
        return 0

    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return 0
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0

    model_to_factory = _model_to_factory_map(factories_dir)
    violations = find_violations(text, model_to_factory)
    if not violations:
        return 0

    warning = f"Test factory check: {file_path} — " + " | ".join(violations)
    print(warning, file=sys.stderr)
    print(
        json.dumps(
            {
                "systemMessage": warning,
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": warning,
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
