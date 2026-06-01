# Public Changelog

This file is the public release-history surface for the external source scope.
The local `CHANGELOG.md` is a private audit log and is intentionally excluded
from the default source export.

## Unreleased

- Added an OSS-readiness profile that aggregates capability coverage, client
  scope, hook alignment, publish scope, source export, path configuration,
  hardcoded-path checks, output contracts, and smoke verification.
- Added a machine-readable capability manifest and human-readable capabilities
  guide so every harness script has an explicit capability owner and status.
- Added client and hook manifests to keep external-client promises and runtime
  hook wiring aligned with the bootstrap output.
- Added a publish-scope manifest, source export plan, and external source safety
  scan to separate public runtime/docs from private memory and task context.
- Added a release issue ledger that classifies remaining work by owner,
  remediation type, and machine-readable decision or tracking plan.
