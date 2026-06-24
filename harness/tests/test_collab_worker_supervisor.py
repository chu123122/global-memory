import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.worker_supervisor import WorkerSupervisor, build_supervisor_snapshot  # noqa: E402


class CollabWorkerSupervisorTests(unittest.TestCase):
    def test_start_send_read_stop_lifecycle(self):
        sup = WorkerSupervisor()
        events = []
        events.append(sup.start_worker("worker-1", [sys.executable, "-u", "-c", "import sys; print('ready', flush=True); print('echo:'+sys.stdin.readline().strip(), flush=True)"]))
        time.sleep(0.1)
        events.append(sup.read_worker("worker-1"))
        events.append(sup.send_to_worker("worker-1", "hello"))
        time.sleep(0.1)
        events.append(sup.read_worker("worker-1"))
        events.append(sup.stop_worker("worker-1"))
        snapshot = build_supervisor_snapshot(events)

        row = snapshot["worker_rows"][0]
        self.assertIn("ready", row["stdout"])
        self.assertIn("echo:hello", row["stdout"])
        self.assertGreaterEqual(row["messages"], 1)

    def test_crash_status_is_visible(self):
        sup = WorkerSupervisor()
        sup.start_worker("worker-1", [sys.executable, "-u", "-c", "import sys; print('boom', flush=True); sys.exit(7)"])
        time.sleep(0.15)
        status = sup.worker_status("worker-1")
        read = sup.read_worker("worker-1")

        self.assertEqual(status["status"], "crashed")
        self.assertIn("boom", read["stdout"])

    def test_timeout_kills_worker(self):
        sup = WorkerSupervisor()
        sup.start_worker("worker-1", [sys.executable, "-u", "-c", "import time; time.sleep(5)"], timeout_seconds=0.1)
        time.sleep(0.25)
        event = sup.enforce_timeout("worker-1")

        self.assertIsNotNone(event)
        self.assertEqual(event["status"], "timeout")


if __name__ == "__main__":
    unittest.main()
