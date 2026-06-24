import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge import build_worker_launch_blueprint, dumps_bridge_json  # noqa: E402
from collab.bridge_host import create_session_from_blueprint, save_session_events  # noqa: E402
from collab.config import load_config  # noqa: E402
from collab.persistence import append_persistent_event, export_event_log, import_event_log, init_persistence, list_persistent_sessions, load_persistent_session, recover_persistence  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_persistence.py"


def _events(tmp: str) -> Path:
    plan = build_dispatch_plan(load_config(), intent="Phase 17 persistence.")
    session = create_session_from_blueprint(build_worker_launch_blueprint(plan), worker_limit=1, runtime_mode="fake")
    path = Path(tmp) / "events.jsonl"
    save_session_events(session, path)
    return path


class CollabPersistenceTests(unittest.TestCase):
    def test_import_reopen_export_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "collab.sqlite3"
            events = _events(tmp)
            init_persistence(db)
            imported = import_event_log(db, "s1", events)
            session = load_persistent_session(db, "s1")
            exported = Path(tmp) / "exported.jsonl"
            export = export_event_log(db, "s1", exported)
            recovery = recover_persistence(db)

        self.assertEqual(imported["event_count"], 3)
        self.assertEqual(len(session["workers"]), 1)
        self.assertEqual(export["event_count"], 3)
        self.assertTrue(recovery["recovered"][0]["ok"])

    def test_concurrent_append_uses_sqlite_locking(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "collab.sqlite3"
            events = _events(tmp)
            init_persistence(db)
            import_event_log(db, "s1", events)
            def add(i: int) -> None:
                append_persistent_event(db, "s1", {"type": "message_sent", "worker_id": "worker-01-find", "message": f"m{i}"})
            threads = [threading.Thread(target=add, args=(i,)) for i in range(10)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            sessions = list_persistent_sessions(db)

        self.assertEqual(sessions["sessions"][0]["event_count"], 13)

    def test_cli_import_list_recover(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "collab.sqlite3"
            events = _events(tmp)
            subprocess.run([sys.executable, str(SCRIPT), "init", "--db", str(db), "--json"], check=True, text=True, capture_output=True)
            subprocess.run([sys.executable, str(SCRIPT), "import", "--db", str(db), "--session-id", "s1", "--events", str(events), "--json"], check=True, text=True, capture_output=True)
            result = subprocess.run([sys.executable, str(SCRIPT), "recover", "--db", str(db), "--json"], check=True, text=True, capture_output=True)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "collab_persistence_recovery")
        self.assertTrue(payload["recovered"][0]["ok"])


if __name__ == "__main__":
    unittest.main()
