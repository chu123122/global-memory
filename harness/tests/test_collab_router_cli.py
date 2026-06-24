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

HOST_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_bridge_host.py"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_router.py"


def _create_events(tmp: str) -> Path:
    plan = build_dispatch_plan(load_config(), intent="Phase 11 router CLI.")
    blueprint_path = Path(tmp) / "blueprint.json"
    events_path = Path(tmp) / "events.jsonl"
    blueprint_path.write_text(dumps_bridge_json(build_worker_launch_blueprint(plan)), encoding="utf-8")
    subprocess.run([sys.executable, str(HOST_SCRIPT), "create", "--blueprint", str(blueprint_path), "--events", str(events_path), "--worker-limit", "1", "--json"], check=True, text=True, capture_output=True)
    return events_path


class CollabRouterCliTests(unittest.TestCase):
    def test_enqueue_ack_snapshot_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _create_events(tmp)
            queued = subprocess.run([sys.executable, str(SCRIPT), "enqueue", "--events", str(events), "--worker-id", "worker-01-find", "--message", "hello", "--correlation-id", "corr-cli", "--dedupe-key", "dedupe-cli", "--json"], check=True, text=True, capture_output=True)
            message_id = json.loads(queued.stdout)["result"]["message_id"]
            acked = subprocess.run([sys.executable, str(SCRIPT), "ack", "--events", str(events), "--message-id", message_id, "--json"], check=True, text=True, capture_output=True)
            snapshot = subprocess.run([sys.executable, str(SCRIPT), "snapshot", "--events", str(events), "--json"], check=True, text=True, capture_output=True)

        self.assertEqual(json.loads(acked.stdout)["result"]["status"], "acked")
        snap_payload = json.loads(snapshot.stdout)
        self.assertEqual(snap_payload["kind"], "collab_router_snapshot")
        self.assertEqual(snap_payload["summary"]["acked"], 1)

    def test_duplicate_cli_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _create_events(tmp)
            base = [sys.executable, str(SCRIPT), "enqueue", "--events", str(events), "--worker-id", "worker-01-find", "--message", "hello", "--dedupe-key", "dup", "--json"]
            subprocess.run(base, check=True, text=True, capture_output=True)
            duplicate = subprocess.run(base, check=True, text=True, capture_output=True)

        payload = json.loads(duplicate.stdout)
        self.assertEqual(payload["result"]["status"], "duplicate_detected")
        self.assertTrue(payload["result"]["duplicate"])
        self.assertEqual(payload["snapshot"]["summary"]["duplicates"], 1)

    def test_invalid_message_id_has_stable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _create_events(tmp)
            result = subprocess.run([sys.executable, str(SCRIPT), "ack", "--events", str(events), "--message-id", "missing", "--json"], check=False, text=True, capture_output=True)

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["kind"], "collab_router_error")
        self.assertEqual(payload["error_code"], "COLLAB_ROUTER_INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
