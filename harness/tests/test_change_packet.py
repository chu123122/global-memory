"""Tests for change_packet.py — validate Change Packet structure."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from textwrap import dedent

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "harness" / "scripts" / "change_packet.py"
TEMPLATE = REPO / "templates" / "change_packet.md.tmpl"


def load_module():
    spec = importlib.util.spec_from_file_location("change_packet", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


cp = load_module()


VALID_PACKET = dedent("""\
    ---
    packet_id: 20260615-120000-test-change
    author: test-agent
    created: 2026-06-15T12:00:00
    risk_tier: 1
    status: submitted
    ---

    # Change Packet: Test change

    ## Motivation (WHY)

    - Fixes a real problem in the codebase
    - Without this fix, tests will keep failing

    ## Scope (WHAT)

    Files to modify:
    - harness/scripts/some_script.py

    Files NOT touched:
    - agents/CLAUDE.md

    New files to create:
    - none

    ## Approach (HOW)

    - Modify the validation logic to handle edge case

    ## Evidence & Verification

    - Pre-implementation: `python -m pytest harness/tests/test_some.py`
    - Post-implementation: `python harness/scripts/quality_gate.py verify --json`

    ## Risks & Rollback

    - Low risk; revert the single file if regression found

    ## Intent Alignment

    - Parent task: test-task-id
    - Does this serve the task's stated goal? Yes, directly fixes the reported bug
