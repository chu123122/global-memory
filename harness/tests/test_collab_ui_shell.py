import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config  # noqa: E402
from collab.dispatch import build_dispatch_packet  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402
from collab.queue import lease_next, queue_from_plan  # noqa: E402
from collab.recover import build_recovery_report  # noqa: E402
from collab.replay import build_replay_runbook  # noqa: E402
from collab.state import state_from_plan, update_dispatch  # noqa: E402
from collab.ui_shell import (  # noqa: E402
    UiShellError,
    build_ui_shell_model,
    dumps_ui_shell_json,
    render_ui_shell_markdown,
)


class CollabUiShellTests(unittest.TestCase):
    def test_model_information_architecture_and_contract(self):
        plan = build_dispatch_plan(load_config(), intent="UI shell.")
        state = update_dispatch(state_from_plan(plan), "01-find", status="done", report="paths.md")
        queue, leased = lease_next(queue_from_plan(plan), worker_id="worker-1", now="2026-06-20T00:00:00Z")
        recovery = build_recovery_report(plan=plan, state=state, queue=queue, now="2026-06-20T00:30:00Z")
        packet = build_dispatch_packet(build_replay_runbook(plan, state=state), dispatch_id="02-designer")

        model = build_ui_shell_model(
            plan=plan,
            state=state,
            queue=queue,
            recovery=recovery,
            dispatch_packet=packet,
            report_pointers={"01-find": "paths.md"},
        )

        self.assertEqual(model["kind"], "collab_ui_shell_model")
        self.assertTrue(model["contract"]["headless"])
        self.assertFalse(model["contract"]["spawns_process"])
        self.assertEqual(model["contract"]["readiness"], "experimental")
        self.assertIn("plan", [section["id"] for section in model["information_architecture"]])
        self.assertIn("recover", [section["id"] for section in model["information_architecture"]])
        first = model["dispatch_rows"][0]
        self.assertEqual(first["dispatch_id"], "01-find")
        self.assertEqual(first["state_status"], "done")
        self.assertEqual(first["queue_status"], "leased")
        self.assertEqual(first["report_pointer"], "paths.md")
        self.assertEqual(model["selected_dispatch"]["dispatch_id"], "02-designer")
        self.assertNotIn("spawn", " ".join(action["action"] for action in model["operator_actions"]).lower())
        self.assertEqual(leased.dispatch_id, "01-find")

    def test_model_handles_missing_optional_artifacts(self):
        plan = build_dispatch_plan(load_config(), intent="UI shell minimal.")

        model = build_ui_shell_model(plan=plan)

        self.assertEqual(model["artifact_presence"]["state"], False)
        self.assertEqual(model["artifact_presence"]["queue"], False)
        self.assertEqual(model["artifact_presence"]["recover"], False)
        self.assertEqual(model["summary"]["dispatch_count"], 5)
        self.assertTrue(all(row["state_status"] == "unknown" for row in model["dispatch_rows"]))

    def test_model_rejects_dispatch_packet_that_spawns_process(self):
        plan = build_dispatch_plan(load_config(), intent="UI shell bad packet.")
        packet = {"dispatch_id": "01-find", "runtime_payload": {"spawns_process": True}}

        with self.assertRaisesRegex(UiShellError, "spawns_process"):
            build_ui_shell_model(plan=plan, dispatch_packet=packet)

    def test_json_and_markdown_are_deterministic(self):
        plan = build_dispatch_plan(load_config(), intent="UI shell render.")
        model = build_ui_shell_model(plan=plan)

        self.assertEqual(dumps_ui_shell_json(model), dumps_ui_shell_json(model))
        markdown = render_ui_shell_markdown(model)
        self.assertIn("# Collaboration UI Shell Dashboard", markdown)
        self.assertIn("## XDMaker Reuse / Replace Boundary", markdown)
        self.assertIn("spawns_process: `false`", markdown)


if __name__ == "__main__":
    unittest.main()
