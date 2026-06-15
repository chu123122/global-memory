Verdict: PASS

Blocking:
- none

Warnings:
- none

Missing tests:
- none

Confidence: high
Need human decision:
- none

Red-Evidence:
- Before running `bootstrap.py install`, `check_hook_alignment.py --json` reported `runtime_not_in_bootstrap` for `hooks/diff_show.py`, proving the check detects the stale runtime hook.
- After install, the same check with `--strict --json` passed with `verdict=aligned`.

Mutation:
- Re-adding `hooks/diff_show.py` to runtime settings without manifest support is killed by `check_hook_alignment.py --strict --json`.
- Re-adding `hooks/diff_show.py` to `harness/hook_manifest.json` without registry/docs alignment would be visible in hook alignment/reconcile checks.
- Leaving runtime settings unchanged is killed by the direct settings grep that must print `False` for `diff_show.py`.
