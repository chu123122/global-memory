import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402
from collab.state import save_state, state_from_plan  # noqa: E402


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_state.py"


class CollabStateCliTests(unittest.TestCase):
    def test_cli_validate_outputs_summary_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            save_state(state_from_plan(build_dispatch_plan(load_config(), intent="CLI validate.")), path)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--state", str(path), "--validate", "--json"],
                text=True,
                capture_output=True,
                check=True,
            )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["kind"], "collab_state_summary")
        self.assertEqual(payload["summary"]["dispatch_count"], 5)
        self.assertEqual(payload["summary"]["status_counts"]["pending"], 5)

    def test_cli_update_overwrites_explicit_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            save_state(state_from_plan(build_dispatch_plan(load_config(), intent="CLI update.")), path)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--state",
                    str(path),
                    "--dispatch-id",
                    "01-find",
                    "--status",
                    "running",
                    "--worker-id",
                    "worker-1",
                    "--session-id",
                    "session-1",
                    "--report",
                    "started",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            raw = json.loads(path.read_text(encoding="utf-8"))

        payload = json.loads(result.stdout)

        self.assertEqual(payload["summary"]["status_counts"]["running"], 1)
        self.assertEqual(raw["dispatches"][0]["status"], "running")
        self.assertEqual(raw["dispatches"][0]["worker_id"], "worker-1")
        self.assertEqual(raw["dispatches"][0]["report"], "started")

    def test_cli_out_writes_copy_without_mutating_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            out = Path(tmp) / "updated.json"
            save_state(state_from_plan(build_dispatch_plan(load_config(), intent="CLI out.")), path)

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--state",
                    str(path),
                    "--out",
                    str(out),
                    "--dispatch-id",
                    "01-find",
                    "--status",
                    "done",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            original = json.loads(path.read_text(encoding="utf-8"))
            updated = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(original["dispatches"][0]["status"], "pending")
        self.assertEqual(updated["dispatches"][0]["status"], "done")

    def test_cli_update_requires_dispatch_id_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            save_state(state_from_plan(build_dispatch_plan(load_config())), path)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--state", str(path), "--dispatch-id", "01-find", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(payload["kind"], "collab_state_error")
        self.assertIn("--dispatch-id and --status", payload["error"])


if __name__ == "__main__":
    unittest.main()
