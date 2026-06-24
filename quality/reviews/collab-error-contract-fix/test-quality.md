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

Red-Evidence:
- Updated `test_collab_error_contract_cli.py` failed before implementation: 7 failures on missing `ok/message/details` across plan/state/replay/dispatch/queue/recover/ui_shell JSON errors.

Mutation:
- Removing `ok:false`, changing `message != error`, or making `details` non-object is killed by shared `assert_error_contract()`.
- A CLI bypassing `error_payload()` for JSON errors is killed by per-CLI subprocess assertions for plan/state/replay/dispatch/queue/recover/ui_shell.
