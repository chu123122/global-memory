import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge import build_worker_launch_blueprint  # noqa: E402
from collab.bridge_host import (  # noqa: E402
    create_session_from_blueprint,
    ingest_worker_report,
    send_worker_message,
)
from collab.bridge_store import (  # noqa: E402
    build_store_summary,
    migrate_event_log,
    replay_store,
    write_materialized_snapshot,
)
from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402


class CollabBridgeStoreTests(unittest.TestCase):
    def _session(self):
        plan = build_dispatch_plan(load_config(), intent="Bridge store.")
        session = create_session_from_blueprint(build_worker_launch_blueprint(plan), worker_limit=2, runtime_mode="fake")
        session = send_worker_message(session, "worker-01-find", "Map files", now="2026-06-20T12:00:00Z")
        return ingest_worker_report(session, "worker-01-find", "reports/find.md", status="done", now="2026-06-20T12:05:00Z")

    def test_store_summary_is_replayable_and_materialized(self):
        session = self._session()

        summary = build_store_summary(session)

        self.assertEqual(summary["kind"], "collab_bridge_store_summary")
        self.assertEqual(summary["schema_version"], 1)
        self.assertEqual(summary["event_count"], len(session["events"]))
        self.assertEqual(summary["materialized"]["summary"]["report_count"], 1)
        self.assertTrue(summary["replay"]["deterministic"])

    def test_snapshot_roundtrip_and_migration_stub(self):
        session = self._session()

        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "session.json"
            written = write_materialized_snapshot(session, snapshot_path)
            replayed = replay_store(snapshot_path)
            migrated = migrate_event_log(session["events"], from_version=1, to_version=1)

        self.assertEqual(written["path"], str(snapshot_path))
        self.assertEqual(replayed["kind"], "collab_bridge_host_model")
        self.assertEqual(migrated["kind"], "collab_bridge_event_migration")
        self.assertFalse(migrated["changed"])
        self.assertEqual(migrated["to_version"], 1)


if __name__ == "__main__":
    unittest.main()
