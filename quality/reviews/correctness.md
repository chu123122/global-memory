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
- `--verify-close` is independent from default scan; no default output contract changed.
- The implementation is read-only: it resolves/reads one source file and emits JSON/text; it does not edit issue/feedback files or any ledger.
- Unsupported paths, missing files, open/active status, missing evidence, and missing drop/supersede reason all result in `verdict=FAIL` and exit 1.
- The gate deliberately checks mechanical closure evidence only, matching the task boundary.
