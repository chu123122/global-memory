Verdict: PASS

Blocking:
- none

Warnings:
- none

Missing tests:
- none

Red-Evidence:
- `pytest harness/tests/test_triage_inbox.py -q` after adding verify-close tests but before implementation produced 6 failures because argparse rejected `--verify-close`; the 5 existing scan tests still passed.
- After implementing `--verify-close`, the same command produced 11 passed.

Mutation:
- Removing the `--verify-close` argparse branch is killed by all six new verify-close tests.
- Allowing `open` issue or `active` feedback to pass is killed by `test_verify_close_fails_open_issue_without_close_record` and `test_verify_close_fails_active_feedback`.
- Removing evidence keyword enforcement is killed by `test_verify_close_fails_closed_issue_without_evidence`.
- Requiring only status but not reason for drop/supersede would weaken intent; reason-positive PASS cases are covered, and failure behavior for no evidence is covered through issue/active paths.
- Changing default scan schema is killed by existing `test_json_output_contract_is_stable`.

Confidence: high
Need human decision:
- none
