#!/usr/bin/env python3
"""
test_lib.py — Phase 4-A 4A-V0 验收用例
覆盖 _lib.py 的 4 个新工具:is_windows / _file_lock / _atomic_append_jsonl / rotate_log
"""

import json
import os
import sys
import tempfile
import unittest
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _lib import is_windows, _atomic_append_jsonl, rotate_log


def _writer_worker(args):
    """multiprocessing pool 的 worker:append N 条记录到目标 jsonl"""
    path, prefix, n = args
    for i in range(n):
        _atomic_append_jsonl(Path(path), {"writer": prefix, "i": i})
    return n


class TestIsWindows(unittest.TestCase):
    def test_returns_bool(self):
        result = is_windows()
        self.assertIsInstance(result, bool)
        # 跟 sys.platform 一致
        self.assertEqual(result, sys.platform == "win32")


class TestAtomicAppendJsonl(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "test.jsonl"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_single_writer(self):
        """单进程 append 100 次,验证行数 = 100 且每行合法 JSON"""
        for i in range(100):
            _atomic_append_jsonl(self.path, {"i": i, "msg": f"row-{i}"})
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 100)
        for j, line in enumerate(lines):
            obj = json.loads(line)  # 不抛异常 = 合法 JSON
            self.assertEqual(obj["i"], j)

    def test_concurrent_writers(self):
        """5 进程各 append 20 行,共 100 行 + 无错乱"""
        targets = [(str(self.path), f"w{w}", 20) for w in range(5)]
        with Pool(5) as pool:
            results = pool.map(_writer_worker, targets)
        self.assertEqual(sum(results), 100)
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 100)
        # 每行均合法 JSON,且 writer/i 字段均存在
        for line in lines:
            obj = json.loads(line)
            self.assertIn("writer", obj)
            self.assertIn("i", obj)


class TestRotateLog(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "test.jsonl"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_rotate_below_threshold(self):
        """文件未超阈值 → 返回 False,文件不变"""
        self.path.write_text("a\nb\nc\n", encoding="utf-8")
        rotated = rotate_log(self.path, max_size_bytes=10000, max_lines=10000, keep=3)
        self.assertFalse(rotated)
        self.assertTrue(self.path.exists())
        self.assertFalse(self.path.with_suffix(".jsonl.0").exists())

    def test_rotate_by_size(self):
        """文件大小超 max_size_bytes → 滚动到 .0,新文件为空"""
        self.path.write_text("x" * 200, encoding="utf-8")
        rotated = rotate_log(self.path, max_size_bytes=100, max_lines=10000, keep=3)
        self.assertTrue(rotated)
        self.assertTrue(self.path.with_suffix(".jsonl.0").exists())
        self.assertEqual(self.path.read_text(encoding="utf-8"), "")

    def test_rotate_by_lines(self):
        """文件行数超 max_lines → 触发轮转"""
        self.path.write_text("\n".join(str(i) for i in range(150)) + "\n", encoding="utf-8")
        rotated = rotate_log(self.path, max_size_bytes=10 * 1024 * 1024, max_lines=100, keep=3)
        self.assertTrue(rotated)
        self.assertTrue(self.path.with_suffix(".jsonl.0").exists())

    def test_rotate_keep_n(self):
        """连续 keep+1 次轮转,最旧的 .keep-1 被丢弃"""
        # 准备 keep=3 → .0/.1/.2 三份
        for round_i in range(4):  # 4 次写入 + 轮转
            self.path.write_text(f"round-{round_i}\n" * 50, encoding="utf-8")
            rotate_log(self.path, max_size_bytes=10, max_lines=10000, keep=3)
        # 最终文件状态:current 空 + .0(round-3) + .1(round-2) + .2(round-1);round-0 已丢弃
        self.assertTrue(self.path.with_suffix(".jsonl.0").exists())
        self.assertTrue(self.path.with_suffix(".jsonl.1").exists())
        self.assertTrue(self.path.with_suffix(".jsonl.2").exists())
        # .3 不应该存在(被 keep=3 限制)
        self.assertFalse(self.path.with_suffix(".jsonl.3").exists())
        # 验证 .0 是最新被滚动的(round-3 是最后一次写入,所以 .0 是 round-3 的内容)
        content_0 = self.path.with_suffix(".jsonl.0").read_text(encoding="utf-8")
        self.assertIn("round-3", content_0)
        # .2 应该是最早保留的(round-1)
        content_2 = self.path.with_suffix(".jsonl.2").read_text(encoding="utf-8")
        self.assertIn("round-1", content_2)


if __name__ == "__main__":
    unittest.main()
