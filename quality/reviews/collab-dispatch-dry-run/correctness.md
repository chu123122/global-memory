Verdict: PASS

Blocking:
- none

Warnings:
- `collab_dispatch.py` emits a dry-run packet only; a human/lead must still invoke any runtime tool and verify worker output.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Review notes:
- `harness/collab/dispatch.py` refuses unavailable dispatch IDs and non-spawning invariant violations.
- The packet includes runtime payload, prompt, and state-update commands for exactly one selected action.
- Default selection uses replay's done-skipping behavior, reducing accidental repeat dispatch.
