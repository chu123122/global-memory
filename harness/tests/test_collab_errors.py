import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collab.errors import CollabError, error_payload, code_for_exception  # noqa: E402
from collab.state import StateError  # noqa: E402


STATE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collab_state.py"


class CollabErrorTests(unittest.TestCase):
    def test_error_payload_preserves_kind_error_and_adds_code(self):
        payload = error_payload("collab_state_error", StateError("bad state"))

        self.assertEqual(payload["kind"], "collab_state_error")
        self.assertEqual(payload["error"], "bad state")
        self.assertEqual(payload["error_code"], "COLLAB_STATE_INVALID")

    def test_collab_error_subclass_code_is_stable(self):
        exc = CollabError("boom", error_code="COLLAB_QUEUE_EMPTY")

        self.assertEqual(code_for_exception(exc), "COLLAB_QUEUE_EMPTY")
        self.assertEqual(exc.to_dict()["error_code"], "COLLAB_QUEUE_EMPTY")


class CollabCliErrorContractTests(unittest.TestCase):
    def test_existing_cli_json_error_keeps_kind_error_and_adds_error_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-state.json"
            result = subprocess.run(
                [sys.executable, str(STATE_SCRIPT), "--state", str(missing), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["kind"], "collab_state_error")
        self.assertIn("failed to read state", payload["error"])
        self.assertEqual(payload["error_code"], "COLLAB_STATE_INVALID")


if __name__ == "__main__":
    unittest.main()
