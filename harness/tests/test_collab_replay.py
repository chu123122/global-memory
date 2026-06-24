import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.config import load_config, parse_config  # noqa: E402
from collab.plan import build_dispatch_plan  # noqa: E402
from collab.replay import ReplayError, build_replay_runbook, render_runbook_markdown  # noqa: E402
from collab.state import state_from_plan, update_dispatch  # noqa: E402


class CollabReplayTests(unittest.TestCase):
    def test_runbook_skips_done_dispatches_by_default(self):
        plan = build_dispatch_plan(load_config(), intent="Replay.")
        state = update_dispatch(state_from_plan(plan), "01-find", status="done", report="done")

        runbook = build_replay_runbook(plan, state=state, state_path="state.json")

        self.assertEqual(runbook["skipped_done"], 1)
        self.assertEqual(runbook["action_count"], 4)
        self.assertNotIn("01-find", [item["dispatch_id"] for item in runbook["actions"]])
        self.assertIn("--dispatch-id 02-designer", runbook["actions"][0]["state_update_commands"]["mark running"])

    def test_runbook_can_include_done_for_audit(self):
        plan = build_dispatch_plan(load_config(), intent="Replay.")
        state = update_dispatch(state_from_plan(plan), "01-find", status="done", report="done")

        runbook = build_replay_runbook(plan, state=state, include_done=True)

        self.assertEqual(runbook["action_count"], 5)
        self.assertEqual(runbook["actions"][0]["status"], "done")

    def test_runbook_filters_adapter(self):
        config = parse_config({
            "schema_version": 1,
            "workflow": "global-memory-collab",
            "defaults": {
                "client": "codex",
                "model": "gpt-5.5",
                "reasoning_effort": "medium",
                "permission_mode": "ask",
            },
            "agents": [
                {"name": "find", "role": "source locator", "client": "manual"},
                {"name": "designer", "role": "architecture designer", "client": "orca"},
                {"name": "dev", "role": "implementation"},
                {"name": "test", "role": "verification"},
                {"name": "main", "role": "documentation and state"},
            ],
        })
        plan = build_dispatch_plan(config, intent="Filter.")

        runbook = build_replay_runbook(plan, adapter="orca")

        self.assertEqual(runbook["action_count"], 1)
        self.assertEqual(runbook["actions"][0]["adapter"], "orca")
        self.assertEqual(runbook["actions"][0]["tool"]["name"], "create_worker")

    def test_runbook_rejects_state_plan_mismatch(self):
        plan = build_dispatch_plan(load_config(), intent="Plan A.")
        other_state = state_from_plan(build_dispatch_plan(load_config(), intent="Plan B."))

        with self.assertRaisesRegex(ReplayError, "does not match"):
            build_replay_runbook(plan, state=other_state)

    def test_markdown_contains_payload_and_prompt(self):
        runbook = build_replay_runbook(build_dispatch_plan(load_config(), intent="Markdown."))

        markdown = render_runbook_markdown(runbook)

        self.assertIn("# Collaboration Replay Runbook", markdown)
        self.assertIn("### Runtime payload", markdown)
        self.assertIn("### State update examples", markdown)
        self.assertIn("Intent:\\nMarkdown.", json.dumps(runbook, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
