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
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_worker_runtime.py"


def _create_events(tmp: str) -> Path:
    plan = build_dispatch_plan(load_config(), intent="Phase 9 runtime CLI.")
    blueprint_path = Path(tmp) / "blueprint.json"
    events_path = Path(tmp) / "events.jsonl"
    blueprint_path.write_text(dumps_bridge_json(build_worker_launch_blueprint(plan)), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(HOST_SCRIPT), "create", "--blueprint", str(blueprint_path), "--events", str(events_path), "--worker-limit", "1", "--json"],
        check=True,
        text=True,
        capture_output=True,
    )
    return events_path


class CollabWorkerRuntimeCliTests(unittest.TestCase):
    def test_request_command_does_not_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _create_events(tmp)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "request", "--events", str(events), "--worker-id", "worker-01-find", "--json", "--", sys.executable, "-c", "print('request')"],
                check=True,
                text=True,
                capture_output=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "collab_worker_runtime_request")
        self.assertFalse(payload["spawns_process_now"])
        self.assertTrue(payload["allow_spawn_required"])

    def test_run_without_allow_spawn_returns_stable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _create_events(tmp)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "run", "--events", str(events), "--worker-id", "worker-01-find", "--json", "--", sys.executable, "-c", "print('blocked')"],
                check=False,
                text=True,
                capture_output=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["kind"], "collab_worker_runtime_error")
        self.assertEqual(payload["error_code"], "COLLAB_WORKER_RUNTIME_INVALID_INPUT")
        self.assertIn("allow_spawn", payload["message"])

    def test_run_with_allow_spawn_updates_event_store_and_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _create_events(tmp)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "run", "--events", str(events), "--worker-id", "worker-01-find", "--allow-spawn", "--json", "--", sys.executable, "-c", "print('cli worker report')"],
                check=True,
                text=True,
                capture_output=True,
            )

            payload = json.loads(result.stdout)
            lines = events.read_text(encoding="utf-8").splitlines()

        self.assertEqual(payload["kind"], "collab_worker_runtime_run")
        self.assertTrue(payload["event_log_updated"])
        self.assertEqual(payload["result"]["status"], "done")
        self.assertIn("cli worker report", payload["result"]["stdout"])
        self.assertTrue(payload["materialized"]["contract"]["real_worker_lifecycle"])
        self.assertTrue(any('"worker_runtime_result"' in line for line in lines))


if __name__ == "__main__":
    unittest.main()
