#!/usr/bin/env python3
"""
test_panel_api.py — Phase 4-A 4A-V0.5 / 4A-V1 / 4A-V2 验收用例
覆盖 panel_api.py 的 outcome 子命令:schema、调用链、错误处理
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent.parent
PANEL_API = HARNESS_DIR / "panel_api.py"


def run_outcome(env_home, *args):
    """跑 panel_api.py outcome,临时 HOME 隔离日志文件"""
    proc = subprocess.run(
        [sys.executable, str(PANEL_API), "outcome", *args],
        capture_output=True, text=True, encoding="utf-8",
        env={**__import__("os").environ, "HOME": str(env_home), "USERPROFILE": str(env_home)},
    )
    return proc


class TestOutcomeWrite(unittest.TestCase):
    """4A-V1: outcome 子命令可写入 1 条记录"""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.outcome_path = self.tmpdir / ".claude" / "logs" / "task_outcomes.jsonl"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_write_single_record(self):
        proc = run_outcome(
            self.tmpdir,
            "--task", "test-task",
            "--phase", "0",
            "--outcome", "completed",
            "--rework", "1",
            "--tools", "17",
            "--lesson", "first record",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertTrue(self.outcome_path.exists())
        lines = self.outcome_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["task"], "test-task")
        self.assertEqual(record["phase"], "0")
        self.assertEqual(record["outcome"], "completed")
        self.assertEqual(record["metrics"]["rework_count"], 1)
        self.assertEqual(record["metrics"]["tool_calls"], 17)
        self.assertEqual(record["lesson"], "first record")
        self.assertIn("ts", record)

    def test_phase_optional(self):
        """phase 字段可省"""
        proc = run_outcome(
            self.tmpdir,
            "--task", "task-no-phase",
            "--outcome", "completed",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        record = json.loads(self.outcome_path.read_text(encoding="utf-8").splitlines()[0])
        self.assertNotIn("phase", record)


class TestOutcomeSchema(unittest.TestCase):
    """4A-V2: schema 校验拒绝缺必填字段 / 非法值"""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_task_rejected(self):
        proc = run_outcome(
            self.tmpdir,
            "--outcome", "completed",
        )
        self.assertNotEqual(proc.returncode, 0)
        # argparse 错误信息 → 包含 "required" 或 "task"
        self.assertTrue(
            "required" in proc.stderr.lower() or "--task" in proc.stderr,
            msg=f"stderr: {proc.stderr}",
        )

    def test_missing_outcome_rejected(self):
        proc = run_outcome(
            self.tmpdir,
            "--task", "x",
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_invalid_outcome_rejected(self):
        """outcome 非 enum 值"""
        proc = run_outcome(
            self.tmpdir,
            "--task", "x",
            "--outcome", "wat",
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue(
            "wat" in proc.stderr or "invalid" in proc.stderr.lower(),
            msg=f"stderr: {proc.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
