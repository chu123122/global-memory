import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge import (  # noqa: E402
    BRIDGE_MCP_TOOLS,
    build_standalone_bridge_spec,
    build_worker_launch_blueprint,
)
from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402


class CollabBridgeTests(unittest.TestCase):
    def test_bridge_contract_does_not_wrap_lead_cli_but_owns_worker_runtime(self):
        spec = build_standalone_bridge_spec()

        self.assertEqual(spec["kind"], "collab_standalone_bridge_spec")
        self.assertFalse(spec["lead_cli_boundary"]["wraps_or_replaces_lead_cli"])
        self.assertFalse(spec["lead_cli_boundary"]["mutates_lead_thread_goal_or_tools"])
        self.assertTrue(spec["control_plane"]["owns_worker_runtime"])
        self.assertTrue(spec["control_plane"]["owns_event_store"])
        self.assertIn("create_worker", [tool["name"] for tool in spec["mcp_tool_surface"]])
        self.assertIn("read_worker", [tool["name"] for tool in spec["mcp_tool_surface"]])

    def test_capability_matrix_makes_manual_not_a_real_runtime(self):
        spec = build_standalone_bridge_spec()
        levels = {entry["adapter"]: entry["capability_level"] for entry in spec["capability_matrix"]}

        self.assertEqual(levels["manual"], "action_card_only")
        self.assertEqual(levels["standalone-codex-worker"], "standalone_worker_runtime")
        self.assertEqual(levels["standalone-claude-worker"], "standalone_worker_runtime")
        self.assertEqual(levels["orca"], "real_worker_api")

    def test_worker_launch_blueprint_is_deferred_and_plan_shaped(self):
        plan = build_dispatch_plan(load_config(), intent="Standalone bridge workers.")

        blueprint = build_worker_launch_blueprint(plan)

        self.assertEqual(blueprint["kind"], "collab_worker_launch_blueprint")
        self.assertFalse(blueprint["spawns_process_now"])
        self.assertEqual(blueprint["launch_policy"], "deferred_explicit_operator_or_mcp_call")
        self.assertEqual(len(blueprint["workers"]), 5)
        first = blueprint["workers"][0]
        self.assertEqual(first["dispatch_id"], "01-find")
        self.assertIn(first["runtime_adapter"], {"standalone-codex-worker", "standalone-claude-worker"})
        self.assertIn("Intent:\nStandalone bridge workers.", first["initial_prompt"])

    def test_bridge_mcp_tool_surface_is_stable(self):
        self.assertEqual(
            [tool.name for tool in BRIDGE_MCP_TOOLS],
            ["create_worker", "send_to_worker", "worker_status", "read_worker", "ingest_worker_report"],
        )


if __name__ == "__main__":
    unittest.main()
