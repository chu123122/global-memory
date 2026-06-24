Verdict: PASS

Blocking:
- none

Warnings:
- Adapter payloads are declarative runtime-shaped data; they must not be documented as proof that Codex/Claude/Orca worker creation has been implemented.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Review notes:
- `harness/collab/adapters.py` keeps `spawns_process=false` and returns tool-shaped dictionaries only.
- `harness/collab/state.py` validates schema version, dispatch IDs, statuses, and JSON roundtrip without introducing a database or host dependency.
- `harness/scripts/collab_plan.py` preserves existing plan output and adds opt-in `--adapter-payloads` / `--state-out` behavior.
