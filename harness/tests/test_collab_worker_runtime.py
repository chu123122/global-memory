import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge import build_worker_launch_blueprint  # noqa: E402
from collab.bridge_host import create_session_from_blueprint, materialize_bridge_host  # noqa: E402
from collab.config import load_config  # noqa: E402
from collab.errors import code_for_exception  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402
from collab.worker_runtime import (  # noqa: E402
    WorkerRuntimeError,
    apply_runtime_result,
    build_worker_runtime_request,
    run_worker_command,
)


def _session():
    plan = build_dispatch_plan(load_config(), intent="Phase 9 runtime alpha.")
    return create_session_from_blueprint(build_worker_launch_blueprint(plan), worker_limit=1, runtime_mode="fake")


class CollabWorkerRuntimeTests(unittest.TestCase):
    def test_request_is_non_spawning_and_requires_explicit_allow(self):
        session = _session()
        request = build_worker_runtime_request(session, "worker-01-find", [sys.executable, "-c", "print('request')"])

        self.assertEqual(request["kind"], "collab_worker_runtime_request")
        self.assertFalse(request["spawns_process_now"])
        self.assertTrue(request["allow_spawn_required"])
        self.assertFalse(request["lead_cli_wrapped"])

    def test_run_without_allow_spawn_is_rejected(self):
        session = _session()

        with self.assertRaises(WorkerRuntimeError) as cm:
            run_worker_command(session, "worker-01-find", [sys.executable, "-c", "print('blocked')"])

        self.assertEqual(code_for_exception(cm.exception), "COLLAB_WORKER_RUNTIME_INVALID_INPUT")
        self.assertIn("allow_spawn", str(cm.exception))

    def test_allowed_command_result_is_ingested_into_event_sourced_model(self):
        session = _session()
        result = run_worker_command(
            session,
            "worker-01-find",
            [sys.executable, "-c", "print('worker report')"],
            allow_spawn=True,
        )
        session = apply_runtime_result(session, result, now="2026-06-20T12:00:00Z")
        model = materialize_bridge_host(session)

        self.assertEqual(result["kind"], "collab_worker_runtime_result")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["status"], "done")
        self.assertTrue(result["spawns_process_now"])
        self.assertFalse(result["lead_cli_wrapped"])
        self.assertTrue(model["contract"]["real_worker_lifecycle"])
        self.assertEqual(model["contract"]["phase"], 9)
        self.assertEqual(model["summary"]["runtime_run_count"], 1)
        row = model["worker_rows"][0]
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["runtime_run_count"], 1)
        self.assertEqual(row["last_runtime_status"], "done")
        self.assertEqual(row["report_pointer"], "worker report")

    def test_nonzero_command_is_captured_as_error_without_throwing(self):
        session = _session()
        result = run_worker_command(
            session,
            "worker-01-find",
            [sys.executable, "-c", "import sys; print('bad'); sys.exit(7)"],
            allow_spawn=True,
        )

        self.assertEqual(result["exit_code"], 7)
        self.assertEqual(result["status"], "error")
        self.assertIn("bad", result["stdout"])


if __name__ == "__main__":
    unittest.main()
