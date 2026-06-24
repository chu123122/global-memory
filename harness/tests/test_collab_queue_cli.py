import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan, dumps_plan_json  # noqa: E402


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_queue.py"


class CollabQueueCliTests(unittest.TestCase):
    def test_cli_create_and_lease_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="Queue CLI.")
            plan_path = Path(tmp) / "plan.json"
            queue_path = Path(tmp) / "queue.json"
            plan_path.write_text(dumps_plan_json(plan), encoding="utf-8")

            create = subprocess.run(
                [sys.executable, str(SCRIPT), "create", "--plan", str(plan_path), "--queue", str(queue_path), "--json"],
                text=True,
                capture_output=True,
                check=True,
            )
            lease = subprocess.run(
                [sys.executable, str(SCRIPT), "lease", "--queue", str(queue_path), "--worker-id", "worker-1", "--now", "2026-06-20T00:00:00Z", "--json"],
                text=True,
                capture_output=True,
                check=True,
            )

        self.assertEqual(json.loads(create.stdout)["kind"], "collab_queue_summary")
        payload = json.loads(lease.stdout)
        self.assertEqual(payload["kind"], "collab_queue_lease")
        self.assertEqual(payload["item"]["dispatch_id"], "01-find")
        self.assertEqual(payload["item"]["status"], "leased")

    def test_cli_requeue_missing_lease_uses_stable_error_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="Queue CLI error.")
            plan_path = Path(tmp) / "plan.json"
            queue_path = Path(tmp) / "queue.json"
            plan_path.write_text(dumps_plan_json(plan), encoding="utf-8")
            subprocess.run([sys.executable, str(SCRIPT), "create", "--plan", str(plan_path), "--queue", str(queue_path)], check=True)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "requeue", "--queue", str(queue_path), "--lease-id", "missing", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["kind"], "collab_queue_error")
        self.assertEqual(payload["error_code"], "COLLAB_QUEUE_LEASE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