""")


def write_packet(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "test-packet.md"
    p.write_text(content, encoding="utf-8")
    return p


class TestValidPacket:
    def test_valid_packet_passes(self, tmp_path):
        path = write_packet(tmp_path, VALID_PACKET)
        result = cp.validate_packet(path)
        assert result["verdict"] == "PASS"
        assert result["errors"] == []
        assert result["kind"] == "change_packet_validation"

    def test_valid_packet_path_in_result(self, tmp_path):
        path = write_packet(tmp_path, VALID_PACKET)
        result = cp.validate_packet(path)
        assert result["path"] == str(path)


class TestMissingFrontmatter:
    def test_missing_packet_id_blocks(self, tmp_path):
        content = VALID_PACKET.replace("packet_id: 20260615-120000-test-change", "")
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "BLOCK"
        assert any("packet_id" in e for e in result["errors"])

    def test_missing_risk_tier_blocks(self, tmp_path):
        content = VALID_PACKET.replace("risk_tier: 1", "")
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "BLOCK"
        assert any("risk_tier" in e for e in result["errors"])

    def test_missing_status_blocks(self, tmp_path):
        content = VALID_PACKET.replace("status: submitted", "")
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "BLOCK"
        assert any("status" in e for e in result["errors"])

    def test_missing_created_blocks(self, tmp_path):
        content = VALID_PACKET.replace("created: 2026-06-15T12:00:00", "")
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "BLOCK"
        assert any("created" in e for e in result["errors"])


class TestInvalidValues:
    def test_invalid_risk_tier_blocks(self, tmp_path):
        content = VALID_PACKET.replace("risk_tier: 1", "risk_tier: 5")
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "BLOCK"
        assert any("risk_tier must be 0-3" in e for e in result["errors"])

    def test_invalid_status_blocks(self, tmp_path):
        content = VALID_PACKET.replace("status: submitted", "status: invalid")
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "BLOCK"
        assert any("Invalid status" in e for e in result["errors"])


class TestMissingSections:
    @pytest.mark.parametrize("section", [
        "Motivation (WHY)",
        "Scope (WHAT)",
        "Approach (HOW)",
        "Evidence & Verification",
        "Risks & Rollback",
        "Intent Alignment",
    ])
    def test_missing_section_blocks(self, tmp_path, section):
        lines = VALID_PACKET.splitlines()
        filtered = []
        skip = False
        for line in lines:
            if line.startswith(f"## {section}"):
                skip = True
                continue
            if skip and line.startswith("## "):
                skip = False
            if not skip:
                filtered.append(line)
        content = "\n".join(filtered)
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "BLOCK"
        assert any(section in e for e in result["errors"])


class TestEmptySections:
    def test_empty_section_in_submitted_blocks(self, tmp_path):
        content = VALID_PACKET.replace(
            "- Fixes a real problem in the codebase\n- Without this fix, tests will keep failing",
            ""
        )
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "BLOCK"
        assert any("Motivation" in e and "no substantive" in e for e in result["errors"])

    def test_empty_section_in_draft_warns(self, tmp_path):
        content = VALID_PACKET.replace("status: submitted", "status: draft").replace(
            "- Fixes a real problem in the codebase\n- Without this fix, tests will keep failing",
            ""
        )
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "PASS"
        assert any("Motivation" in w and "draft" in w for w in result["warnings"])


class TestClaudeMdProtection:
    def test_claude_md_in_scope_without_justification_blocks(self, tmp_path):
        content = VALID_PACKET.replace(
            "Files to modify:\n- harness/scripts/some_script.py",
            "Files to modify:\n- agents/CLAUDE.md"
        ).replace(
            "Files NOT touched:\n- agents/CLAUDE.md",
            "Files NOT touched:\n- none"
        )
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "BLOCK"
        assert any("agents/CLAUDE.md" in e and "justification" in e for e in result["errors"])

    def test_claude_md_with_justification_passes(self, tmp_path):
        content = VALID_PACKET.replace(
            "Files to modify:\n- harness/scripts/some_script.py",
            "Files to modify:\n- agents/CLAUDE.md"
        ).replace(
            "Files NOT touched:\n- agents/CLAUDE.md",
            "Files NOT touched:\n- none"
        )
        content += dedent("""\

            ## Justification for modifying agents/CLAUDE.md

            - Cannot be solved via AGENTS.md alone because the behavioral change
              must apply cross-project to prevent recurring mistakes.
        """)
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "PASS"

    def test_claude_md_in_not_touched_does_not_block(self, tmp_path):
        path = write_packet(tmp_path, VALID_PACKET)
        result = cp.validate_packet(path)
        assert result["verdict"] == "PASS"
        assert not any("agents/CLAUDE.md" in e for e in result["errors"])


class TestEvidenceWarning:
    def test_no_command_in_evidence_warns(self, tmp_path):
        content = VALID_PACKET.replace(
            "- Pre-implementation: `python -m pytest harness/tests/test_some.py`\n"
            "- Post-implementation: `python harness/scripts/quality_gate.py verify --json`",
            "- Manual review of the changes"
        )
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "PASS"
        assert any("command-like" in w for w in result["warnings"])


class TestFileNotFound:
    def test_nonexistent_file_errors(self, tmp_path):
        path = tmp_path / "nonexistent.md"
        result = cp.validate_packet(path)
        assert result["verdict"] == "ERROR"
        assert any("not found" in e.lower() for e in result["errors"])


class TestNewCommand:
    def test_new_creates_packet(self, tmp_path):
        ns = argparse.Namespace(
            title="Fix validation bug",
            task="test-task",
            out=str(tmp_path),
            risk_tier=2,
            json=False,
        )
        ret = cp.cmd_new(ns)
        assert ret == 0
        created = list(tmp_path.glob("*.md"))
        assert len(created) == 1
        content = created[0].read_text(encoding="utf-8")
        assert "Fix validation bug" in content
        assert "risk_tier: 2" in content
        assert "test-task" in content


class TestTemplate:
    def test_template_exists(self):
        assert TEMPLATE.exists()

    def test_template_has_required_sections(self):
        content = TEMPLATE.read_text(encoding="utf-8")
        for section in cp.REQUIRED_SECTIONS:
            assert f"## {section}" in content


class TestTemplatePlaceholderDetection:
    def test_template_draft_warns_not_passes_as_substantive(self, tmp_path):
        """A freshly-created packet from template should warn on all sections in draft."""
        ns = argparse.Namespace(
            title="Test placeholder detection",
            task="test-task",
            out=str(tmp_path),
            risk_tier=1,
            json=False,
        )
        cp.cmd_new(ns)
        created = list(tmp_path.glob("*.md"))
        assert len(created) == 1
        result = cp.validate_packet(created[0])
        assert result["verdict"] == "PASS"
        assert len(result["warnings"]) >= 5, (
            f"Template draft should warn on placeholder sections, got: {result['warnings']}"
        )

    def test_submitted_with_only_template_prompts_blocks(self, tmp_path):
        """A submitted packet with only template question-prompts must BLOCK."""
        ns = argparse.Namespace(
            title="Template prompts only",
            task="test-task",
            out=str(tmp_path),
            risk_tier=1,
            json=False,
        )
        cp.cmd_new(ns)
        created = list(tmp_path.glob("*.md"))
        content = created[0].read_text(encoding="utf-8")
        content = content.replace("status: draft", "status: submitted")
        created[0].write_text(content, encoding="utf-8")
        result = cp.validate_packet(created[0])
        assert result["verdict"] == "BLOCK"
        assert any("no substantive content" in e for e in result["errors"])


class TestScopeHeadingNotContent:
    def test_scope_with_only_headings_blocks_submitted(self, tmp_path):
        """Scope with only 'Files to modify:' heading but no actual paths must BLOCK."""
        content = VALID_PACKET.replace(
            "Files to modify:\n- harness/scripts/some_script.py\n\nFiles NOT touched:\n- agents/CLAUDE.md\n\nNew files to create:\n- none",
            "Files to modify:\n\nFiles NOT touched:\n\nNew files to create:"
        )
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "BLOCK"
        assert any("Scope" in e for e in result["errors"])

    def test_scope_with_real_path_passes(self, tmp_path):
        """Scope with a real file path should pass."""
        path = write_packet(tmp_path, VALID_PACKET)
        result = cp.validate_packet(path)
        assert result["verdict"] == "PASS"

    def test_not_touched_path_does_not_satisfy_scope(self, tmp_path):
        """Files NOT touched entries must not count as files to modify."""
        content = VALID_PACKET.replace(
            "Files to modify:\n- harness/scripts/some_script.py",
            "Files to modify:\n- none"
        )
        path = write_packet(tmp_path, content)
        result = cp.validate_packet(path)
        assert result["verdict"] == "BLOCK"
        assert any("Scope must list files" in e for e in result["errors"])


import argparse  # noqa: E402 (already imported, but needed for type in test)
