# Collab headless examples

These examples are executable and stay headless. They generate JSON artifacts and dashboards without spawning Codex/Claude/Orca workers.

## Minimal Phase 4 flow

Run from the repository root:

```powershell
python examples\collab\run_minimal_flow.py --out .tmp\collab-example
```

Expected artifacts:

- `plan.json`: host-neutral dispatch plan.
- `state.json`: lightweight dispatch state with one intentionally stale running item.
- `queue.json`: host-neutral queue with one leased item.
- `recover.json`: recovery advice for stale running / state-queue conflict.
- `dispatch.json`: one dry-run dispatch packet.

## Optional Phase 5 UI shell view model

```powershell
python examples\collab\run_ui_shell_flow.py --out .tmp\collab-ui-shell-example
```

Additional artifacts:

- `ui-shell.json`: deterministic view model for an optional UI shell.
- `ui-shell.md`: Markdown dashboard showing plan/state/queue/recover/dispatch/report panels.

All runtime payloads keep `spawns_process=false`; operators must manually dispatch workers through the active client and then record progress with `collab_state.py` / `collab_queue.py`. The UI shell model is read-only and must not bypass state, queue, recovery, or error contracts.
