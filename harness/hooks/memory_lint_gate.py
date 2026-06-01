#!/usr/bin/env python3
"""
memory_lint_gate.py — PreToolUse Write|Edit|MultiEdit hook

Gate frontmatter on $env:GLOBAL_MEMORY_DIR/{feedback,knowledge,fixes,decisions,
procedure,reference,interview}/*.md writes.

Reconstructs the post-write content (Write=content, Edit=apply replacement,
MultiEdit=chain replacements), writes to tmp, runs harness_memory_lint, denies
on failure.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _hook_lib import read_hook_input, deny, allow, append_jsonl, now_iso, LOG_DIR

MEMORY_ROOT = Path(os.environ.get("GLOBAL_MEMORY_DIR", str(Path(__file__).resolve().parents[2]))).resolve()
LINTER = MEMORY_ROOT / "harness" / "scripts" / "harness_memory_lint.py"

PATH_RE = re.compile(
    r"[\\/](feedback|knowledge|fixes|decisions|procedure|reference|interview)[\\/][^\\/]+\.md(\.proposed)?$"
)


def in_scope(file_path: str) -> bool:
    norm = file_path.replace("\\", "/").lower()
    root = str(MEMORY_ROOT).replace("\\", "/").lower()
    if not norm.startswith(root):
        return False
    return bool(PATH_RE.search(norm))


def reconstruct(tool: str, tool_input: dict, file_path: str) -> str | None:
    """Return the content that WILL be on disk after this tool call."""
    p = Path(file_path)
    if tool == "Write":
        return tool_input.get("content") or ""
    current = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    if tool == "Edit":
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        if tool_input.get("replace_all"):
            return current.replace(old, new)
        if old in current:
            return current.replace(old, new, 1)
        return None
    if tool == "MultiEdit":
        out = current
        for e in tool_input.get("edits", []):
            o = e.get("old_string", "")
            n = e.get("new_string", "")
            if e.get("replace_all"):
                out = out.replace(o, n)
            elif o in out:
                out = out.replace(o, n, 1)
        return out
    return None


def run_lint(content: str, original_path: str) -> tuple[bool, str]:
    """Write reconstructed content to tmp, lint with --source pointing at the
    real source .md (so .proposed sidecars can resolve body/meta correctly)."""
    suffix = ".md.proposed" if original_path.endswith(".proposed") else ".md"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=suffix, delete=False
    ) as f:
        f.write(content)
        tmp_path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        cmd = [sys.executable, str(LINTER), tmp_path, "--quiet"]
        if original_path.endswith(".proposed"):
            src_path = original_path[: -len(".proposed")]
            cmd += ["--source", src_path]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10, env=env,
        )
        return proc.returncode == 0, (proc.stdout or proc.stderr).strip()
    except Exception as e:
        return True, f"lint skipped: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def main():
    data = read_hook_input()
    tool = data.get("tool_name", "")
    if tool not in ("Write", "Edit", "MultiEdit"):
        allow()

    tin = data.get("tool_input", {}) or {}
    file_path = tin.get("file_path", "")
    if not file_path or not in_scope(file_path):
        allow()

    new_content = reconstruct(tool, tin, file_path)
    if new_content is None:
        # can't reconstruct → allow, let the underlying Edit error itself
        allow()

    ok, report = run_lint(new_content, file_path)
    append_jsonl(LOG_DIR / "memory_lint_gate.jsonl", {
        "ts": now_iso(), "file": file_path, "tool": tool,
        "ok": ok, "report_head": report[:500],
    })
    if not ok:
        deny(
            f"memory_lint_gate BLOCK: {file_path}\n"
            f"frontmatter invalid after this write. Fix and retry:\n"
            f"{report}\n"
            f"Schema: harness/scripts/triggers_vocab.yaml"
        )
    allow()


if __name__ == "__main__":
    main()
