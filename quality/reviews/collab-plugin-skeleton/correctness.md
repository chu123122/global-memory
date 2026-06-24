Verdict: PASS

Blocking:
- none

Warnings:
- `harness/collab` currently generates dispatch plans only; real worker spawning remains a later adapter/runtime phase and must not be claimed as implemented.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Review notes:
- `harness/collab/config.py` validates schema version, required five agents, duplicate names, reasoning effort, client, permission mode, and stop policy before plan generation.
- `harness/collab/plan.py` produces deterministic sections and stable agent order; tests cover prompt sections and host-neutral payload constraints.
- `harness/scripts/collab_plan.py` is read-only by default and only emits JSON/Markdown or validates config.
