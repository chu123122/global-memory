import unittest
from pathlib import Path
import shutil

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import quality_gate as qg  # noqa: E402


class QualityGateClassificationTests(unittest.TestCase):
    def config(self):
        return qg.DEFAULT_CONFIG_DATA

    def test_docs_only_is_tier0(self):
        changes = qg.ChangeSet(files={"docs/example.md"}, added_lines=5)
        plan = qg.classify(changes, self.config())
        self.assertEqual(plan["tier"], 0)
        self.assertFalse(plan["requires_test_evidence"])

    def test_harness_code_is_tier2(self):
        changes = qg.ChangeSet(files={"harness/foo.py"}, added_lines=50)
        plan = qg.classify(changes, self.config())
        self.assertEqual(plan["tier"], 2)
        self.assertIn("correctness", plan["required_reviews"])
        self.assertTrue(plan["requires_test_evidence"])

    def test_hook_code_is_tier3(self):
        changes = qg.ChangeSet(files={"harness/hooks/dangerous_command_blocker.py"}, added_lines=20)
        plan = qg.classify(changes, self.config())
        self.assertEqual(plan["tier"], 3)
        self.assertEqual(plan["required_reviews"], list(qg.REVIEW_KINDS))
        self.assertTrue(plan["requires_human_decision"])

    def test_large_diff_promotes_to_tier3(self):
        changes = qg.ChangeSet(files={f"src/file_{i}.py" for i in range(12)}, added_lines=900)
        plan = qg.classify(changes, self.config())
        self.assertEqual(plan["tier"], 3)

    def test_pathspec_matching_supports_directory_and_glob(self):
        self.assertTrue(qg.path_matches_pathspecs("harness/scripts/quality_gate.py", ["harness/scripts"]))
        self.assertTrue(qg.path_matches_pathspecs("harness/scripts/quality_gate.py", ["harness/**/*.py"]))
        self.assertFalse(qg.path_matches_pathspecs("README.md", ["harness/scripts"]))


class QualityGateVerifyTests(unittest.TestCase):
    def review_item(self, exists=True, verdict="PASS", errors=None):
        return {
            "exists": exists,
            "verdict": verdict,
            "confidence": "HIGH" if verdict else "",
            "has_block": verdict == "BLOCK",
            "format_errors": errors or [],
            "sections": {},
        }

    def test_tier2_without_test_or_reviews_blocks(self):
        changes = qg.ChangeSet(files={"harness/foo.py"}, added_lines=50)
        plan = qg.classify(changes, qg.DEFAULT_CONFIG_DATA)
        evidence = {
            "changed_tests": [],
            "verification_files": [],
            "verification_mentions_test": False,
            "verification_mentions_human_decision": False,
            "verification_mentions_rollback": False,
            "reviews": {k: self.review_item(exists=False, verdict="") for k in qg.REVIEW_KINDS},
        }
        result = qg.verify_plan(plan, evidence)
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertIn("test-evidence", result["missing"])
        self.assertIn("review:correctness", result["missing"])

    def test_tier2_with_test_and_required_reviews_passes(self):
        changes = qg.ChangeSet(files={"harness/foo.py", "harness/tests/test_foo.py"}, added_lines=80)
        plan = qg.classify(changes, qg.DEFAULT_CONFIG_DATA)
        evidence = {
            "changed_tests": ["harness/tests/test_foo.py"],
            "verification_files": ["quality/verification.md"],
            "verification_mentions_test": True,
            "verification_mentions_human_decision": False,
            "verification_mentions_rollback": False,
            "reviews": {k: self.review_item(exists=k in {"correctness", "test-quality"}, verdict="PASS") for k in qg.REVIEW_KINDS},
        }
        result = qg.verify_plan(plan, evidence)
        self.assertEqual(result["verdict"], "PASS")

    def test_review_format_errors_block_required_review(self):
        changes = qg.ChangeSet(files={"harness/foo.py", "harness/tests/test_foo.py"}, added_lines=80)
        plan = qg.classify(changes, qg.DEFAULT_CONFIG_DATA)
        evidence = {
            "changed_tests": ["harness/tests/test_foo.py"],
            "verification_files": ["quality/verification.md"],
            "verification_mentions_test": True,
            "verification_mentions_human_decision": False,
            "verification_mentions_rollback": False,
            "reviews": {k: self.review_item(exists=k in {"correctness", "test-quality"}, verdict="PASS") for k in qg.REVIEW_KINDS},
        }
        evidence["reviews"]["correctness"] = self.review_item(exists=True, verdict="PASS", errors=["missing confidence"])
        result = qg.verify_plan(plan, evidence)
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertIn("review-format:correctness", result["missing"])

    def test_parse_review_result_rejects_prompt_template(self):
        parsed = qg.parse_review_result(qg.review_prompt("correctness", {
            "plan": {"tier": 2, "label": "behavior", "reasons": ["test"]},
            "change_summary": {"changed_lines": 10, "sample_files": ["harness/foo.py"]},
        }))
        self.assertEqual(parsed["verdict"], "")
        self.assertIn("invalid verdict `PASS / WARN / BLOCK`", parsed["format_errors"])
        self.assertIn("invalid confidence `HIGH / MEDIUM / LOW`", parsed["format_errors"])

    def test_parse_review_result_accepts_filled_review(self):
        text = """Verdict: WARN

Blocking:
- none

Warnings:
- harness/foo.py:10
- risk

Missing tests:
- behavior
- unit
- needed

Confidence: medium
Need human decision:
- none
"""
        parsed = qg.parse_review_result(text)
        self.assertEqual(parsed["verdict"], "WARN")
        self.assertEqual(parsed["confidence"], "MEDIUM")
        self.assertEqual(parsed["format_errors"], [])

    def test_block_review_requires_blocking_item(self):
        text = """Verdict: BLOCK

Blocking:
- 

Warnings:
- none

Missing tests:
- behavior

Confidence: high
Need human decision:
- none
"""
        parsed = qg.parse_review_result(text)
        self.assertIn("BLOCK verdict requires at least one Blocking item", parsed["format_errors"])

    def test_review_pack_writes_required_files(self):
        changes = qg.ChangeSet(files={"harness/foo.py"}, added_lines=50)
        report = {
            "plan": qg.classify(changes, qg.DEFAULT_CONFIG_DATA),
            "change_summary": {"changed_lines": 50, "sample_files": ["harness/foo.py"]},
        }
        tmp = Path(__file__).resolve().parent / "_tmp_quality_gate"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            written = qg.write_review_pack(report, tmp)
            names = sorted(Path(p).name for p in written)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(names, ["correctness.md", "test-quality.md"])


if __name__ == "__main__":
    unittest.main()
