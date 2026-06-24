import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402
from collab.queue import lease_next, queue_from_plan  # noqa: E402
from collab.recover import build_recovery_report  # noqa: E402
from collab.state import state_from_plan, update_dispatch  # noqa: E402


class CollabRecoverTests(unittest.TestCase):
    def test_recovery_reports_stale_running_dispatch(self):
        plan = build_dispatch_plan(load_config(), intent="Stale running.")
        state = update_dispatch(
            state_from_plan(plan),
            "01-find",
            status="running",
            worker_id="worker-1",
            updated_at="2026-06-20T00:00:00Z",
        )

        report = build_recovery_report(plan=plan, state=state, now="2026-06-20T02:00:00Z", stale_after_seconds=3600)

        self.assertEqual(report["kind"], "collab_recovery_report")
        self.assertIn("COLLAB_RECOVER_STALE_RUNNING", [issue["error_code"] for issue in report["issues"]])
        self.assertTrue(any(action["action"] == "requeue_or_mark_blocked" for action in report["actions"]))

    def test_recovery_reports_plan_state_id_mismatch(self):
        plan = build_dispatch_plan(load_config(), intent="Mismatch A.")
        other_plan = build_dispatch_plan(load_config(), intent="Mismatch B.")
        state = state_from_plan(other_plan)

        report = build_recovery_report(plan=plan, state=state, now="2026-06-20T00:00:00Z")

        self.assertIn("COLLAB_PLAN_STATE_MISMATCH", [issue["error_code"] for issue in report["issues"]])
        self.assertEqual(report["verdict"], "needs_attention")

    def test_recovery_reports_queue_stale_lease_and_state_queue_conflict(self):
        plan = build_dispatch_plan(load_config(), intent="Queue stale.")
        state = update_dispatch(state_from_plan(plan), "01-find", status="pending")
        queue, leased = lease_next(queue_from_plan(plan), worker_id="worker-1", now="2026-06-20T00:00:00Z")

        report = build_recovery_report(
            plan=plan,
            state=state,
            queue=queue,
            now="2026-06-20T02:00:00Z",
            stale_after_seconds=3600,
        )

        codes = [issue["error_code"] for issue in report["issues"]]
        self.assertEqual(leased.dispatch_id, "01-find")
        self.assertIn("COLLAB_QUEUE_STALE_LEASE", codes)
        self.assertIn("COLLAB_STATE_QUEUE_CONFLICT", codes)

    def test_recovery_reports_unsupported_schema_from_raw_payloads(self):
        report = build_recovery_report(
            plan={"schema_version": 99, "plan_id": "p", "workflow": "w", "dispatches": []},
            state_raw={"schema_version": 99, "plan_id": "p", "workflow": "w", "dispatches": []},
            queue_raw={"schema_version": 99, "plan_id": "p", "workflow": "w", "items": []},
            now="2026-06-20T00:00:00Z",
        )

        codes = [issue["error_code"] for issue in report["issues"]]
        self.assertIn("COLLAB_PLAN_SCHEMA_UNSUPPORTED", codes)
        self.assertIn("COLLAB_STATE_SCHEMA_UNSUPPORTED", codes)
        self.assertIn("COLLAB_QUEUE_SCHEMA_UNSUPPORTED", codes)


if __name__ == "__main__":
    unittest.main()
