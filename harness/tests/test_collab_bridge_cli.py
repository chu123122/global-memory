import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan, dumps_plan_json  # noqa: E402


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_bridge.py"


class CollabBridgeCliTests(unittest.TestCase):
    def test_cli_outputs_bridge_spec_with_worker_blueprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="Bridge CLI.")
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(dumps_plan_json(plan), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--plan", str(plan_path), "--json"],
                text=True,
                capture_output=True,
                check=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "collab_standalone_bridge_bundle")
        self.assertEqual(payload["spec"]["kind"], "collab_standalone_bridge_spec")
        self.assertEqual(payload["worker_launch_blueprint"]["kind"], "collab_worker_launch_blueprint")
        self.assertFalse(payload["worker_launch_blueprint"]["spawns_process_now"])

    def test_cli_outputs_markdown_spec(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("# Standalone Collaboration Bridge", result.stdout)
        self.assertIn("wraps_or_replaces_lead_cli: `false`", result.stdout)
        self.assertIn("create_worker", result.stdout)

    def test_cli_missing_plan_uses_stable_error_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--plan", str(Path(tmp) / "missing.json"), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["kind"], "collab_bridge_error")
        self.assertEqual(payload["error_code"], "COLLAB_BRIDGE_INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
