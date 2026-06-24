Verdict: PASS

Blocking:
- none

Warnings:
- The replay runbook emits action cards and example commands only; it does not prove that any runtime worker has executed them.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Review notes:
- `harness/collab/replay.py` validates plan shape and plan/state ID alignment before producing action cards.
- Done dispatches are skipped by default and can be included explicitly for audit with `--include-done`.
- Runtime payloads are reused from the non-spawning adapter contract, so replay does not introduce hidden dispatch behavior.
