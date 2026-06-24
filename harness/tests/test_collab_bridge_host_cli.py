import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge import build_worker_launch_blueprint, dumps_bridge_json  # noqa: E402
from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_bridge_host.py"


class CollabBridgeHostCliTests(unittest.TestCase):
    def test_cli_creates_session_and_view_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="Bridge host CLI.")
            blueprint_path = Path(tmp) / "blueprint.json"
            events_path = Path(tmp) / "events.jsonl"
            blueprint_path.write_text(dumps_bridge_json(build_worker_launch_blueprint(plan)), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "create", "--blueprint", str(blueprint_path), "--events", str(events_path), "--worker-limit", "2", "--json"],
                text=True,
                capture_output=True,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["kind"], "collab_bridge_host_model")
            self.assertEqual(len(payload["worker_rows"]), 2)
            self.assertTrue(events_path.exists())

    def test_cli_send_and_report_update_persist_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="Bridge host CLI update.")
            blueprint_path = Path(tmp) / "blueprint.json"
            events_path = Path(tmp) / "events.jsonl"
            blueprint_path.write_text(dumps_bridge_json(build_worker_launch_blueprint(plan)), encoding="utf-8")
            subprocess.run([sys.executable, str(SCRIPT), "create", "--blueprint", str(blueprint_path), "--events", str(events_path), "--worker-limit", "2", "--json"], check=True, text=True, capture_output=True)

            send = subprocess.run([sys.executable, str(SCRIPT), "send", "--events", str(events_path), "--worker-id", "worker-01-find", "--message", "Map files", "--json"], check=True, text=True, capture_output=True)
            report = subprocess.run([sys.executable, str(SCRIPT), "report", "--events", str(events_path), "--worker-id", "worker-01-find", "--report", "reports/find.md", "--status", "done", "--json"], check=True, text=True, capture_output=True)

            send_payload = json.loads(send.stdout)
            report_payload = json.loads(report.stdout)
            self.assertEqual(send_payload["worker_rows"][0]["message_count"], 1)
            self.assertEqual(report_payload["worker_rows"][0]["report_pointer"], "reports/find.md")
            self.assertEqual(report_payload["worker_rows"][0]["status"], "done")

    def test_cli_missing_events_uses_stable_error_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "show", "--events", str(Path(tmp) / "missing.jsonl"), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["kind"], "collab_bridge_host_error")
        self.assertEqual(payload["error_code"], "COLLAB_BRIDGE_HOST_INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
