Verdict: PASS

Blocking:
- none

Warnings:
- If future runtime adapters start auto-updating state, keep this CLI as the deterministic recovery/manual path rather than embedding tool-call logic here.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Maintainability notes:
- The CLI is a thin wrapper over `state.py`; business rules remain in the reusable library.
- Registry/docs changes attach `collab_state.py` to the existing experimental collab capability instead of adding another capability bucket.
- Existing `collab_plan.py` behavior is unchanged; state update is a separate command with a narrow surface.
