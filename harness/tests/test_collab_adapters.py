import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.adapters import build_adapter_payload, build_adapter_payloads  # noqa: E402
from collab.config import load_config, parse_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402


class CollabAdapterPayloadTests(unittest.TestCase):
    def test_codex_payload_is_declarative_spawn_agent_shape(self):
        plan = build_dispatch_plan(load_config(), intent="Adapter payload smoke.")
        payloads = build_adapter_payloads(plan)

        first = payloads[0]

        self.assertEqual(first["kind"], "collab_adapter_payload")
        self.assertEqual(first["adapter"], "codex")
        self.assertFalse(first["spawns_process"])
        self.assertTrue(first["requires_runtime_tool"])
        self.assertEqual(first["tool"]["name"], "spawn_agent")
        self.assertEqual(first["tool"]["arguments"]["agent_type"], "worker")
        self.assertIn("Intent:\nAdapter payload smoke.", first["tool"]["arguments"]["message"])

    def test_orca_payload_maps_to_create_worker_without_running_it(self):
        config = parse_config({
            "schema_version": 1,
            "workflow": "global-memory-collab",
            "defaults": {
                "client": "orca",
                "model": "gpt-5.5",
                "reasoning_effort": "high",
                "permission_mode": "workspace-write",
            },
            "agents": [
                {"name": "find", "role": "source locator"},
                {"name": "designer", "role": "architecture designer"},
                {"name": "dev", "role": "implementation"},
                {"name": "test", "role": "verification"},
                {"name": "main", "role": "documentation and state"},
            ],
        })
        plan = build_dispatch_plan(config, intent="Map to Orca.")

        payload = build_adapter_payload(plan["dispatches"][0])

        self.assertEqual(payload["adapter"], "orca")
        self.assertEqual(payload["tool"]["name"], "create_worker")
        self.assertEqual(payload["tool"]["arguments"]["agent"], "codex")
        self.assertEqual(payload["tool"]["arguments"]["role"], "find")
        self.assertFalse(payload["spawns_process"])

    def test_manual_payload_has_prompt_fallback_and_no_tool(self):
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
        plan = build_dispatch_plan(config, intent="Manual fallback.")

        payload = build_adapter_payloads(plan)[0]

        self.assertIsNone(payload["tool"])
        self.assertFalse(payload["requires_runtime_tool"])
        self.assertIn("Manual fallback.", payload["manual_fallback"]["prompt"])

    def test_adapter_payloads_remain_host_neutral(self):
        plan = build_dispatch_plan(load_config(), intent="No host-specific payload.")
        payloads = build_adapter_payloads(plan)

        encoded = json.dumps(payloads, ensure_ascii=False).lower()

        self.assertNotIn("electron", encoded)
        self.assertNotIn("localdb", encoded)
        self.assertNotIn("xdt-maker-main", encoded)


if __name__ == "__main__":
    unittest.main()
