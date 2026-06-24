---
packet_id: 20260619-224031-collab-dispatch-dry-run-packet
author: codex-lead
created: 2026-06-19T22:40:31
risk_tier: 2
status: submitted
---

# Change Packet: collab dispatch dry run packet

## Motivation (WHY)

- The replay helper emits a full runbook, but using it still requires the lead to pick one action and manually extract the exact dispatch payload plus the matching state update commands.
- A dry-run dispatch packet makes the workflow more directly usable: select the next dispatch, show the runtime-shaped tool payload, the worker prompt, and the precise state commands for marking running/done/blocked.
- This still avoids automatic worker calls; it is a deterministic bridge between planning and runtime execution.

## Scope (WHAT)

Files to modify:
- `harness/collab/__init__.py`
- `harness/collab/replay.py`
- `harness/capability_manifest.json`
- `docs/capabilities.md`
- `docs/scripts-registry.md`
- `harness/README.md`
- `README.md`
- `skills/collab/v1/SKILL.md`
- `quality/verification.md`

Files NOT touched:
- `harness/client_manifest.json`
- hooks / bootstrap / runtime settings
- `agents/CLAUDE.md`
- `D:/xdt-maker-main/**`
- real worker/session process spawning or tool invocation

New files to create:
- `harness/collab/dispatch.py`
- `harness/scripts/collab_dispatch.py`
- `harness/tests/test_collab_dispatch.py`
- `harness/tests/test_collab_dispatch_cli.py`
- `quality/reviews/collab-dispatch-dry-run/{correctness,test-quality,risk-security,maintainability}.md`

## Approach (HOW)

- Build on replay action cards: select by `--dispatch-id` or default to the first available action, then render a single dispatch packet.
- Keep the packet declarative and dry-run only. It includes the runtime payload and copy/paste guidance but never calls MCP/subagent/Task tools.
- Include paired state update commands so the lead can record execution consistently after using the runtime manually.

## Evidence & Verification

- Pre-implementation: replay/runbook tests are PASS; task docs identify runtime adapter execution as the next layer but still require no automatic spawning.
- Post-implementation: `python -m pytest harness/tests/test_collab_config.py harness/tests/test_collab_plan.py harness/tests/test_collab_adapters.py harness/tests/test_collab_state.py harness/tests/test_collab_state_cli.py harness/tests/test_collab_replay.py harness/tests/test_collab_replay_cli.py harness/tests/test_collab_dispatch.py harness/tests/test_collab_dispatch_cli.py -q`
- Post-implementation: `python harness/scripts/collab_dispatch.py --plan <plan.json> --state <state.json> --json`
- Post-implementation: `python harness/scripts/check_capability_manifest.py --json`
- Post-implementation: path-limited `quality_gate.py verify --review-dir quality/reviews/collab-dispatch-dry-run ... --json`

## Risks & Rollback

- Risk: Users may think `collab_dispatch.py` executes the dispatch. Mitigation: name output `dry_run`, keep `spawns_process=false`, and document it as copy/execute guidance only.
- Risk: Selecting a done dispatch by default could cause repeated work. Mitigation: reuse replay's default done-skipping and require `--include-done` to select completed items.
- Risk: Scope creep toward runtime invocation. Mitigation: no imports from runtime tool namespaces, no subprocess to clients, no hidden state mutation.
- Rollback: remove dispatch module/script/tests/reviews and registry/docs references. Replay/state/plan features remain intact.

## Intent Alignment

- Parent task: xd-maker-agent-collab-standalone
- Yes. It moves the plugin from a runbook toward a practical lead-operated dispatch workflow while preserving the agreed boundary that full lifecycle automation and UI shell are not claimed.
