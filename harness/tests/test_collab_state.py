import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402
from collab.state import (  # noqa: E402
    StateError,
    load_state,
    save_state,
    state_from_plan,
    update_dispatch,
)


class CollabStateTests(unittest.TestCase):
    def test_state_from_plan_tracks_each_dispatch_as_pending(self):
        plan = build_dispatch_plan(load_config(), intent="Create state.")

        state = state_from_plan(plan)

        self.assertEqual(state.workflow, "global-memory-collab")
        self.assertEqual(state.plan_id, plan["plan_id"])
        self.assertEqual([item.dispatch_id for item in state.dispatches], [item["id"] for item in plan["dispatches"]])
        self.assertTrue(all(item.status == "pending" for item in state.dispatches))

    def test_update_dispatch_returns_copy_with_worker_metadata(self):
        state = state_from_plan(build_dispatch_plan(load_config()))

        updated = update_dispatch(
            state,
            "01-find",
            status="done",
            worker_id="worker-1",
            session_id="session-1",
            report="found paths",
        )

        self.assertEqual(state.dispatches[0].status, "pending")
        self.assertEqual(updated.dispatches[0].status, "done")
        self.assertEqual(updated.dispatches[0].worker_id, "worker-1")
        self.assertEqual(updated.dispatches[0].report, "found paths")

    def test_update_dispatch_rejects_unknown_status_and_id(self):
        state = state_from_plan(build_dispatch_plan(load_config()))

        with self.assertRaisesRegex(StateError, "status"):
            update_dispatch(state, "01-find", status="finished")
        with self.assertRaisesRegex(StateError, "unknown dispatch_id"):
            update_dispatch(state, "99-missing", status="done")

    def test_state_roundtrip_json_file(self):
        state = update_dispatch(
            state_from_plan(build_dispatch_plan(load_config(), intent="Roundtrip.")),
            "01-find",
            status="running",
            worker_id="worker-1",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collab-state.json"
            save_state(state, path)

            loaded = load_state(path)
            raw = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded.to_dict(), state.to_dict())
        self.assertEqual(raw["dispatches"][0]["worker_id"], "worker-1")


if __name__ == "__main__":
    unittest.main()
