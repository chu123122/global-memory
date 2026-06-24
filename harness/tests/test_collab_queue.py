import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402
from collab.queue import (  # noqa: E402
    QueueError,
    complete_lease,
    lease_next,
    queue_from_plan,
    requeue_lease,
    summarize_queue,
)


class CollabQueueTests(unittest.TestCase):
    def test_queue_from_plan_preserves_order_and_labels(self):
        plan = build_dispatch_plan(load_config(), intent="Queue labels.")
        queue = queue_from_plan(plan, labels_by_dispatch={"01-find": ["docs", "phase4"]})

        self.assertEqual(queue.plan_id, plan["plan_id"])
        self.assertEqual(queue.items[0].dispatch_id, "01-find")
        self.assertEqual(queue.items[0].status, "queued")
        self.assertEqual(queue.items[0].labels, ("docs", "phase4"))
        self.assertEqual(summarize_queue(queue)["status_counts"]["queued"], 5)

    def test_lease_next_filters_labels_and_respects_worker_concurrency(self):
        plan = build_dispatch_plan(load_config(), intent="Lease labels.")
        queue = queue_from_plan(plan, labels_by_dispatch={"02-designer": ["design"]})

        queue, item = lease_next(queue, worker_id="worker-1", labels=["design"], now="2026-06-20T00:00:00Z")

        self.assertEqual(item.dispatch_id, "02-designer")
        self.assertEqual(item.status, "leased")
        self.assertEqual(item.lease_owner, "worker-1")
        with self.assertRaisesRegex(QueueError, "concurrency"):
            lease_next(queue, worker_id="worker-1", max_concurrent=1, now="2026-06-20T00:01:00Z")

    def test_requeue_and_complete_lease_update_attempts_and_status(self):
        queue = queue_from_plan(build_dispatch_plan(load_config(), intent="Retry."))
        queue, item = lease_next(queue, worker_id="worker-1", now="2026-06-20T00:00:00Z")

        queue = requeue_lease(queue, item.lease_id, reason="needs rerun")
        self.assertEqual(queue.items[0].status, "queued")
        self.assertEqual(queue.items[0].attempts, 1)
        self.assertEqual(queue.items[0].last_error, "needs rerun")

        queue, item = lease_next(queue, worker_id="worker-2", now="2026-06-20T00:02:00Z")
        queue = complete_lease(queue, item.lease_id, report="done")
        self.assertEqual(queue.items[0].status, "done")
        self.assertEqual(queue.items[0].report, "done")

    def test_retry_exhaustion_marks_error(self):
        queue = queue_from_plan(build_dispatch_plan(load_config(), intent="Exhaust."), max_attempts=1)
        queue, item = lease_next(queue, worker_id="worker-1", now="2026-06-20T00:00:00Z")

        queue = requeue_lease(queue, item.lease_id, reason="failed")

        self.assertEqual(queue.items[0].status, "error")
        self.assertEqual(queue.items[0].attempts, 1)


if __name__ == "__main__":
    unittest.main()
