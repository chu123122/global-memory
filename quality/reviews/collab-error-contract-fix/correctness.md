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
- Shared `error_payload()` now emits `ok:false`, `kind`, `error`, `error_code`, `message`, and object `details` while preserving compatibility fields.
- All collab CLIs already route JSON error output through the shared helper, so the fix remains centralized.
