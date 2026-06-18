Verdict: PASS

Blocking:
- none

Warnings:
- `intent_bank.json` is verbose but intentionally human-reviewable for Phase 1; avoid growing it into full curation before Phase 1 go/no-go.
- `measure_intent_bank.py` is standalone rather than integrated into `cli.py`, which keeps production untouched but means usage is documented through task evidence rather than a stable public CLI.

Missing tests:
- none

Confidence: medium
Need human decision:
- none
