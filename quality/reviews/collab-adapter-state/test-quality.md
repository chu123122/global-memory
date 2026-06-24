Verdict: PASS

Blocking:
- none

Warnings:
- CLI state writing is tested through a subprocess smoke and state module roundtrip; no real runtime adapter is exercised because this slice intentionally does not dispatch workers.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Red-Evidence:
- `test_collab_adapters.py` would fail before this slice because `build_adapter_payloads` did not exist.
- `test_collab_state.py` would fail before this slice because `harness/collab/state.py` did not exist.
- Existing `test_cli_json_smoke_outputs_dispatches` protects the original `collab_plan.py --json` behavior while new smoke checks cover the adapter/state flags.

Mutation:
- Removing `spawns_process=false` from payloads is killed by adapter tests.
- Allowing arbitrary dispatch statuses is killed by `test_update_dispatch_rejects_unknown_status_and_id`.
- Dropping stable `plan_id` generation is killed by `test_plan_id_is_stable_for_same_inputs` and the state tests that bind state to plan ID.
