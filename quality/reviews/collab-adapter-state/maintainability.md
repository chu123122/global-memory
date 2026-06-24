Verdict: PASS

Blocking:
- none

Warnings:
- If runtime-specific payloads grow beyond simple tool-shaped dictionaries, split each adapter into its own module before adding complex branching.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Maintainability notes:
- `state.py` is intentionally independent from `config.py` and `plan.py` except for consuming a plan dictionary, which keeps it usable for future adapters.
- CLI additions are opt-in flags, so existing `collab_plan.py` callers keep the same default behavior.
- Registry/docs updates keep the new `collab/state.py` file assigned to the existing experimental capability instead of creating another capability bucket.
