#!/usr/bin/env python3
"""PreToolUse hook (Write/Edit): blocks a new multi-line comment block before it's written."""
import ast
import io
import json
import re
import sys
import tokenize
from collections import Counter

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
DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def comment_runs(numbered_lines, marker):
    """Yield (first_lineno, text) for each run of more than MAX_CONSECUTIVE comment lines."""
    run = []
    for lineno, line in numbered_lines + [(None, "")]:
        stripped = line.strip()
        is_comment = stripped.startswith(marker) and not stripped.startswith(marker * 3)
        if is_comment and (not run or run[-1][0] + 1 == lineno):
            run.append((lineno, stripped))
            continue
        if len(run) > MAX_CONSECUTIVE:
            yield run[0][0], "\n".join(t for _, t in run)
        run = [(lineno, stripped)] if is_comment else []


def regex_violations(ext, text):
    found = []
    marker = LINE_COMMENT_STYLES.get(ext)
    if marker:
        found += comment_runs(list(enumerate(text.splitlines(), 1)), marker)

    patterns = []
    if ext in BLOCK_COMMENT_EXTS:
        patterns.append(r"/\*.*?\*/")
    if ext == ".py":
        patterns.append(r'("{3}|\'{3})(.*?)\1')
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.DOTALL):
            if m.group(0).count("\n") + 1 > MAX_BLOCK_LINES:
                found.append((text.count("\n", 0, m.start()) + 1, m.group(0)))
    return found


def python_violations(text, file_path):
    """Use tokenize/ast so string literals aren't mistaken for comments or docstrings."""
    tree = ast.parse(text)
    comments = [
        (tok.start[0], tok.string)
        for tok in tokenize.generate_tokens(io.StringIO(text).readline)
        if tok.type == tokenize.COMMENT and tok.line.strip().startswith("#")
    ]
    found = list(comment_runs(comments, "#"))

    is_migration = "/migrations/versions/" in file_path
    for node in ast.walk(tree):
        if not isinstance(node, DOCSTRING_OWNERS) or not node.body:
            continue
        if isinstance(node, ast.Module) and is_migration:
            continue  # Alembic's generated Revision ID/Revises header
        first = node.body[0]
        if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            continue
        if first.end_lineno - first.lineno + 1 > MAX_BLOCK_LINES:
            found.append((first.lineno, first.value.value.strip()))
    return found


def violations(ext, text, file_path):
    if ext == ".py":
        try:
            return python_violations(text, file_path)
        except (SyntaxError, tokenize.TokenError, ValueError):
            pass
    return regex_violations(ext, text)


def before_and_after(tool_name, tool_input, file_path):
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            before = f.read()
    except OSError:
        before = ""

    if tool_name == "Write":
        return before, tool_input.get("content", "")
    if tool_name == "Edit":
        old, new = tool_input.get("old_string", ""), tool_input.get("new_string", "")
        if not before or old not in before:
            return "", new
        count = -1 if tool_input.get("replace_all") else 1
        return before, before.replace(old, new, count)
    return None, None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    if "." not in file_path.rsplit("/", 1)[-1]:
        return

    ext = "." + file_path.rsplit(".", 1)[-1].lower()
    if ext not in LINE_COMMENT_STYLES and ext not in BLOCK_COMMENT_EXTS:
        return

    before, after = before_and_after(tool_name, tool_input, file_path)
    if after is None:
        return

    existing = Counter(text for _, text in violations(ext, before, file_path))
    introduced = []
    for lineno, text in violations(ext, after, file_path):
        if existing[text] > 0:
            existing[text] -= 1
        else:
            introduced.append((lineno, text))
    if not introduced:
        return

    lineno, text = introduced[0]
    preview = text.splitlines()[0][:80]
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Blocked: this {tool_name} to {file_path} introduces a multi-line comment "
                f"at line {lineno} ({preview!r}): more than {MAX_BLOCK_LINES} lines, or more "
                f"than {MAX_CONSECUTIVE} consecutive comment lines. Trim it to one or two "
                "lines; longer rationale belongs in the commit message, PR description, or docs."
            ),
        }
    }))


if __name__ == "__main__":
    main()
