import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan, dumps_plan_json  # noqa: E402
from collab.queue import save_queue, queue_from_plan  # noqa: E402
from collab.recover import build_recovery_report, dumps_recovery_json  # noqa: E402
from collab.state import save_state, state_from_plan  # noqa: E402


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_ui_shell.py"


class CollabUiShellCliTests(unittest.TestCase):
    def test_cli_outputs_json_view_model_from_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="UI CLI.")
            state = state_from_plan(plan)
            queue = queue_from_plan(plan)
            recovery = build_recovery_report(plan=plan, state=state, queue=queue, now="2026-06-20T00:00:00Z")
            plan_path = Path(tmp) / "plan.json"
            state_path = Path(tmp) / "state.json"
            queue_path = Path(tmp) / "queue.json"
            recover_path = Path(tmp) / "recover.json"
            plan_path.write_text(dumps_plan_json(plan), encoding="utf-8")
            save_state(state, state_path)
            save_queue(queue, queue_path)
            recover_path.write_text(dumps_recovery_json(recovery), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--plan",
                    str(plan_path),
                    "--state",
                    str(state_path),
                    "--queue",
                    str(queue_path),
                    "--recover",
                    str(recover_path),
                    "--report",
                    "01-find=paths.md",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "collab_ui_shell_model")
        self.assertFalse(payload["contract"]["spawns_process"])
        self.assertEqual(payload["dispatch_rows"][0]["report_pointer"], "paths.md")

    def test_cli_outputs_markdown_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="UI CLI markdown.")
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(dumps_plan_json(plan), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--plan", str(plan_path)],
                text=True,
                capture_output=True,
                check=True,
            )

        self.assertIn("# Collaboration UI Shell Dashboard", result.stdout)
        self.assertIn("spawns_process: `false`", result.stdout)

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
        self.assertEqual(payload["kind"], "collab_ui_shell_error")
        self.assertEqual(payload["error_code"], "COLLAB_UI_SHELL_INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
