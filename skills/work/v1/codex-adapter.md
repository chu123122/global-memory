# Codex Adapter

This section overrides Claude Code-only wording in the shared Work Mode source below.

- Use PowerShell-compatible commands and absolute Windows paths when examples are ambiguous.
- Use `apply_patch` for manual file edits.
- Request sandbox escalation for writes outside the workspace, network-dependent commands, GUI launches, or commands blocked by sandboxing.
- Do not rely on Claude Code-only statusline, hooks, or subagents.
- Treat hooks such as `doc_gate.py` as validation context only; Codex must run explicit checks instead of assuming hooks fired.
- 设计审查或设计讨论收敛后，先向用户输出确认摘要并等待用户显式批准，才能实现或派 worker；设计审查是输入，不是授权。
- 用户已明确预授权（如 "直接实现", "不用确认", "just do it", or "proceed"）时可跳过确认门，但必须说明 skip reason。
- For new tasks, use `python C:\Users\XINDONG\.claude\scripts\create_task.py <task-id> "<display-name>" --summary "<one-line requirement>"`.
- For context, use `python C:\Users\XINDONG\.claude\scripts\work_context_pack.py --task <task-id-or-path> --json --write-status`.
- Validation should run the available explicit commands: `work_context_pack.py`, `verify_conventions.py`, and `task_complete.py`.
