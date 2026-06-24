import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge import build_worker_launch_blueprint  # noqa: E402
from collab.bridge_host import create_session_from_blueprint, materialize_bridge_host  # noqa: E402
from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402
from collab.router import (  # noqa: E402
    acknowledge_message,
    build_router_snapshot,
    enqueue_message,
    fail_message,
    ingest_router_report,
    retry_message,
)


def _session():
    plan = build_dispatch_plan(load_config(), intent="Phase 11 router.")
    return create_session_from_blueprint(build_worker_launch_blueprint(plan), worker_limit=1, runtime_mode="fake")


class CollabRouterTests(unittest.TestCase):
    def test_enqueue_ack_and_report_are_visible_in_materialized_model(self):
        session = _session()
        session, queued = enqueue_message(session, "worker-01-find", "Inspect router", correlation_id="corr-1", dedupe_key="dedupe-1")
        session, acked = acknowledge_message(session, queued["message_id"], ack_id="ack-1")
        session, report = ingest_router_report(session, "worker-01-find", "reports/router.md", status="done")
        snapshot = build_router_snapshot(session)
        model = materialize_bridge_host(session)

        self.assertEqual(acked["status"], "acked")
        self.assertEqual(report["status"], "report_ingested")
        self.assertEqual(snapshot["summary"]["acked"], 1)
        self.assertEqual(model["summary"]["router_message_count"], 1)
        row = model["worker_rows"][0]
        self.assertEqual(row["router_acked_count"], 1)
        self.assertEqual(row["message_count"], 1)
        self.assertEqual(row["report_pointer"], "reports/router.md")

    def test_duplicate_message_is_visible_not_silent(self):
        session = _session()
        session, first = enqueue_message(session, "worker-01-find", "Inspect router", correlation_id="corr-1", dedupe_key="dup")
        session, duplicate = enqueue_message(session, "worker-01-find", "Inspect router again", correlation_id="corr-2", dedupe_key="dup")
        snapshot = build_router_snapshot(session)
        model = materialize_bridge_host(session)

        self.assertFalse(first.get("duplicate", False))
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(snapshot["summary"]["duplicates"], 1)
        self.assertEqual(model["summary"]["router_duplicate_count"], 1)
        self.assertEqual(model["worker_rows"][0]["router_duplicate_count"], 1)

    def test_failed_message_can_be_retried_with_new_message_id(self):
        session = _session()
        session, queued = enqueue_message(session, "worker-01-find", "Send may fail", correlation_id="corr-fail", dedupe_key="fail")
        session, failed = fail_message(session, queued["message_id"], "transport unavailable", retryable=True)
        session, retried = retry_message(session, failed["message_id"])
        snapshot = build_router_snapshot(session)

        self.assertEqual(failed["status"], "failed")
        self.assertEqual(retried["status"], "retried")
        self.assertNotEqual(retried["message_id"], queued["message_id"])
        self.assertEqual(snapshot["summary"]["retried"], 1)
        self.assertEqual(snapshot["summary"]["queued"], 1)


if __name__ == "__main__":
    unittest.main()
