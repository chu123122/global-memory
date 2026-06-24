---
packet_id: 20260620-020542-collab-phase5-ui-shell-contract
author: codex-worker-sqt3yzub9jibk4obiqwdaq2r
created: 2026-06-20T02:05:42
risk_tier: 2
status: submitted
---

# Change Packet: collab phase5 ui shell contract

## Motivation (WHY)

- Phase 4 provides stable headless plan/state/queue/recover/dispatch artifacts, but Phase 5 still lacks an explicit optional UI shell information architecture and a deterministic headless-to-UI adapter contract.
- Without this slice, future UI/runtime work can bypass state/queue/recover/error contracts or overfit to XDMaker product shell details instead of the host-neutral artifacts.

## Scope (WHAT)

Files to modify:
- `harness/collab/__init__.py`
- `harness/capability_manifest.json`
- `docs/scripts-registry.md`
- `README.md`
- `harness/README.md`
- `examples/collab/README.md`
- `CHANGELOG.md`

Files NOT touched:
- `agents/CLAUDE.md`
- `harness/client_manifest.json`
- `harness/hooks/**`, `bootstrap.py`, runtime settings
- `D:\xdt-maker-main\**`
- `D:\ClaudeTasks\active\xd-maker-agent-collab-standalone\**`

New files to create:
- `harness/collab/ui_shell.py`
- `harness/scripts/collab_ui_shell.py`
- `harness/tests/test_collab_ui_shell.py`
- `harness/tests/test_collab_ui_shell_cli.py`
- `examples/collab/run_ui_shell_flow.py`
- `quality/reviews/collab-phase5/*.md` if quality gate tier requires reviews

## Approach (HOW)

- Build a deterministic UI view model from existing Phase 4 artifacts: plan, optional state, optional queue, optional recovery report, optional dispatch packet, and optional worker report pointers.
- Render the same model as JSON and Markdown dashboard; explicitly encode UI sections, XDMaker reuse/replace boundaries, non-spawning runtime contract, and available operator actions.
- Add CLI smoke and contract tests that prove missing optional artifacts are handled, missing required plan returns stable `error_code`, and UI shell does not bypass state/queue/recover/dispatch contracts.

## Evidence & Verification

- Pre-implementation: Phase 5 design requires P5-1..P5-4; Phase 4 artifacts and tests are stable at 57 collab tests passing.
- Post-implementation: run `python -m pytest <collab tests> -q`; `python examples\collab\run_ui_shell_flow.py --out <tmp>`; `python harness\scripts\check_capability_manifest.py --json`; `python harness\scripts\scan_orphan_scripts.py --strict --json`; `python harness\generate_catalog.py --check --json`; path-limited `python harness\scripts\quality_gate.py verify --review-dir quality\reviews\collab-phase5 ... --json`.

## Risks & Rollback

- Risk: UI shell model overclaims real UI/runtime behavior; mitigated by schema fields that mark `headless=true`, `spawns_process=false`, `readiness=experimental`, and by tests asserting no spawn action.
- Risk: new script becomes unregistered; mitigated by manifest/registry/catalog checks.
- Rollback: remove the new UI shell module/script/tests/example and revert listed manifest/docs changes; no runtime settings, hooks, or client readiness are modified.

## Intent Alignment

- Parent task: xd-maker-agent-collab-standalone
- Does this serve the task's stated goal? yes; it implements Phase 5 as an optional deterministic UI shell contract and regression slice without introducing a real UI build chain or worker spawning.
