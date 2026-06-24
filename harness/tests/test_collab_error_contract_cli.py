import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan, dumps_plan_json  # noqa: E402
from collab.queue import queue_from_plan, save_queue  # noqa: E402


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def assert_error_contract(testcase: unittest.TestCase, payload: dict, *, kind: str, code: str, contains: str | None = None) -> None:
    testcase.assertIs(payload.get("ok"), False)
    testcase.assertEqual(payload["kind"], kind)
    testcase.assertEqual(payload["error_code"], code)
    testcase.assertIsInstance(payload.get("error"), str)
    testcase.assertIsInstance(payload.get("message"), str)
    testcase.assertEqual(payload["message"], payload["error"])
    testcase.assertIsInstance(payload.get("details"), dict)
    if contains:
        testcase.assertIn(contains, payload["message"])


class CollabErrorContractCliTests(unittest.TestCase):
    def test_plan_cli_config_error_has_complete_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_config = Path(tmp) / "bad.json"
            bad_config.write_text("{not-json", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "collab_plan.py"), "--config", str(bad_config), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        assert_error_contract(self, payload, kind="collab_plan_error", code="COLLAB_CONFIG_INVALID")

    def test_state_cli_error_has_complete_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "collab_state.py"), "--state", str(Path(tmp) / "missing.json"), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        assert_error_contract(self, payload, kind="collab_state_error", code="COLLAB_STATE_INVALID", contains="failed to read state")

    def test_replay_cli_error_has_complete_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "collab_replay.py"), "--plan", str(Path(tmp) / "missing.json"), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        assert_error_contract(self, payload, kind="collab_replay_error", code="COLLAB_REPLAY_INVALID")

    def test_dispatch_cli_error_has_complete_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="Dispatch error contract.")
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(dumps_plan_json(plan), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "collab_dispatch.py"),
                    "--plan",
                    str(plan_path),
                    "--adapter",
                    "manual",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        assert_error_contract(self, payload, kind="collab_dispatch_error", code="COLLAB_DISPATCH_INVALID")

    def test_queue_cli_error_has_complete_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_dispatch_plan(load_config(), intent="Queue error contract.")
            queue_path = Path(tmp) / "queue.json"
            save_queue(queue_from_plan(plan), queue_path)
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "collab_queue.py"), "requeue", "--queue", str(queue_path), "--lease-id", "missing", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        assert_error_contract(self, payload, kind="collab_queue_error", code="COLLAB_QUEUE_LEASE_NOT_FOUND")

    def test_recover_cli_error_has_complete_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "collab_recover.py"), "--plan", str(Path(tmp) / "missing.json"), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        assert_error_contract(self, payload, kind="collab_recover_error", code="COLLAB_RECOVER_INVALID_INPUT")

    def test_ui_shell_cli_error_has_complete_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "collab_ui_shell.py"), "--plan", str(Path(tmp) / "missing.json"), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        assert_error_contract(self, payload, kind="collab_ui_shell_error", code="COLLAB_UI_SHELL_INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
