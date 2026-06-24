import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.web_ui import run_web_ui_smoke  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_web_ui.py"


class CollabWebUiTests(unittest.TestCase):
    def test_smoke_exercises_model_send_report_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_web_ui_smoke(tmp)

        self.assertTrue(payload["api_ok"])
        self.assertTrue(payload["page_controls_present"])
        self.assertEqual(payload["final_summary"]["worker_count"], 2)
        self.assertEqual(payload["reload_preserved_worker_count"], 2)
        self.assertGreater(payload["event_count"], 0)
        self.assertGreaterEqual(payload["router_summary"]["retried"], 1)

    def test_cli_smoke_outputs_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(SCRIPT), "smoke", "--out", tmp, "--json"], check=True, text=True, capture_output=True)
            payload = json.loads(result.stdout)
            artifact = Path(tmp) / "web-ui-smoke.json"
            self.assertTrue(artifact.exists())

        self.assertEqual(payload["kind"], "collab_web_ui_smoke")
        self.assertTrue(payload["api_ok"])


if __name__ == "__main__":
    unittest.main()
