import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_real_worker.py"


class CollabRealWorkerCliTests(unittest.TestCase):
    def test_request_command_outputs_non_spawning_codex_request(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "request", "--runtime", "codex", "--prompt", "Reply exactly CODEX_WORKER_OK.", "--json"],
            check=True,
            text=True,
            capture_output=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "collab_real_worker_request")
        self.assertFalse(payload["spawns_process_now"])
        self.assertIn("codex", payload["command"][0])

    def test_classify_budget_blocker_from_debug_file(self):
        debug = Path(__file__).with_name("_tmp_claude_budget_debug.log")
        debug.write_text("429 ExceededBudget: Max budget limit reached.", encoding="utf-8")
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "classify",
                    "--runtime",
                    "claude",
                    "--timed-out",
                    "--debug-log",
                    str(debug),
                    "--expected-text",
                    "CLAUDE_WORKER_OK",
                    "--json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
        finally:
            debug.unlink(missing_ok=True)

        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "collab_real_worker_classification")
        self.assertEqual(payload["classification"]["status"], "blocked_budget")

    def test_probe_without_allow_spawn_returns_stable_error(self):
        # Use a deliberately missing events file to exercise CLI error contract without starting a real CLI.
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "probe",
                "--events",
                "missing-events.jsonl",
                "--worker-id",
                "worker-01-find",
                "--runtime",
                "codex",
                "--prompt",
                "Reply exactly CODEX_WORKER_OK.",
                "--json",
            ],
            check=False,
            text=True,
            capture_output=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["kind"], "collab_real_worker_error")
        self.assertEqual(payload["error_code"], "COLLAB_REAL_WORKER_INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
