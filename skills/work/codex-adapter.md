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

## Work runner explicit commands

Codex must not wire the work runner to a global `UserPromptSubmit` hook; ordinary chat must not auto-trigger runner checks. Use these only for explicit `/work check`, `/work run --worker codex-exec`, or `/work repair --worker codex-exec` requests. `/work check` is diagnostic and does not count as a repair attempt; `/work repair --worker codex-exec` starts at most 3 codex-exec workers, and if the 3rd verifier still fails the runner writes `failure_code=WORK_RUNNER_REPAIR_LIMIT_REACHED`, marks `status=blocked`, and waits for human handling.

`/work check` PowerShell template (verifier-only; no Codex worker):

```powershell
python ~/.claude/global-memory\harness\scripts\work_runner.py check `
  --run-root D:\ClaudeTasks\active\<task-id>\ops\work-runner `
  --task-id <task-id> `
  --step <phase-id> `
  --repo-root ~/.claude/global-memory `
  --verifier-command '["python","~/.claude/global-memory\\harness\\work_context_pack.py","--task","<task-id>","--json"]' `
  --verifier-command '["python","~/.claude/global-memory\\harness\\verify\\verify_conventions.py","D:\\ClaudeTasks\\active\\<task-id>"]' `
  --verifier-command '["python","~/.claude/global-memory\\harness\\scripts\\check_phase_evidence.py","--task","D:\\ClaudeTasks\\active\\<task-id>"]' `
  --json
```

`/work run --worker codex-exec` PowerShell template (worker repairs from `gate-feedback.json`, then verifier decides):

```powershell
python ~/.claude/global-memory\harness\scripts\work_runner.py run `
  --worker codex-exec `
  --run-root D:\ClaudeTasks\active\<task-id>\ops\work-runner `
  --task-id <task-id> `
  --step <phase-id> `
  --repo-root ~/.claude/global-memory `
  --verifier-command '["python","~/.claude/global-memory\\harness\\work_context_pack.py","--task","<task-id>","--json"]' `
  --verifier-command '["python","~/.claude/global-memory\\harness\\verify\\verify_conventions.py","D:\\ClaudeTasks\\active\\<task-id>"]' `
  --verifier-command '["python","~/.claude/global-memory\\harness\\scripts\\check_phase_evidence.py","--task","D:\\ClaudeTasks\\active\\<task-id>"]' `
  --json
```


`/work repair --worker codex-exec` PowerShell template (bounded repair loop; requires existing `gate-feedback.json` with `gate=process-fail`; max 3 repair attempts):

```powershell
python ~/.claude/global-memory\harness\scripts\work_runner.py repair `
  --worker codex-exec `
  --run-root D:\ClaudeTasks\active\<task-id>\ops\work-runner `
  --task-id <task-id> `
  --step <phase-id> `
  --repo-root ~/.claude/global-memory `
  --verifier-command '["python","D:\\\\global-memory\\\\harness\\\\work_context_pack.py","--task","<task-id>","--json"]' `
  --verifier-command '["python","D:\\\\global-memory\\\\harness\\\\verify\\\\verify_conventions.py","D:\\\\ClaudeTasks\\\\active\\\\<task-id>"]' `
  --verifier-command '["python","D:\\\\global-memory\\\\harness\\\\scripts\\\\check_phase_evidence.py","--task","D:\\\\ClaudeTasks\\\\active\\\\<task-id>"]' `
  --json
```
