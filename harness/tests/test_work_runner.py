import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from work_runner import (  # noqa: E402
    FORBIDDEN_FAILURE_CODE,
    PROCESS_FAIL,
    PROCESS_PASS,
    REPAIR_LIMIT_CODE,
    RUNNER_INFRA_FAIL,
    VERIFIER_FAILURE_CODE,
    WorkRunnerError,
    check_once,
    repair_loop,
    run_once,
)


class WorkRunnerTests(unittest.TestCase):
    def test_fake_fail_does_not_advance_and_writes_feedback_and_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_once(run_root=tmp, task_id="demo", step="GM-R1", worker="fake", fake_result="fail")
            root = Path(tmp)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            feedback = json.loads((root / "gate-feedback.json").read_text(encoding="utf-8"))
            log_lines = (root / "runner-log.jsonl").read_text(encoding="utf-8").splitlines()
            last_event = json.loads(log_lines[-1])

        self.assertEqual(result["verdict"], PROCESS_FAIL)
        self.assertEqual(state["current_step"], "GM-R1")
        self.assertEqual(state["status"], "running")
        self.assertEqual(feedback["gate"], PROCESS_FAIL)
        self.assertEqual(feedback["blocked_before"], "GM-R1")
        self.assertEqual(last_event["event"], PROCESS_FAIL)

    def test_fake_pass_advances_to_allowed_next_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run-state.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "task_id": "demo",
                        "profile": "work-runner/v1",
                        "worker_kind": "fake",
                        "current_step": "GM-R1",
                        "allowed_next_step": "GM-R2",
                        "attempt": 0,
                        "max_attempts_per_gate": 3,
                        "last_gate": None,
                        "blocked_before": None,
                        "failure_streak": 0,
                        "status": "running",
                    }
                ),
                encoding="utf-8",
            )

            result = run_once(run_root=root, task_id="demo", step="GM-R1", worker="fake", fake_result="pass")
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))

        self.assertEqual(result["verdict"], PROCESS_PASS)
        self.assertEqual(state["current_step"], "GM-R2")
        self.assertEqual(state["last_gate"], PROCESS_PASS)
        self.assertEqual(state["failure_streak"], 0)

    def test_three_consecutive_failures_block_same_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for _ in range(3):
                run_once(run_root=root, task_id="demo", step="GM-R1", worker="fake", fake_result="fail")
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))

        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["blocked_before"], "GM-R1")
        self.assertEqual(state["failure_streak"], 3)

    def test_touch_forbidden_forces_fail_even_when_worker_claims_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_once(run_root=root, task_id="demo", step="GM-R1", worker="fake", fake_result="touch-forbidden")
            worker_output = json.loads((root / "worker-output" / "fake-worker.json").read_text(encoding="utf-8"))
            feedback = json.loads((root / "gate-feedback.json").read_text(encoding="utf-8"))

        self.assertEqual(worker_output["result"], "pass")
        self.assertEqual(result["verdict"], PROCESS_FAIL)
        self.assertEqual(feedback["failure_code"], FORBIDDEN_FAILURE_CODE)
        self.assertIn("run-state.json", feedback["forbidden_paths"])

    def test_worker_output_declaring_runner_owned_state_modification_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_once(
                run_root=root,
                task_id="demo",
                step="GM-R1",
                worker="fake",
                fake_result="pass",
                fake_declared_modified_paths=["run-state.json"],
            )
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            feedback = json.loads((root / "gate-feedback.json").read_text(encoding="utf-8"))

        self.assertEqual(result["verdict"], PROCESS_FAIL)
        self.assertEqual(state["current_step"], "GM-R1")
        self.assertEqual(feedback["failure_code"], FORBIDDEN_FAILURE_CODE)

    @patch("work_runner.subprocess.run")
    def test_check_verifier_fail_writes_feedback_without_worker_artifacts(self, run_mock):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            run_mock.return_value = subprocess.CompletedProcess(["verifier-spy"], 9, stdout=b"", stderr=b"bad")

            result = check_once(
                run_root=root,
                task_id="demo",
                step="GM-R3",
                repo_root=repo_tmp,
                allowed_next_step="GM-R4",
                verifier_commands=[["verifier-spy"]],
            )
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            feedback = json.loads((root / "gate-feedback.json").read_text(encoding="utf-8"))
            log_event = json.loads((root / "runner-log.jsonl").read_text(encoding="utf-8").splitlines()[-1])

        self.assertEqual(result["verdict"], PROCESS_FAIL)
        self.assertEqual(result["worker"], "verifier-only")
        self.assertEqual(state["current_step"], "GM-R3")
        self.assertEqual(state["last_gate"], PROCESS_FAIL)
        self.assertEqual(state["repair_attempt"], 0)
        self.assertEqual(feedback["repair_attempt"], 0)
        self.assertEqual(state["failure_streak"], 0)
        self.assertEqual(state["status"], "running")
        self.assertEqual(feedback["failure_kind"], "verifier")
        self.assertEqual(feedback["gate_exit_code"], 9)
        self.assertEqual(feedback["gate_command"], ["verifier-spy"])
        self.assertEqual(log_event["worker"], "verifier-only")
        self.assertEqual(log_event["gate_exit_code"], 9)
        self.assertFalse((root / "worker-input" / "prompt.md").exists())
        self.assertFalse((root / "worker-output" / "codex-exec.jsonl").exists())

    @patch("work_runner.subprocess.run")
    def test_check_verifier_pass_advances_only_with_allowed_next_step(self, run_mock):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            run_mock.return_value = subprocess.CompletedProcess(["verifier-spy"], 0, stdout=b"ok", stderr=b"")

            result = check_once(
                run_root=root,
                task_id="demo",
                step="GM-R3",
                repo_root=repo_tmp,
                allowed_next_step="GM-R4",
                verifier_commands=[["verifier-spy"]],
            )
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))

        self.assertEqual(result["verdict"], PROCESS_PASS)
        self.assertEqual(state["current_step"], "GM-R4")
        self.assertEqual(state["last_gate"], PROCESS_PASS)
        self.assertFalse((root / "worker-output" / "codex-exec.jsonl").exists())

    @patch("work_runner.subprocess.run")
    def test_codex_exec_writes_prompt_jsonl_last_message_and_runs_verifier(self, run_mock):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            repo = Path(repo_tmp)
            codex_stdout = b'{"type":"final","message":"worker says done"}\n'
            run_mock.side_effect = [
                subprocess.CompletedProcess(["fake-codex"], 0, stdout=codex_stdout, stderr=b""),
                subprocess.CompletedProcess(["verifier-spy"], 0, stdout=b"ok\n", stderr=b""),
            ]

            result = run_once(
                run_root=root,
                task_id="demo",
                step="GM-R2",
                worker="codex-exec",
                repo_root=repo,
                allowed_next_step="GM-R3",
                codex_command="fake-codex",
                verifier_commands=[["verifier-spy"]],
            )
            prompt_path = root / "worker-input" / "prompt.md"
            jsonl_path = root / "worker-output" / "codex-exec.jsonl"
            last_message_path = root / "worker-output" / "last-message.md"
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            log_event = json.loads((root / "runner-log.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            jsonl_bytes = jsonl_path.read_bytes()
            last_message = last_message_path.read_text(encoding="utf-8")
            prompt = prompt_path.read_text(encoding="utf-8")

        self.assertEqual(result["verdict"], PROCESS_PASS)
        self.assertEqual(state["current_step"], "GM-R3")
        self.assertEqual(jsonl_bytes, codex_stdout)
        self.assertIn("worker says done", last_message)
        self.assertIn("run-state.json", prompt)
        self.assertIn("gate-feedback.json", prompt)
        self.assertIn("runner-log.jsonl", prompt)
        first_command = run_mock.call_args_list[0].args[0]
        self.assertEqual(first_command[:5], ["fake-codex", "exec", "--json", "--sandbox", "workspace-write"])
        self.assertIn("--cd", first_command)
        self.assertIn(str(repo), first_command)
        self.assertEqual(log_event["prompt_path"], str(prompt_path))
        self.assertEqual(log_event["worker_jsonl_path"], str(jsonl_path))
        self.assertEqual(log_event["last_message_path"], str(last_message_path))
        self.assertEqual(log_event["gate_exit_code"], 0)
        self.assertEqual(log_event["worker_exit_code"], 0)

    @patch("work_runner.subprocess.run")
    def test_codex_verifier_fail_does_not_advance_even_when_worker_claims_done(self, run_mock):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            run_mock.side_effect = [
                subprocess.CompletedProcess(["fake-codex"], 0, stdout=b'{"message":"DONE"}\n', stderr=b""),
                subprocess.CompletedProcess(["verifier-spy"], 7, stdout=b"", stderr=b"nope"),
            ]

            result = run_once(
                run_root=root,
                task_id="demo",
                step="GM-R2",
                worker="codex-exec",
                repo_root=repo_tmp,
                allowed_next_step="GM-R3",
                codex_command="fake-codex",
                verifier_commands=[["verifier-spy"]],
            )
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            feedback = json.loads((root / "gate-feedback.json").read_text(encoding="utf-8"))
            log_event = json.loads((root / "runner-log.jsonl").read_text(encoding="utf-8").splitlines()[-1])

        self.assertEqual(result["verdict"], PROCESS_FAIL)
        self.assertEqual(state["current_step"], "GM-R2")
        self.assertEqual(state["last_gate"], PROCESS_FAIL)
        self.assertEqual(feedback["failure_code"], VERIFIER_FAILURE_CODE)
        self.assertEqual(feedback["gate_exit_code"], 7)
        self.assertEqual(log_event["gate_exit_code"], 7)

    @patch("work_runner.subprocess.run")
    def test_codex_nonzero_is_runner_infra_fail_and_does_not_advance_state(self, run_mock):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            run_mock.return_value = subprocess.CompletedProcess(["fake-codex"], 2, stdout=b'{"message":"failed"}\n', stderr=b"boom")

            result = run_once(
                run_root=root,
                task_id="demo",
                step="GM-R2",
                worker="codex-exec",
                repo_root=repo_tmp,
                allowed_next_step="GM-R3",
                codex_command="fake-codex",
                verifier_commands=[["verifier-spy"]],
            )
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            feedback = json.loads((root / "gate-feedback.json").read_text(encoding="utf-8"))
            log_event = json.loads((root / "runner-log.jsonl").read_text(encoding="utf-8").splitlines()[-1])

        self.assertEqual(result["verdict"], RUNNER_INFRA_FAIL)
        self.assertEqual(state["current_step"], "GM-R2")
        self.assertIsNone(state["last_gate"])
        self.assertEqual(feedback["failure_kind"], "runner-infra")
        self.assertEqual(feedback["worker_exit_code"], 2)
        self.assertEqual(log_event["failure_kind"], "runner-infra")
        self.assertEqual(log_event["worker_exit_code"], 2)
        self.assertEqual(run_mock.call_count, 1)

    @patch("work_runner.subprocess.run")
    def test_codex_timeout_is_runner_infra_fail(self, run_mock):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            run_mock.side_effect = subprocess.TimeoutExpired(cmd=["fake-codex"], timeout=1, output=b"partial")

            result = run_once(
                run_root=root,
                task_id="demo",
                step="GM-R2",
                worker="codex-exec",
                repo_root=repo_tmp,
                timeout_sec=1,
                codex_command="fake-codex",
                verifier_commands=[["verifier-spy"]],
            )
            feedback = json.loads((root / "gate-feedback.json").read_text(encoding="utf-8"))

        self.assertEqual(result["verdict"], RUNNER_INFRA_FAIL)
        self.assertEqual(feedback["failure_kind"], "runner-infra")
        self.assertIn("timed out", feedback["message"])


    @patch("work_runner.subprocess.run")
    def test_repair_pass_after_check_runs_one_worker_and_stops(self, run_mock):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            run_mock.side_effect = [
                subprocess.CompletedProcess(["verifier-spy"], 7, stdout=b"", stderr=b"red"),
                subprocess.CompletedProcess(["fake-codex"], 0, stdout=b'{"message":"fixed"}\n', stderr=b""),
                subprocess.CompletedProcess(["verifier-spy"], 0, stdout=b"green", stderr=b""),
            ]

            check_once(
                run_root=root,
                task_id="demo",
                step="GM-R3",
                repo_root=repo_tmp,
                allowed_next_step="GM-R4",
                verifier_commands=[["verifier-spy"]],
            )
            result = repair_loop(
                run_root=root,
                task_id="demo",
                step="GM-R3",
                worker="codex-exec",
                repo_root=repo_tmp,
                allowed_next_step="GM-R4",
                codex_command="fake-codex",
                verifier_commands=[["verifier-spy"]],
            )
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))

        self.assertEqual(result["verdict"], PROCESS_PASS)
        self.assertEqual(state["current_step"], "GM-R4")
        self.assertEqual(state["repair_attempt"], 1)
        self.assertEqual(state["max_repair_attempts"], 3)
        self.assertEqual(run_mock.call_count, 3)

    @patch("work_runner.subprocess.run")
    def test_repair_three_verifier_failures_blocks_with_limit_feedback(self, run_mock):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            run_mock.side_effect = [
                subprocess.CompletedProcess(["verifier-spy"], 7, stdout=b"", stderr=b"red"),
                subprocess.CompletedProcess(["fake-codex"], 0, stdout=b'{"message":"try1"}\n', stderr=b""),
                subprocess.CompletedProcess(["verifier-spy"], 7, stdout=b"", stderr=b"nope1"),
                subprocess.CompletedProcess(["fake-codex"], 0, stdout=b'{"message":"try2"}\n', stderr=b""),
                subprocess.CompletedProcess(["verifier-spy"], 7, stdout=b"", stderr=b"nope2"),
                subprocess.CompletedProcess(["fake-codex"], 0, stdout=b'{"message":"try3"}\n', stderr=b""),
                subprocess.CompletedProcess(["verifier-spy"], 7, stdout=b"", stderr=b"nope3"),
            ]

            check_once(
                run_root=root,
                task_id="demo",
                step="GM-R3",
                repo_root=repo_tmp,
                verifier_commands=[["verifier-spy"]],
            )
            result = repair_loop(
                run_root=root,
                task_id="demo",
                step="GM-R3",
                worker="codex-exec",
                repo_root=repo_tmp,
                codex_command="fake-codex",
                verifier_commands=[["verifier-spy"]],
            )
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            feedback = json.loads((root / "gate-feedback.json").read_text(encoding="utf-8"))

        self.assertEqual(result["verdict"], PROCESS_FAIL)
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["repair_attempt"], 3)
        self.assertEqual(state["max_repair_attempts"], 3)
        self.assertEqual(feedback["failure_code"], REPAIR_LIMIT_CODE)
        self.assertEqual(feedback["failure_kind"], "repair-limit")
        self.assertEqual(feedback["repair_attempt"], 3)
        self.assertEqual(feedback["max_repair_attempts"], 3)
        self.assertEqual(feedback["gate_exit_code"], 7)
        self.assertEqual(feedback["gate_command"], ["verifier-spy"])
        self.assertEqual(run_mock.call_count, 7)

    @patch("work_runner.subprocess.run")
    def test_repair_fourth_call_does_not_start_worker(self, run_mock):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run-state.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "task_id": "demo",
                        "profile": "work-runner/v1",
                        "worker_kind": "codex-exec",
                        "current_step": "GM-R3",
                        "attempt": 3,
                        "max_attempts_per_gate": 3,
                        "repair_attempt": 3,
                        "max_repair_attempts": 3,
                        "last_gate": PROCESS_FAIL,
                        "blocked_before": "GM-R3",
                        "failure_streak": 3,
                        "status": "blocked",
                    }
                ),
                encoding="utf-8",
            )
            (root / "gate-feedback.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "work_runner_gate_feedback",
                        "task_id": "demo",
                        "step": "GM-R3",
                        "gate": PROCESS_FAIL,
                        "failure_code": VERIFIER_FAILURE_CODE,
                        "failure_kind": "verifier",
                        "gate_exit_code": 7,
                        "gate_command": ["verifier-spy"],
                    }
                ),
                encoding="utf-8",
            )

            result = repair_loop(
                run_root=root,
                task_id="demo",
                step="GM-R3",
                worker="codex-exec",
                codex_command="fake-codex",
                verifier_commands=[["verifier-spy"]],
            )
            feedback = json.loads((root / "gate-feedback.json").read_text(encoding="utf-8"))

        self.assertEqual(result["verdict"], PROCESS_FAIL)
        self.assertEqual(feedback["failure_code"], REPAIR_LIMIT_CODE)
        self.assertEqual(run_mock.call_count, 0)

    @patch("work_runner.subprocess.run")
    def test_repair_runner_infra_fail_stops_immediately(self, run_mock):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            (root / "gate-feedback.json").write_text(
                json.dumps({"schema_version": 1, "kind": "work_runner_gate_feedback", "task_id": "demo", "step": "GM-R3", "gate": PROCESS_FAIL}),
                encoding="utf-8",
            )
            run_mock.return_value = subprocess.CompletedProcess(["fake-codex"], 2, stdout=b'{"message":"boom"}\n', stderr=b"boom")

            result = repair_loop(
                run_root=root,
                task_id="demo",
                step="GM-R3",
                worker="codex-exec",
                repo_root=repo_tmp,
                codex_command="fake-codex",
                verifier_commands=[["verifier-spy"]],
            )
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            feedback = json.loads((root / "gate-feedback.json").read_text(encoding="utf-8"))

        self.assertEqual(result["verdict"], RUNNER_INFRA_FAIL)
        self.assertEqual(state["repair_attempt"], 1)
        self.assertEqual(feedback["failure_kind"], "runner-infra")
        self.assertEqual(run_mock.call_count, 1)

    def test_repair_requires_process_fail_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(WorkRunnerError):
                repair_loop(run_root=root, task_id="demo", step="GM-R3", worker="codex-exec")

            (root / "gate-feedback.json").write_text(
                json.dumps({"schema_version": 1, "kind": "work_runner_gate_feedback", "task_id": "demo", "step": "GM-R3", "gate": PROCESS_PASS}),
                encoding="utf-8",
            )
            with self.assertRaises(WorkRunnerError):
                repair_loop(run_root=root, task_id="demo", step="GM-R3", worker="codex-exec")

    def test_cli_smoke_emits_json_for_gate_fail(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "work_runner.py"
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "run",
                    "--worker",
                    "fake",
                    "--fake-result",
                    "fail",
                    "--run-root",
                    tmp,
                    "--task-id",
                    "demo",
                    "--step",
                    "GM-R1",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

        self.assertEqual(payload["verdict"], PROCESS_FAIL)
        self.assertEqual(payload["feedback"]["blocked_before"], "GM-R1")

    def test_cli_check_accepts_verifier_json_and_does_not_write_codex_jsonl(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "work_runner.py"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            verifier = json.dumps([sys.executable, "-c", "import sys; sys.exit(5)"])
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "check",
                    "--verifier-command",
                    verifier,
                    "--repo-root",
                    repo_tmp,
                    "--allowed-next-step",
                    "GM-R4",
                    "--run-root",
                    tmp,
                    "--task-id",
                    "demo",
                    "--step",
                    "GM-R3",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)
            jsonl_exists = (root / "worker-output" / "codex-exec.jsonl").exists()

        self.assertEqual(payload["verdict"], PROCESS_FAIL)
        self.assertEqual(payload["worker"], "verifier-only")
        self.assertEqual(payload["feedback"]["gate_exit_code"], 5)
        self.assertFalse(jsonl_exists)


    def test_cli_repair_accepts_fake_command_and_verifier_json(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "work_runner.py"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            fake_codex = _write_fake_codex_command(root)
            (root / "gate-feedback.json").write_text(
                json.dumps({"schema_version": 1, "kind": "work_runner_gate_feedback", "task_id": "demo", "step": "GM-R3", "gate": PROCESS_FAIL}),
                encoding="utf-8",
            )
            verifier = json.dumps([sys.executable, "-c", "import sys; sys.exit(0)"])
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "repair",
                    "--worker",
                    "codex-exec",
                    "--codex-command",
                    str(fake_codex),
                    "--verifier-command",
                    verifier,
                    "--repo-root",
                    repo_tmp,
                    "--allowed-next-step",
                    "GM-R4",
                    "--run-root",
                    tmp,
                    "--task-id",
                    "demo",
                    "--step",
                    "GM-R3",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

        self.assertEqual(payload["verdict"], PROCESS_PASS)
        self.assertEqual(payload["state"]["current_step"], "GM-R4")
        self.assertEqual(payload["state"]["repair_attempt"], 1)

    def test_cli_codex_exec_accepts_fake_command_and_verifier_json(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "work_runner.py"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(tmp)
            fake_codex = _write_fake_codex_command(root)
            verifier = json.dumps([sys.executable, "-c", "import sys; sys.exit(0)"])
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "run",
                    "--worker",
                    "codex-exec",
                    "--codex-command",
                    str(fake_codex),
                    "--verifier-command",
                    verifier,
                    "--repo-root",
                    repo_tmp,
                    "--allowed-next-step",
                    "GM-R3",
                    "--run-root",
                    tmp,
                    "--task-id",
                    "demo",
                    "--step",
                    "GM-R2",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)
            jsonl_exists = (root / "worker-output" / "codex-exec.jsonl").exists()

        self.assertEqual(payload["verdict"], PROCESS_PASS)
        self.assertEqual(payload["state"]["current_step"], "GM-R3")
        self.assertTrue(jsonl_exists)


def _write_fake_codex_command(root: Path) -> Path:
    if os.name == "nt":
        path = root / "fake_codex.cmd"
        path.write_text('@echo {"message":"cli fake done"}\r\n', encoding="utf-8")
        return path
    path = root / "fake_codex.sh"
    path.write_text('#!/usr/bin/env sh\nprintf \'{"message":"cli fake done"}\\n\'\n', encoding="utf-8")
    path.chmod(0o755)
    return path


if __name__ == "__main__":
    unittest.main()
