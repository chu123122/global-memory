# Codex Adapter

This section overrides Claude Code-only wording in the shared Work Mode source below.

- Use PowerShell-compatible commands and absolute Windows paths when examples are ambiguous.
- Use `apply_patch` for manual file edits.
- Request sandbox escalation for writes outside the workspace, network-dependent commands, GUI launches, or commands blocked by sandboxing.
- Do not rely on Claude Code-only statusline, hooks, or subagents.
- Treat hooks such as `doc_gate.py` as validation context only; Codex must run explicit checks instead of assuming hooks fired.
- Prefer direct implementation when the user explicitly asks to proceed.
- For new tasks, use `python C:\Users\XINDONG\.claude\scripts\create_task.py <task-id> "<display-name>" --summary "<one-line requirement>"`.
- For context, use `python C:\Users\XINDONG\.claude\scripts\work_context_pack.py --task <task-id-or-path> --json --write-status`.
- Validation should run the available explicit commands: `work_context_pack.py`, `verify_conventions.py`, and `task_complete.py`.
