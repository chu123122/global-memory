import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan, dumps_plan_json  # noqa: E402
from collab.state import save_state, state_from_plan, update_dispatch  # noqa: E402


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_dispatch.py"


class CollabDispatchCliTests(unittest.TestCase):
    def test_cli_outputs_first_available_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="CLI dispatch.")
            plan_path = Path(tmp) / "plan.json"
            state_path = Path(tmp) / "state.json"
            plan_path.write_text(dumps_plan_json(plan), encoding="utf-8")
            save_state(update_dispatch(state_from_plan(plan), "01-find", status="done"), state_path)

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--plan", str(plan_path), "--state", str(state_path), "--json"],
                text=True,
                capture_output=True,
                check=True,
            )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["kind"], "collab_dispatch_packet")
        self.assertEqual(payload["dispatch_id"], "02-designer")
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["runtime_payload"]["spawns_process"], False)

    def test_cli_selects_specific_dispatch_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="CLI specific.")
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(dumps_plan_json(plan), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--plan",
                    str(plan_path),
                    "--dispatch-id",
                    "03-dev",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=True,
            )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["dispatch_id"], "03-dev")
        self.assertEqual(payload["agent"], "dev")

    def test_cli_errors_when_filter_has_no_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="No manual.")
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(dumps_plan_json(plan), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--plan", str(plan_path), "--adapter", "manual", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(payload["kind"], "collab_dispatch_error")
        self.assertIn("no available actions", payload["error"])


if __name__ == "__main__":
    unittest.main()
