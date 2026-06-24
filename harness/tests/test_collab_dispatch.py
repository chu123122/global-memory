import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config, parse_config  # noqa: E402
from collab.dispatch import DispatchError, build_dispatch_packet, render_dispatch_packet_markdown  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402
from collab.replay import build_replay_runbook  # noqa: E402
from collab.state import state_from_plan, update_dispatch  # noqa: E402


class CollabDispatchPacketTests(unittest.TestCase):
    def test_dispatch_packet_selects_first_available_action(self):
        plan = build_dispatch_plan(load_config(), intent="Dispatch.")
        state = update_dispatch(state_from_plan(plan), "01-find", status="done")
        runbook = build_replay_runbook(plan, state=state, state_path="state.json")

        packet = build_dispatch_packet(runbook)

        self.assertEqual(packet["kind"], "collab_dispatch_packet")
        self.assertTrue(packet["dry_run"])
        self.assertEqual(packet["dispatch_id"], "02-designer")
        self.assertFalse(packet["spawns_process"])
        self.assertIn("collab_state.py", packet["state_update_commands"]["mark running"])

    def test_dispatch_packet_can_select_specific_action(self):
        runbook = build_replay_runbook(build_dispatch_plan(load_config(), intent="Specific."))

        packet = build_dispatch_packet(runbook, dispatch_id="03-dev")

        self.assertEqual(packet["dispatch_id"], "03-dev")
        self.assertEqual(packet["agent"], "dev")

    def test_dispatch_packet_rejects_unavailable_action(self):
        runbook = build_replay_runbook(build_dispatch_plan(load_config()))

        with self.assertRaisesRegex(DispatchError, "not available"):
            build_dispatch_packet(runbook, dispatch_id="99-missing")

    def test_dispatch_packet_preserves_manual_fallback(self):
        config = parse_config({
            "schema_version": 1,
            "workflow": "global-memory-collab",
            "defaults": {
                "client": "manual",
                "model": "gpt-5.5",
                "reasoning_effort": "medium",
                "permission_mode": "ask",
            },
            "agents": [
                {"name": "find", "role": "source locator"},
                {"name": "designer", "role": "architecture designer"},
                {"name": "dev", "role": "implementation"},
                {"name": "test", "role": "verification"},
                {"name": "main", "role": "documentation and state"},
            ],
        })
        runbook = build_replay_runbook(build_dispatch_plan(config, intent="Manual."))

        packet = build_dispatch_packet(runbook)

        self.assertEqual(packet["adapter"], "manual")
        self.assertIsNone(packet["runtime_tool"])
        self.assertIn("manual_fallback", json.dumps(packet["runtime_payload"]))

    def test_markdown_renders_payload_and_state_commands(self):
        packet = build_dispatch_packet(build_replay_runbook(build_dispatch_plan(load_config(), intent="Markdown.")))

        markdown = render_dispatch_packet_markdown(packet)

        self.assertIn("# Collaboration Dispatch Packet", markdown)
        self.assertIn("## Runtime payload", markdown)
        self.assertIn("## State update commands", markdown)
        self.assertIn("## Worker prompt", markdown)


if __name__ == "__main__":
    unittest.main()
