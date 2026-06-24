import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import ConfigError, DEFAULT_AGENT_NAMES, load_config, parse_config  # noqa: E402


class CollabConfigTests(unittest.TestCase):
    def test_default_config_contains_required_five_agents_in_stable_order(self):
        config = load_config()

        self.assertEqual(config.schema_version, 1)
        self.assertEqual([agent.name for agent in config.agents], list(DEFAULT_AGENT_NAMES))
        self.assertEqual(config.agent("dev").reasoning_effort, "high")
        self.assertEqual(config.agent("find").reasoning_effort, "medium")

    def test_config_fills_agent_defaults_without_mutating_required_identity(self):
        config = parse_config({
            "schema_version": 1,
            "workflow": "global-memory-collab",
            "defaults": {"model": "gpt-test", "reasoning_effort": "medium", "permission_mode": "ask", "client": "codex"},
            "agents": [
                {"name": "find", "role": "source locator"},
                {"name": "designer", "role": "architecture designer", "reasoning_effort": "high"},
                {"name": "dev", "role": "implementation", "reasoning_effort": "high"},
                {"name": "test", "role": "verification", "reasoning_effort": "high"},
                {"name": "main", "role": "documentation and state"},
            ],
        })

        self.assertEqual(config.agent("find").model, "gpt-test")
        self.assertEqual(config.agent("find").permission_mode, "ask")
        self.assertEqual(config.agent("designer").reasoning_effort, "high")

    def test_invalid_reasoning_effort_is_rejected(self):
        payload = load_config().to_dict()
        payload["agents"][0]["reasoning_effort"] = "maximum"

        with self.assertRaisesRegex(ConfigError, "reasoning_effort"):
            parse_config(payload)

    def test_missing_required_agent_is_rejected(self):
        payload = load_config().to_dict()
        payload["agents"] = [agent for agent in payload["agents"] if agent["name"] != "test"]

        with self.assertRaisesRegex(ConfigError, "missing required agents"):
            parse_config(payload)

    def test_load_config_reads_json_file(self):
        payload = load_config().to_dict()
        payload["agents"][0]["model"] = "gpt-custom"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collab.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            config = load_config(path)

        self.assertEqual(config.agent("find").model, "gpt-custom")


if __name__ == "__main__":
    unittest.main()
