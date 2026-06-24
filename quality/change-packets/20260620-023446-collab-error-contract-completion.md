---
packet_id: 20260620-023446-collab-error-contract-completion
author: codex-worker-sqt3yzub9jibk4obiqwdaq2r
created: 2026-06-20T02:34:46
risk_tier: 2
status: submitted
---

# Change Packet: collab error contract completion

## Motivation (WHY)

- Reviewer found a blocking mismatch: task docs claim collab CLI JSON errors are additive `ok=false,error_code,message,details`, but implementation only returned `kind/error/error_code`.
- Without fixing the shared contract, downstream UI/recovery tooling cannot reliably distinguish successful payloads from error payloads or attach structured diagnostics.

## Scope (WHAT)

Files to modify:
- `harness/collab/errors.py`
- `harness/tests/test_collab_errors.py`
- `harness/tests/test_collab_error_contract_cli.py`
- existing collab CLI tests as needed for queue/recover/ui shell error assertions
- `CHANGELOG.md`

Files NOT touched:
- `agents/CLAUDE.md`
- `harness/client_manifest.json`
- `harness/hooks/**`, `bootstrap.py`, runtime settings
- `D:\xdt-maker-main\**`

New files to create:
- `quality/reviews/collab-error-contract-fix/*.md` if quality gate tier requires reviews

## Approach (HOW)

- Strengthen the shared `error_payload()` helper so every collab CLI using it emits `ok:false`, `kind`, `error`, `error_code`, `message`, and object `details` while preserving old fields.
- Keep all success JSON outputs unchanged.
- Add tests over plan/state/replay/dispatch/queue/recover/ui_shell JSON error outputs to prevent future drift.

## Evidence & Verification

- Pre-implementation: reviewer FAIL identifies exact mismatch; all collab CLIs already route JSON errors through shared `error_payload()`.
- Post-implementation: run `python -m pytest harness\tests\test_collab_errors.py harness\tests\test_collab_error_contract_cli.py harness\tests\test_collab_queue_cli.py harness\tests\test_collab_recover_cli.py harness\tests\test_collab_ui_shell_cli.py -q`; run all collab tests; run path-limited `python harness\scripts\quality_gate.py verify --review-dir quality\reviews\collab-error-contract-fix ... --json`.

## Risks & Rollback

- Risk: adding fields could break consumers that assert exact error payload shape; mitigated by only additive fields and preserving `kind/error/error_code`.
- Rollback: revert `harness/collab/errors.py` and test/changelog updates; no runtime settings or success payloads are changed.

## Intent Alignment

- Parent task: xd-maker-agent-collab-standalone
- Does this serve the task's stated goal? yes; it directly closes the reviewer blocking finding for P4-7 without expanding scope.
