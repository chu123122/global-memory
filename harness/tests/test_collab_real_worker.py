import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge import build_worker_launch_blueprint  # noqa: E402
from collab.bridge_host import create_session_from_blueprint, materialize_bridge_host  # noqa: E402
from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402
from collab.real_worker import (  # noqa: E402
    apply_real_worker_result,
    build_real_worker_command,
    build_real_worker_result,
    classify_real_worker_result,
)


def _session():
    plan = build_dispatch_plan(load_config(), intent="Phase 13 real worker.")
    return create_session_from_blueprint(build_worker_launch_blueprint(plan), worker_limit=1, runtime_mode="fake")


class CollabRealWorkerTests(unittest.TestCase):
    def test_codex_request_uses_ephemeral_read_only_exec(self):
        request = build_real_worker_command(
            "codex",
            "Reply exactly CODEX_WORKER_OK.",
            cwd=Path("D:/tmp/collab"),
            output_file=Path("D:/tmp/collab/codex-last.txt"),
        )

        self.assertEqual(request["kind"], "collab_real_worker_request")
        self.assertEqual(request["runtime"], "codex")
        self.assertIn("exec", request["command"])
        self.assertIn("--ephemeral", request["command"])
        self.assertIn("read-only", request["command"])
        self.assertFalse(request["spawns_process_now"])
        self.assertTrue(request["allow_spawn_required"])

    def test_claude_request_uses_print_json_and_debug_log(self):
        request = build_real_worker_command("claude", "Reply exactly CLAUDE_WORKER_OK.", debug_log="debug.log")

        self.assertEqual(request["runtime"], "claude")
        self.assertIn("--print", request["command"])
        self.assertIn("--output-format", request["command"])
        self.assertIn("json", request["command"])
        self.assertIn("--debug-file", request["command"])

    def test_classifies_ok_when_expected_marker_is_found(self):
        classification = classify_real_worker_result(
            "codex",
            {"exit_code": 0, "stdout": "CODEX_WORKER_OK", "stderr": "", "timed_out": False},
            expected_text="CODEX_WORKER_OK",
        )

        self.assertEqual(classification["status"], "ok")
        self.assertTrue(classification["expected_text_found"])

    def test_classifies_claude_budget_blocker_from_debug_log(self):
        classification = classify_real_worker_result(
            "claude",
            {"exit_code": None, "stdout": "", "stderr": "", "timed_out": True},
            expected_text="CLAUDE_WORKER_OK",
            debug_log_text="API error 429 ExceededBudget: User over budget. Max budget limit reached.",
        )

        self.assertEqual(classification["status"], "blocked_budget")
        self.assertIn("budget", classification["reason"])

    def test_apply_real_worker_result_updates_event_model(self):
        session = _session()
        runtime_result = {
            "worker_id": "worker-01-find",
            "command": ["codex", "exec", "prompt"],
            "exit_code": 0,
            "status": "done",
            "stdout": "CODEX_WORKER_OK",
            "stderr": "",
            "timed_out": False,
            "spawns_process_now": True,
        }
        result = build_real_worker_result("codex", runtime_result, expected_text="CODEX_WORKER_OK")
        session = apply_real_worker_result(session, result, now="2026-06-20T13:00:00Z")
        model = materialize_bridge_host(session)

        self.assertTrue(result["real_cli_e2e_verified"])
        self.assertEqual(result["classification"]["status"], "ok")
        self.assertEqual(model["summary"]["runtime_run_count"], 1)
        self.assertEqual(model["worker_rows"][0]["last_runtime_status"], "done")
        self.assertIn("CODEX_WORKER_OK", model["worker_rows"][0]["report_pointer"])


if __name__ == "__main__":
    unittest.main()
