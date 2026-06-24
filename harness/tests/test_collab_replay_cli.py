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


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_replay.py"


class CollabReplayCliTests(unittest.TestCase):
    def test_cli_json_outputs_next_actions_from_plan_and_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="CLI replay.")
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

        self.assertEqual(payload["kind"], "collab_replay_runbook")
        self.assertEqual(payload["action_count"], 4)
        self.assertEqual(payload["actions"][0]["dispatch_id"], "02-designer")
        self.assertIn("collab_state.py", payload["actions"][0]["state_update_commands"]["mark running"])

    def test_cli_adapter_filter_outputs_only_matching_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="Filter.")
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(dumps_plan_json(plan), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--plan", str(plan_path), "--adapter", "manual", "--json"],
                text=True,
                capture_output=True,
                check=True,
            )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["action_count"], 0)
        self.assertEqual(payload["adapter_filter"], "manual")

    def test_cli_rejects_missing_plan(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--plan", "missing-plan.json", "--json"],
            text=True,
            capture_output=True,
            check=False,
        )

        payload = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(payload["kind"], "collab_replay_error")
        self.assertIn("failed to read plan", payload["error"])


if __name__ == "__main__":
    unittest.main()
