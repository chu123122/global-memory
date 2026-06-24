import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge import build_worker_launch_blueprint, dumps_bridge_json  # noqa: E402
from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402

HOST_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_bridge_host.py"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_mcp_bridge.py"


def _create_events(tmp: str) -> Path:
    plan = build_dispatch_plan(load_config(), intent="Phase 10 MCP bridge CLI.")
    blueprint_path = Path(tmp) / "blueprint.json"
    events_path = Path(tmp) / "events.jsonl"
    blueprint_path.write_text(dumps_bridge_json(build_worker_launch_blueprint(plan)), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(HOST_SCRIPT), "create", "--blueprint", str(blueprint_path), "--events", str(events_path), "--worker-limit", "1", "--json"],
        check=True,
        text=True,
        capture_output=True,
    )
    return events_path


class CollabMcpBridgeCliTests(unittest.TestCase):
    def test_schema_and_probe_cli(self):
        schema = subprocess.run([sys.executable, str(SCRIPT), "schema", "--json"], check=True, text=True, capture_output=True)
        payload = json.loads(schema.stdout)
        self.assertEqual(payload["kind"], "collab_lead_cli_mcp_schema")
        self.assertFalse(payload["lead_cli_boundary"]["wraps_or_replaces_lead_cli"])

        with tempfile.TemporaryDirectory() as tmp:
            events = _create_events(tmp)
            probe = subprocess.run([sys.executable, str(SCRIPT), "probe", "--events", str(events), "--json"], check=True, text=True, capture_output=True)
        payload = json.loads(probe.stdout)
        self.assertEqual(payload["kind"], "collab_lead_cli_mcp_probe")
        self.assertTrue(payload["events_loadable"])
        self.assertFalse(payload["real_mcp_server_verified"])

    def test_call_cli_updates_events_for_mutating_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _create_events(tmp)
            args = json.dumps({"worker_id": "worker-01-find", "message": "MCP bridge hello"})
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "call", "--events", str(events), "--tool", "send_to_worker", "--args-json", args, "--json"],
                check=True,
                text=True,
                capture_output=True,
            )
            lines = events.read_text(encoding="utf-8").splitlines()

        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "collab_lead_cli_mcp_call_result")
        self.assertTrue(payload["event_log_updated"])
        self.assertEqual(payload["tool"], "send_to_worker")
        self.assertEqual(payload["materialized"]["worker_rows"][0]["message_count"], 1)
        self.assertTrue(any('"message_sent"' in line for line in lines))

    def test_call_cli_invalid_tool_uses_stable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _create_events(tmp)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "call", "--events", str(events), "--tool", "missing", "--args-json", "{}", "--json"],
                check=False,
                text=True,
                capture_output=True,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["kind"], "collab_lead_cli_mcp_error")
        self.assertEqual(payload["error_code"], "COLLAB_LEAD_CLI_MCP_INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
