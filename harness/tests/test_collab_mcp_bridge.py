import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge import build_worker_launch_blueprint  # noqa: E402
from collab.bridge_host import create_session_from_blueprint, materialize_bridge_host  # noqa: E402
from collab.config import load_config  # noqa: E402
from collab.mcp_bridge import build_lead_cli_mcp_schema, call_bridge_tool, probe_lead_cli_mcp  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402


def _session(worker_limit=1):
    plan = build_dispatch_plan(load_config(), intent="Phase 10 MCP bridge.")
    return create_session_from_blueprint(build_worker_launch_blueprint(plan), worker_limit=worker_limit, runtime_mode="fake")


class CollabMcpBridgeTests(unittest.TestCase):
    def test_schema_exposes_stable_tools_without_wrapping_lead_cli(self):
        schema = build_lead_cli_mcp_schema()

        self.assertEqual(schema["kind"], "collab_lead_cli_mcp_schema")
        self.assertFalse(schema["lead_cli_boundary"]["wraps_or_replaces_lead_cli"])
        self.assertFalse(schema["server"]["real_mcp_server_verified"])
        self.assertEqual([tool["name"] for tool in schema["tools"]], ["create_worker", "send_to_worker", "worker_status", "read_worker", "ingest_worker_report"])

    def test_probe_reports_bridge_tools_and_event_summary(self):
        session = _session()
        probe = probe_lead_cli_mcp(session)

        self.assertEqual(probe["kind"], "collab_lead_cli_mcp_probe")
        self.assertTrue(probe["bridge_tools_available"])
        self.assertFalse(probe["lead_cli_wrapped"])
        self.assertFalse(probe["real_mcp_server_verified"])
        self.assertEqual(probe["materialized_summary"]["worker_count"], 1)

    def test_mutating_tool_calls_update_event_sourced_model(self):
        session = _session(worker_limit=0)
        payload, session, updated = call_bridge_tool(
            session,
            "create_worker",
            {"worker_id": "worker-extra", "agent": "find", "initial_prompt": "Map files", "focus": True},
        )
        self.assertTrue(updated)
        self.assertEqual(payload["result"]["status"], "created")
        self.assertEqual(payload["materialized"]["summary"]["worker_count"], 1)

        payload, session, updated = call_bridge_tool(session, "send_to_worker", {"worker_id": "worker-extra", "message": "Please inspect Phase 10."})
        self.assertTrue(updated)
        self.assertEqual(payload["materialized"]["worker_rows"][0]["message_count"], 1)

        payload, session, updated = call_bridge_tool(session, "ingest_worker_report", {"worker_id": "worker-extra", "report": "reports/phase10.md", "status": "done"})
        self.assertTrue(updated)
        row = payload["materialized"]["worker_rows"][0]
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["report_pointer"], "reports/phase10.md")

    def test_read_only_tool_calls_do_not_update_events(self):
        session = _session()
        before = len(session["events"])
        payload, session, updated = call_bridge_tool(session, "worker_status", {"worker_id": "worker-01-find"})

        self.assertFalse(updated)
        self.assertEqual(len(session["events"]), before)
        self.assertEqual(payload["result"]["worker"]["worker_id"], "worker-01-find")

        payload, session, updated = call_bridge_tool(session, "read_worker", {"worker_id": "worker-01-find"})
        self.assertFalse(updated)
        self.assertIn("initial_prompt", payload["result"]["worker"])


if __name__ == "__main__":
    unittest.main()
