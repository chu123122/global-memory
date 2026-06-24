Verdict: PASS

Blocking:
- none

Warnings:
- Runbooks include full worker prompts and adapter payloads; if prompts contain sensitive task data, store generated runbooks in the task workspace rather than broad shared locations.

Missing tests:
- none

Confidence: high
Need human decision:
- none

Risk notes:
- No network access, credential handling, hook mutation, bootstrap mutation, or worker process invocation is introduced.
- The helper reads explicit plan/state paths and writes only stdout.
- State update examples are inert text; the lead must intentionally run `collab_state.py` or a runtime tool.
