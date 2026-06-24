Verdict: PASS

Blocking:
- none

Warnings:
- Tests intentionally use generated plan/state JSON and subprocess CLI smoke; actual worker runtime calls remain out of scope for this non-spawning slice.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Red-Evidence:
- `test_collab_replay.py` and `test_collab_replay_cli.py` would fail before this slice because `collab/replay.py` and `collab_replay.py` did not exist.
- Plan/state mismatch rejection would fail if replay ignored stale state.
- Adapter filtering tests would fail if replay could not focus the action list by runtime.

Mutation:
- Removing done filtering is killed by `test_runbook_skips_done_dispatches_by_default`.
- Removing plan/state mismatch validation is killed by `test_runbook_rejects_state_plan_mismatch`.
- Removing state update command rendering is killed by CLI/action-card tests that assert `collab_state.py` command text is present.
