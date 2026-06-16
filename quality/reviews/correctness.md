Verdict: PASS

Blocking:
- none

Warnings:
- none

Missing tests:
- none

Confidence: high
Need human decision:
- none

Notes:
- Capability assignments follow existing manifest semantics: `readback_audit.py` is diagnostic, `check_phase_evidence.py` and `change_packet.py` support task/work governance, and `task_experience_index.py` supports memory repository maintenance.
- Prompt verifier change is intentionally in the verifier, not `agents/CLAUDE.md`, because the missing old sections were migrated out of the slim global behavior contract.
- `rules/Untitled.md` was a personal prompt, not a repository rule; removing the single untracked file is the least invasive cleanup.
