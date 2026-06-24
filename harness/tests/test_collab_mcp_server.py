import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.bridge import build_worker_launch_blueprint, dumps_bridge_json  # noqa: E402
from collab.config import load_config  # noqa: E402
from collab.mcp_server import build_codex_mcp_exec_probe_command, build_mcp_server_config, classify_codex_mcp_exec_probe, handle_mcp_request, run_mcp_self_test  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402

HOST_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_bridge_host.py"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_mcp_server.py"


def _events(tmp: str) -> Path:
    plan = build_dispatch_plan(load_config(), intent="Phase 15 MCP server.")
    blueprint = Path(tmp) / "blueprint.json"
    events = Path(tmp) / "events.jsonl"
    blueprint.write_text(dumps_bridge_json(build_worker_launch_blueprint(plan)), encoding="utf-8")
    subprocess.run([sys.executable, str(HOST_SCRIPT), "create", "--blueprint", str(blueprint), "--events", str(events), "--worker-limit", "1", "--json"], check=True, text=True, capture_output=True)
    return events


class CollabMcpServerTests(unittest.TestCase):
    def test_initialize_and_tools_list_are_jsonrpc_mcp(self):
        init = handle_mcp_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        tools = handle_mcp_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

        self.assertEqual(init["result"]["serverInfo"]["name"], "global-memory-collab-bridge")
        names = {tool["name"] for tool in tools["result"]["tools"]}
        self.assertIn("send_to_worker", names)
        self.assertIn("worker_status", names)
        worker_status = next(tool for tool in tools["result"]["tools"] if tool["name"] == "worker_status")
        send_tool = next(tool for tool in tools["result"]["tools"] if tool["name"] == "send_to_worker")
        self.assertTrue(worker_status["annotations"]["readOnlyHint"])
        self.assertFalse(send_tool["annotations"]["readOnlyHint"])
        self.assertTrue(send_tool["annotations"]["requiresApprovalHint"])

    def test_tool_call_updates_event_log_through_real_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _events(tmp)
            before = len(events.read_text(encoding="utf-8").splitlines())
            response = handle_mcp_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "send_to_worker", "arguments": {"worker_id": "worker-01-find", "message": "hello"}}}, events_path=events)
            after = len(events.read_text(encoding="utf-8").splitlines())

        self.assertIn("result", response)
        self.assertGreater(after, before)
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertTrue(content["real_mcp_server_verified"])

    def test_self_test_verifies_initialize_list_and_tool_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _events(tmp)
            payload = run_mcp_self_test(events)

        self.assertTrue(payload["real_mcp_server_verified"])
        self.assertTrue(payload["mutating_tool_call_ok"])

    def test_config_is_non_persistent(self):
        cfg = build_mcp_server_config("events.jsonl", python_executable="python")
        self.assertTrue(cfg["does_not_persist_config_by_itself"])
        self.assertIn("mcp_servers.global-memory-collab-bridge", cfg["codex_config_toml"])



    def test_codex_probe_command_and_classification_helpers(self):
        command = build_codex_mcp_exec_probe_command("events.jsonl", workdir=".", output_file="last.txt", python_executable="python")
        self.assertEqual(command["kind"], "collab_codex_mcp_exec_probe_command")
        self.assertIn("-a", command["command"])
        self.assertIn("never", command["command"])
        ok = classify_codex_mcp_exec_probe(output_text="MCP_TOOL_OK")
        cancelled = classify_codex_mcp_exec_probe(stderr="mcp: global-memory-collab-bridge/worker_status started\nuser cancelled MCP tool call")
        self.assertEqual(ok["status"], "ok")
        self.assertEqual(cancelled["status"], "approval_cancelled")

class CollabMcpServerCliTests(unittest.TestCase):

    def test_cli_codex_probe_command_and_classify(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "last.txt"
            out.write_text("MCP_TOOL_OK", encoding="utf-8")
            command = subprocess.run([sys.executable, str(SCRIPT), "codex-probe-command", "--events", "events.jsonl", "--workdir", tmp, "--output-file", str(out), "--json"], check=True, text=True, capture_output=True)
            classify = subprocess.run([sys.executable, str(SCRIPT), "classify-codex-probe", "--output-file", str(out), "--json"], check=True, text=True, capture_output=True)
        self.assertEqual(json.loads(command.stdout)["kind"], "collab_codex_mcp_exec_probe_command")
        self.assertEqual(json.loads(classify.stdout)["status"], "ok")

    def test_cli_self_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = _events(tmp)
            result = subprocess.run([sys.executable, str(SCRIPT), "self-test", "--events", str(events), "--json"], check=True, text=True, capture_output=True)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["kind"], "collab_real_mcp_server_probe")
        self.assertTrue(payload["real_mcp_server_verified"])


if __name__ == "__main__":
    unittest.main()
