Verdict: PASS

Blocking:
- none

Warnings:
- none

Missing tests:
- none

Red-Evidence:
- Before cleanup, `triage_inbox.py --json` reported 2 open issues and 15 active feedback items.
- After cleanup, the two issues and `feedback_diff_workflow.md` each pass `triage_inbox.py --verify-close <path> --json`; `triage_inbox.py --json` reports only 14 active feedback items and no open issues.

Mutation:
- Reverting either issue status to `open` would make it reappear in `triage_inbox.py --json`.
- Reverting `feedback_diff_workflow.md` to `active` would make it reappear in the feedback inbox.
- Removing any close/routing/defer evidence would be caught by `triage_inbox.py --verify-close` as missing evidence.

Confidence: high
Need human decision:
- none
