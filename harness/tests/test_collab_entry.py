import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.entry import build_product_runbook, build_readiness_report, build_xdmaker_like_readiness_report, run_product_smoke, run_xdmaker_like_smoke  # noqa: E402


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_entry.py"


class CollabEntryTests(unittest.TestCase):
    def test_runbook_declares_stable_entry_without_readiness_mutation(self):
        runbook = build_product_runbook()

        self.assertEqual(runbook["kind"], "collab_product_runbook")
        self.assertIn("collab_entry.py smoke", runbook["entry_command"])
        self.assertIn("harness/client_manifest.json readiness", runbook["does_not_modify"])

    def test_readiness_report_is_honest_not_ready(self):
        report = build_readiness_report(runtime_smoke=True)

        self.assertEqual(report["kind"], "collab_readiness_report")
        self.assertEqual(report["verdict"], "not_ready")
        self.assertFalse(report["client_manifest_readiness_changed"])
        blockers = {item["name"] for item in report["checks"] if item["status"] == "blocker"}
        self.assertIn("codex_claude_e2e", blockers)
        self.assertIn("real_mcp_registration", blockers)

    def test_product_smoke_writes_artifacts_without_spawn_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_product_smoke(tmp)
            artifacts = {key: Path(value) for key, value in payload["artifacts"].items()}

            self.assertFalse(payload["allow_spawn"])
            self.assertEqual(payload["readiness"]["verdict"], "not_ready")
            for name in ["plan", "blueprint", "events", "store_summary", "router_snapshot", "readiness"]:
                self.assertTrue(artifacts[name].exists(), name)
            self.assertNotIn("runtime_result", artifacts)
            self.assertEqual(payload["materialized"]["summary"]["router_message_count"], 1)

    def test_product_smoke_with_explicit_spawn_records_runtime_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_product_smoke(tmp, allow_spawn=True, command=[sys.executable, "-c", "print('entry worker')"])
            artifacts = {key: Path(value) for key, value in payload["artifacts"].items()}

            self.assertTrue(payload["allow_spawn"])
            self.assertTrue(artifacts["runtime_result"].exists())
            runtime = json.loads(artifacts["runtime_result"].read_text(encoding="utf-8"))
            self.assertEqual(runtime["status"], "done")
            self.assertTrue(payload["materialized"]["contract"]["real_worker_lifecycle"])



    def test_xdmaker_like_readiness_can_reach_experimental_ready_with_evidence(self):
        report = build_xdmaker_like_readiness_report(
            real_worker_e2e=True,
            supervisor=True,
            mcp_server=True,
            mcp_registration=True,
            mcp_tool_call=True,
            web_ui=True,
            persistence=True,
            claude_blocked=True,
        )

        self.assertEqual(report["kind"], "collab_xdmaker_like_readiness_report")
        self.assertEqual(report["verdict"], "experimental_ready")
        self.assertEqual(report["summary"]["blocker"], 0)
        self.assertEqual(report["summary"]["warning"], 1)

    def test_xdmaker_like_smoke_folds_in_real_evidence_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.json"
            real.write_text(json.dumps({"result": {"real_cli_e2e_verified": True}}), encoding="utf-8")
            mcp = Path(tmp) / "mcp-list.json"
            mcp.write_text(json.dumps([{"name": "global-memory-collab-bridge", "enabled": True}]), encoding="utf-8")
            claude = Path(tmp) / "claude.json"
            claude.write_text(json.dumps({"classification": {"runtime": "claude", "status": "blocked_budget"}}), encoding="utf-8")
            payload = run_xdmaker_like_smoke(Path(tmp) / "out", real_worker_evidence=real, mcp_registration_evidence=mcp, claude_blocker_evidence=claude)

        self.assertEqual(payload["kind"], "collab_xdmaker_like_smoke")
        self.assertEqual(payload["readiness"]["verdict"], "experimental_ready")


class CollabEntryCliTests(unittest.TestCase):
    def test_cli_runbook_and_readiness(self):
        runbook = subprocess.run([sys.executable, str(SCRIPT), "runbook", "--json"], check=True, text=True, capture_output=True)
        readiness = subprocess.run([sys.executable, str(SCRIPT), "readiness", "--runtime-smoke", "--json"], check=True, text=True, capture_output=True)

        self.assertEqual(json.loads(runbook.stdout)["kind"], "collab_product_runbook")
        report = json.loads(readiness.stdout)
        self.assertEqual(report["verdict"], "not_ready")
        self.assertFalse(report["client_manifest_readiness_changed"])


    def test_cli_xdmaker_readiness(self):
        result = subprocess.run([
            sys.executable,
            str(SCRIPT),
            "xdmaker-readiness",
            "--real-worker-e2e",
            "--supervisor",
            "--mcp-server",
            "--mcp-registration",
            "--mcp-tool-call",
            "--web-ui",
            "--persistence",
            "--json",
        ], check=True, text=True, capture_output=True)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["verdict"], "experimental_ready")

    def test_cli_smoke_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(SCRIPT), "smoke", "--out", tmp, "--json"], check=True, text=True, capture_output=True)
            payload = json.loads(result.stdout)

        self.assertEqual(payload["kind"], "collab_product_entry_smoke")
        self.assertEqual(payload["readiness"]["verdict"], "not_ready")
        self.assertIn("readiness", payload["artifacts"])


if __name__ == "__main__":
    unittest.main()
