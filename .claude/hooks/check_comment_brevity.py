#!/usr/bin/env python3
"""PostToolUse hook: flags multi-line comment blocks in a just-written/edited file."""
import json
import re
import sys

LINE_COMMENT_STYLES = {
    ".ts": "//", ".tsx": "//", ".js": "//", ".jsx": "//",
    ".go": "//", ".java": "//", ".c": "//", ".cpp": "//",
    ".h": "//", ".hpp": "//", ".rs": "//",
    ".py": "#", ".sh": "#", ".yml": "#", ".yaml": "#", ".rb": "#",
}
BLOCK_COMMENT_EXTS = {
    ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".c", ".cpp", ".h", ".hpp", ".rs", ".css",
}
MAX_CONSECUTIVE = 2  # 3+ consecutive same-style comment lines triggers a flag
MAX_BLOCK_LINES = 2  # a /* */ or docstring spanning more than this triggers a flag
MAX_FILE_BYTES = 2 * 1024 * 1024


def _line_at(text, offset):
    return text.count("\n", 0, offset) + 1


def find_violations(ext, text):
    lines = text.splitlines()
    violations = []

    marker = LINE_COMMENT_STYLES.get(ext)
    if marker:
        run_start = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(marker) and not stripped.startswith(marker * 3):
                if run_start is None:
                    run_start = i
            else:
                if run_start is not None and i - run_start > MAX_CONSECUTIVE:
                    violations.append((run_start + 1, i))
                run_start = None
        if run_start is not None and len(lines) - run_start > MAX_CONSECUTIVE:
            violations.append((run_start + 1, len(lines)))

    if ext in BLOCK_COMMENT_EXTS:
        for m in re.finditer(r"/\*.*?\*/", text, re.DOTALL):
            if m.group(0).count("\n") + 1 > MAX_BLOCK_LINES:
                violations.append((_line_at(text, m.start()), _line_at(text, m.end())))

    if ext == ".py":
        for m in re.finditer(r'("""|\'\'\')(.*?)\1', text, re.DOTALL):
            if m.group(0).count("\n") + 1 > MAX_BLOCK_LINES:
                violations.append((_line_at(text, m.start()), _line_at(text, m.end())))

    return sorted(set(violations))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or (payload.get("tool_response") or {}).get("filePath")
    if not file_path or "." not in file_path.rsplit("/", 1)[-1]:
        return 0

    ext = "." + file_path.rsplit(".", 1)[-1].lower()
    if ext not in LINE_COMMENT_STYLES and ext not in BLOCK_COMMENT_EXTS:
        return 0

    try:
        import os
        if os.path.getsize(file_path) > MAX_FILE_BYTES:
            return 0
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except OSError:
        return 0

    violations = find_violations(ext, text)
    if not violations:
        return 0

    ranges = ", ".join(f"L{a}-{b}" if a != b else f"L{a}" for a, b in violations)
    warning = (
        f"Comment brevity check: {file_path} has a multi-line comment block at {ranges}. "
        "Trim it to one short line; move any longer rationale to a memory file instead."
    )
    print(warning, file=sys.stderr)
    print(json.dumps({
        "systemMessage": warning,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": warning,
        },
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
