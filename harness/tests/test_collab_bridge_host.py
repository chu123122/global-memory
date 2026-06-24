import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge_host import (  # noqa: E402
    create_session_from_blueprint,
    focus_worker,
    ingest_worker_report,
    materialize_bridge_host,
    send_worker_message,
)
from collab.bridge import build_worker_launch_blueprint  # noqa: E402
from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402


class CollabBridgeHostTests(unittest.TestCase):
    def test_session_creates_fake_workers_from_blueprint_without_spawning(self):
        plan = build_dispatch_plan(load_config(), intent="Bridge host MVP.")
        blueprint = build_worker_launch_blueprint(plan)

        session = create_session_from_blueprint(blueprint, worker_limit=2, runtime_mode="fake")

        self.assertEqual(session["kind"], "collab_bridge_host_session")
        self.assertEqual(session["runtime_mode"], "fake")
        self.assertFalse(session["spawns_process_now"])
        self.assertEqual(len(session["workers"]), 2)
        self.assertEqual(session["workers"][0]["worker_id"], "worker-01-find")
        self.assertEqual(session["workers"][0]["status"], "ready")

    def test_focus_send_and_report_update_event_sourced_view_model(self):
        plan = build_dispatch_plan(load_config(), intent="Bridge host interaction.")
        session = create_session_from_blueprint(build_worker_launch_blueprint(plan), worker_limit=2, runtime_mode="fake")

        session = focus_worker(session, "worker-02-designer")
        session = send_worker_message(session, "worker-02-designer", "Please refine the architecture.", now="2026-06-20T10:00:00Z")
        session = ingest_worker_report(session, "worker-02-designer", "reports/designer.md", status="done", now="2026-06-20T10:05:00Z")
        model = materialize_bridge_host(session)

        self.assertEqual(model["kind"], "collab_bridge_host_model")
        self.assertEqual(model["focused_worker_id"], "worker-02-designer")
        row = {item["worker_id"]: item for item in model["worker_rows"]}["worker-02-designer"]
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["message_count"], 1)
        self.assertEqual(row["report_pointer"], "reports/designer.md")
        self.assertEqual(model["contract"]["runtime_mode"], "fake")
        self.assertFalse(model["contract"]["real_worker_lifecycle"])

    def test_event_log_roundtrip_restores_view_model(self):
        plan = build_dispatch_plan(load_config(), intent="Bridge host persistence.")
        session = create_session_from_blueprint(build_worker_launch_blueprint(plan), worker_limit=2, runtime_mode="fake")
        session = send_worker_message(session, "worker-01-find", "Map sources.", now="2026-06-20T11:00:00Z")

        with tempfile.TemporaryDirectory() as tmp:
            event_log = Path(tmp) / "events.jsonl"
            from collab.bridge_host import load_session_events, save_session_events  # noqa: E402
            save_session_events(session, event_log)
            restored = load_session_events(event_log)

        self.assertEqual(materialize_bridge_host(restored), materialize_bridge_host(session))


if __name__ == "__main__":
    unittest.main()
