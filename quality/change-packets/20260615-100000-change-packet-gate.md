---
packet_id: 20260615-100000-change-packet-gate
author: worker-ib503uvyiiif9z95mg5jcjdr
created: 2026-06-15T10:00:00
risk_tier: 2
status: submitted
---

# Change Packet: Implement Change Packet pre-implementation gate

## Motivation (WHY)

- The `/work` discussion phase lacks a strong intent-alignment gate before implementation begins, allowing wrong-direction tasks to absorb new goals (recorded in ISSUE-2026-06-15-work-discussion-before-implementation-gap.md).
- Maintenance changes to `~/.claude/global-memory` affect all projects via shared harness/hooks/rules; a pre-implementation intent/scope check provides traceable justification before touching shared infrastructure.
- Without this, implementation may proceed with incorrect boundaries, pollute `agents/CLAUDE.md`, or create orphan scripts without registry/docs updates.

## Scope (WHAT)

Files to modify:
- AGENTS.md (add Maintenance Gate adapter section)
- docs/scripts-registry.md (register change_packet.py)
- docs/guide/CONTRIBUTING.md (add section 3.7)
- CHANGELOG.md (audit entry)

Files NOT touched:
- agents/CLAUDE.md (cross-project behavioral contract, must not be modified)
- harness/hooks/ (no hook installation in this phase)
- bootstrap.py (no deployment changes)

New files to create:
- templates/change_packet.md.tmpl
- harness/scripts/change_packet.py
- harness/tests/test_change_packet.py
- quality/change-packets/ (directory)

## Approach (HOW)

- Deterministic validation script (R8: code validates structure, AI only drafts content)
- Template + CLI pattern matching existing `quality_gate.py` style
- Adapter/overlay framing: gate is local to this repo's maintenance workflow, layered on top of global CLAUDE.md and default /work; does not replace or modify either
- Graduated strictness: draft allows empty sections (WARN); submitted requires all fields (BLOCK)
- CLAUDE.md protection: any packet scoping `agents/CLAUDE.md` without justification is hard-BLOCKed

## Evidence & Verification

- Pre-implementation: Phase 1 design review approved with constraints (see `design/Phase1-design-review-result.md`)
- Post-implementation: `python -m pytest harness/tests/test_change_packet.py -q` (28 tests)
- Post-implementation: `python harness/scripts/change_packet.py validate quality/change-packets/20260615-100000-change-packet-gate.md --json`
- Post-implementation: `python harness/scripts/quality_gate.py verify --path <changed files> --json`
- Deterministic checks: placeholder detection, frontmatter validation, section presence, scope file listing

## Risks & Rollback

- Over-bureaucracy for trivial changes: mitigated by Tier 0 docs-only being low-cost (template fill minimal) and draft allowing iterative fill
- Rubber-stamp risk: validation checks substance (not just presence); template prompts and placeholders are explicitly rejected for submitted packets
- Script maintenance burden: ~220 LOC, zero dependencies beyond stdlib, registered in scripts-registry, covered by unit tests and smoke-test
- Rollback: delete new files + revert AGENTS.md/registry/CONTRIBUTING edits; no hook or deployment to unwind

## Intent Alignment

- Parent task: global-memory-entry-pr-gate
- Does this serve the task's stated goal? Yes: the task's objective is "接入式入口 prompt + PR-shaped 改动过滤机制" — this implements the PR-shaped gate as a local adapter that records motivation/scope/evidence before modifying this repo's shared infrastructure.
