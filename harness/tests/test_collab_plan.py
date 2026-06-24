import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.adapters import ADAPTER_CONTRACTS, get_adapter_contract  # noqa: E402
from collab.config import load_config  # noqa: E402
from collab.plan import build_dispatch_plan, render_plan_markdown  # noqa: E402


class CollabPlanTests(unittest.TestCase):
    def test_dispatch_plan_has_stable_sections_and_agent_order(self):
        config = load_config()
        plan = build_dispatch_plan(
            config,
            intent="Implement the collab plugin skeleton.",
            decisions=["No UI shell in the first patch."],
            boundaries=["Do not edit hooks."],
            task="Create deterministic plan payloads.",
        )

        self.assertEqual([item["agent"] for item in plan["dispatches"]], [agent.name for agent in config.agents])
        first_prompt = plan["dispatches"][0]["prompt"]
        self.assertIn("Intent:\nImplement the collab plugin skeleton.", first_prompt)
        self.assertIn("Decisions:\n- No UI shell in the first patch.", first_prompt)
        self.assertIn("Boundaries:\n- Do not edit hooks.", first_prompt)
        self.assertIn("Task:\nCreate deterministic plan payloads.", first_prompt)
        self.assertIn("Report Contract:", first_prompt)

    def test_plan_payload_is_host_neutral(self):
        plan = build_dispatch_plan(load_config(), intent="Check host neutrality.")
        encoded = json.dumps(plan, ensure_ascii=False).lower()

        self.assertNotIn("electron", encoded)
        self.assertNotIn("localdb", encoded)
        self.assertNotIn("xdt-maker-main", encoded)
        self.assertTrue(all(item["adapter"]["spawns_process"] is False for item in plan["dispatches"]))

    def test_plan_id_is_stable_for_same_inputs(self):
        config = load_config()

        first = build_dispatch_plan(config, intent="Stable id.", decisions=["same"])
        second = build_dispatch_plan(config, intent="Stable id.", decisions=["same"])
        changed = build_dispatch_plan(config, intent="Stable id.", decisions=["different"])

        self.assertEqual(first["plan_id"], second["plan_id"])
        self.assertNotEqual(first["plan_id"], changed["plan_id"])

    def test_adapter_contracts_are_lookupable_and_do_not_spawn_processes(self):
        self.assertIn("codex", ADAPTER_CONTRACTS)
        self.assertIn("claude-code", ADAPTER_CONTRACTS)
        self.assertIn("orca", ADAPTER_CONTRACTS)

        contract = get_adapter_contract("codex")

        self.assertFalse(contract.spawns_process)
        self.assertIn("dispatch_plan", contract.payload_kind)

    def test_markdown_render_mentions_each_agent_once(self):
        plan = build_dispatch_plan(load_config(), intent="Summarize collaboration work.")
        markdown = render_plan_markdown(plan)

        for agent_name in ["find", "designer", "dev", "test", "main"]:
            self.assertEqual(markdown.count(f"### {agent_name}"), 1)

    def test_cli_json_smoke_outputs_dispatches(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "collab_plan.py"
        result = subprocess.run(
            [sys.executable, str(script), "--intent", "CLI smoke", "--json"],
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)

        self.assertEqual(payload["workflow"], "global-memory-collab")
        self.assertEqual(len(payload["dispatches"]), 5)
        self.assertEqual(payload["dispatches"][0]["agent"], "find")


if __name__ == "__main__":
    unittest.main()
