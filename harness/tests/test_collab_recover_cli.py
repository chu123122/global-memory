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


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_recover.py"


class CollabRecoverCliTests(unittest.TestCase):
    def test_cli_outputs_recovery_report_for_stale_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="Recover CLI.")
            state = update_dispatch(
                state_from_plan(plan),
                "01-find",
                status="running",
                worker_id="worker-1",
                updated_at="2026-06-20T00:00:00Z",
            )
            plan_path = Path(tmp) / "plan.json"
            state_path = Path(tmp) / "state.json"
            plan_path.write_text(dumps_plan_json(plan), encoding="utf-8")
            save_state(state, state_path)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--plan",
                    str(plan_path),
                    "--state",
                    str(state_path),
                    "--now",
                    "2026-06-20T02:00:00Z",
                    "--stale-after-seconds",
                    "3600",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "collab_recovery_report")
        self.assertEqual(payload["verdict"], "needs_attention")
        self.assertIn("COLLAB_RECOVER_STALE_RUNNING", [issue["error_code"] for issue in payload["issues"]])

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
        self.assertEqual(payload["kind"], "collab_recover_error")
        self.assertEqual(payload["error_code"], "COLLAB_RECOVER_INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
