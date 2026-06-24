import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_worker_supervisor.py"


class CollabWorkerSupervisorCliTests(unittest.TestCase):
    def test_scenario_writes_replayable_event_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = Path(tmp) / "supervisor.jsonl"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "scenario", "--events", str(events), "--message", "hello", "--json", "--", sys.executable, "-u", "-c", "import sys; print('ready', flush=True); print('echo:'+sys.stdin.readline().strip(), flush=True)"],
                check=True,
                text=True,
                capture_output=True,
            )
            snap = subprocess.run([sys.executable, str(SCRIPT), "snapshot", "--events", str(events), "--json"], check=True, text=True, capture_output=True)

        payload = json.loads(result.stdout)
        snapshot = json.loads(snap.stdout)
        self.assertEqual(payload["kind"], "collab_worker_supervisor_scenario")
        self.assertGreaterEqual(payload["events_written"], 5)
        self.assertIn("echo:hello", snapshot["worker_rows"][0]["stdout"])

    def test_crash_scenario_reports_crashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = Path(tmp) / "crash.jsonl"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "crash-scenario", "--events", str(events), "--json", "--", sys.executable, "-u", "-c", "import sys; print('boom', flush=True); sys.exit(3)"],
                check=True,
                text=True,
                capture_output=True,
            )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["snapshot"]["worker_rows"][0]["status"], "crashed")

    def test_timeout_scenario_reports_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = Path(tmp) / "timeout.jsonl"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "timeout-scenario", "--events", str(events), "--timeout-seconds", "0.1", "--sleep", "0.25", "--json", "--", sys.executable, "-u", "-c", "import time; time.sleep(5)"],
                check=True,
                text=True,
                capture_output=True,
            )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["snapshot"]["worker_rows"][0]["status"], "timeout")


if __name__ == "__main__":
    unittest.main()
