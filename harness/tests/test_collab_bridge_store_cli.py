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

HOST = Path(__file__).resolve().parents[1] / "scripts" / "collab_bridge_host.py"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_bridge_store.py"


class CollabBridgeStoreCliTests(unittest.TestCase):
    def test_cli_summarizes_and_snapshots_event_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="Bridge store CLI.")
            blueprint = Path(tmp) / "blueprint.json"
            events = Path(tmp) / "events.jsonl"
            snapshot = Path(tmp) / "session.json"
            blueprint.write_text(dumps_bridge_json(build_worker_launch_blueprint(plan)), encoding="utf-8")
            subprocess.run([sys.executable, str(HOST), "create", "--blueprint", str(blueprint), "--events", str(events), "--worker-limit", "2", "--json"], check=True, text=True, capture_output=True)
            subprocess.run([sys.executable, str(HOST), "send", "--events", str(events), "--worker-id", "worker-01-find", "--message", "Map files", "--json"], check=True, text=True, capture_output=True)

            summary = subprocess.run([sys.executable, str(SCRIPT), "summary", "--events", str(events), "--json"], check=True, text=True, capture_output=True)
            snap = subprocess.run([sys.executable, str(SCRIPT), "snapshot", "--events", str(events), "--out", str(snapshot), "--json"], check=True, text=True, capture_output=True)
            replay = subprocess.run([sys.executable, str(SCRIPT), "replay", "--snapshot", str(snapshot), "--json"], check=True, text=True, capture_output=True)

        summary_payload = json.loads(summary.stdout)
        snap_payload = json.loads(snap.stdout)
        replay_payload = json.loads(replay.stdout)
        self.assertEqual(summary_payload["kind"], "collab_bridge_store_summary")
        self.assertEqual(snap_payload["kind"], "collab_bridge_snapshot_written")
        self.assertEqual(replay_payload["kind"], "collab_bridge_host_model")

    def test_cli_missing_events_uses_stable_error_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(SCRIPT), "summary", "--events", str(Path(tmp) / "missing.jsonl"), "--json"], text=True, capture_output=True, check=False)

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["kind"], "collab_bridge_store_error")
        self.assertEqual(payload["error_code"], "COLLAB_BRIDGE_STORE_INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
