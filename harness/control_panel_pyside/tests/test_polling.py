"""polling.read_incremental 单元测试。

直接跑：
    python -m control_panel_pyside.tests.test_polling

REVIEW-2026-04-24-1814 中的 🟢 低风险条目之一：JSONL 半行/损坏行/rotate 边界。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# 同目录 import 兜底（不依赖 pytest）
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from control_panel_pyside.polling import read_incremental  # noqa: E402


def _writeln(path: Path, *records: dict) -> None:
    with path.open("ab") as f:
        for r in records:
            f.write((json.dumps(r) + "\n").encode("utf-8"))


def _writeraw(path: Path, s: str) -> None:
    with path.open("ab") as f:
        f.write(s.encode("utf-8"))


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.jsonl"

        # T1 完整 N 行：offset 应推进到 size
        p.write_bytes(b"")
        _writeln(p, {"a": 1}, {"a": 2}, {"a": 3})
        events, off = read_incremental(p, 0)
        assert len(events) == 3
        assert off == p.stat().st_size
        print(f"[T1] 完整 3 行 OK")

        # T2 半行回退：offset 不前进到半行
        _writeln(p, {"a": 4})
        _writeraw(p, '{"a": 5')
        events, new_off = read_incremental(p, off)
        size = p.stat().st_size
        assert len(events) == 1 and events[0]["a"] == 4
        assert size - new_off == 7  # 半行未消耗
        print(f"[T2] 半行回退 OK（剩 {size - new_off}B）")

        # T3 半行补齐 → 下一轮读取
        _writeraw(p, ', "b": 99}\n')
        events, final_off = read_incremental(p, new_off)
        assert len(events) == 1 and events[0] == {"a": 5, "b": 99}
        assert final_off == p.stat().st_size
        print(f"[T3] 半行补齐后读取 OK")

        # T4 损坏行跳过，offset 仍推进
        _writeraw(p, "not-json\n")
        _writeln(p, {"a": 6})
        events, _ = read_incremental(p, final_off)
        assert len(events) == 1 and events[0]["a"] == 6
        print(f"[T4] 损坏行跳过 OK")

        # T5 文件 rotate（size 变小）reset 到 0 重读
        p.write_bytes((json.dumps({"a": 999}) + "\n").encode("utf-8"))
        events, _ = read_incremental(p, 99999)
        assert len(events) == 1 and events[0]["a"] == 999
        print(f"[T5] rotate 检测 OK")

    print("\n[OK] all 5 polling tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
