---
packet_id: 20260615-115034-disable-vs-code-diff-popup-hook
author: codex
created: 2026-06-15T11:50:34
risk_tier: 3
status: submitted
---

# Change Packet: Disable VS Code diff popup hook

## Motivation (WHY)

- Stops the PostToolUse hook that automatically opens VS Code diff windows after Write/Edit operations.
- If we do not do this, every edit can continue to pop VS Code and interrupt the user's workflow.

## Scope (WHAT)

Files to modify:
- harness/hook_manifest.json
- bootstrap.py
- docs/hook-chain.md
- docs/主循环与日志地图.md
- docs/scripts-registry.md
- CHANGELOG.md

Files NOT touched:
- `harness/hooks/diff_show.py` implementation; keep it available for history/manual reference.
- `harness/hooks/diff_backup.py`; keep edit backups and manual diff workflows possible.
- memory data, sync chain, and unrelated dirty files already present in the worktree.

New files to create:
- none

## Approach (HOW)

- Remove only the runtime hook registration for `hooks/diff_show.py` from `harness/hook_manifest.json`.
- Re-render Claude settings through `bootstrap.py install` so the currently active runtime stops launching VS Code.
- Mark `diff_show.py` as retained but not registered in human docs/registry; keep `diff_backup.py` as the non-popup safety net.

## Evidence & Verification

- Pre-implementation: `harness/hooks/diff_show.py` is the only hook that launches `code --diff`; `harness/hook_manifest.json` registers it under `PostToolUse:Write|Edit`.
- Post-implementation:
  - `python bootstrap.py install`
  - `python harness\scripts\check_hook_alignment.py --strict --json`
  - `python bootstrap.py check`
  - targeted grep/JSON check that runtime settings no longer include `hooks/diff_show.py`.

## Risks & Rollback

- Risk: docs/registry drift from manifest/runtime if only settings are edited.
- Risk: removing `diff_show.py` entirely would break manual references; this change keeps the file and disables only runtime registration.
- Rollback: restore the `PostToolUse Write|Edit` manifest entry for `hooks/diff_show.py`, rerun `python bootstrap.py install`, and update docs/registry back.

## Intent Alignment

- Parent task: hook-diff-show-disable
- Does this serve the task's stated goal? yes; the user asked to disable the hook that pops VS Code after file modifications.
