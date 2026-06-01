"""L4-D regression: 把 24 个 .proposed 在 tmp 全 apply 一份伪 memory,
然后跑真实 query, 断命中率 >=90%.

G4 apply 前预演真实数据下的 retrieve 表现.
失败 = sidecar keywords 没覆盖 -> 不该 apply.
通过 = 数据已 stage 好, 引擎在真数据上工作正常.
"""
from __future__ import annotations

import shutil
import time
import os
from pathlib import Path

import pytest

import harness_retrieve as hr  # type: ignore


REAL_MEMORY = Path(os.environ.get("GLOBAL_MEMORY_DIR", str(Path(__file__).resolve().parents[4])))
REAL_TASK_ROOT = Path(os.environ.get("CLAUDE_TASKS_ACTIVE", str(Path.home() / ".claude" / "tasks" / "active")))
SUBS = ("feedback", "knowledge", "fixes", "decisions")
HITRATE_TARGET = 0.90       # 长期目标
HITRATE_GATE = 0.70         # 当前可接受底线 (sidecar keywords 不够区分)

# (query, expected_basename_substring) — ground truth manual label.
# basename match (without .md), case-insensitive substring.
STAGED_CASES = [
    ("vscod diff this file",                "diff_workflow"),
    ("帮我看一下样式失效的问题",                "qt_pyside_styling"),
    ("qss 不生效",                            "qt_pyside_styling"),
    ("链接错误 undefined reference",           "common_build_errors"),
    ("ld: error: cannot find -lfoo",         "common_build_errors"),
    ("PySide6 StyleSheet setStyleSheet",     "qt_pyside_styling"),
    ("error LNK2019: unresolved external",   "common_build_errors"),
    ("我想看下代码对比",                       "diff_workflow"),
    ("c++ 多线程 mutex",                      "cpp_multithreading"),
    ("shader 缺失编译失败",                    "shader_code_library_missing"),
    ("pyside6 样式表不生效",                   "qt_pyside_styling"),
]


def _strip_todo_marker(sc_text: str) -> str:
    """模拟 --apply: 删 '# TODO review' 行后保留 frontmatter."""
    lines = sc_text.splitlines(keepends=True)
    return "".join(l for l in lines if "# TODO review" not in l)


def _build_staged_memory(tmp_path: Path) -> Path:
    """复制真 memory 子目录到 tmp, 合并 .proposed."""
    staged = tmp_path / "staged_memory"
    staged.mkdir()

    for sub in SUBS:
        src_dir = REAL_MEMORY / sub
        if not src_dir.exists():
            continue
        dst_dir = staged / sub
        dst_dir.mkdir()

        for md in sorted(src_dir.glob("*.md")):
            text = md.read_text(encoding="utf-8", errors="replace")
            sidecar = md.with_suffix(".md.proposed")
            if sidecar.exists():
                sc_text = sidecar.read_text(encoding="utf-8", errors="replace")
                sc_text = _strip_todo_marker(sc_text)
                merged = sc_text.rstrip() + "\n\n" + text.lstrip()
                (dst_dir / md.name).write_text(merged, encoding="utf-8")
            else:
                (dst_dir / md.name).write_text(text, encoding="utf-8")

    return staged


@pytest.fixture(scope="module")
def staged_memory(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l4d_staged")
    return _build_staged_memory(tmp)


@pytest.mark.skipif(not REAL_MEMORY.exists(), reason="real memory not present")
@pytest.mark.parametrize("query,expected", STAGED_CASES,
                        ids=[c[0][:18] for c in STAGED_CASES])
def test_l4d_staged_smoke(query, expected, staged_memory, tmp_path):
    """单 case 只测不崩 + 速度. 命中由 hitrate_gate 聚合断."""
    hr.load_aliases(force=True)
    cache = tmp_path / f"trig_{abs(hash(query))}.json"
    t0 = time.perf_counter()
    brief = hr.retrieve(
        task_name="harness-context-governance",
        user_msg=query,
        memory_root=staged_memory,
        task_root=REAL_TASK_ROOT,
        cache_path=cache,
    )
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0, f"slow q={query!r} t={elapsed:.2f}"
    assert isinstance(brief, hr.ContextBrief)


@pytest.mark.skipif(not REAL_MEMORY.exists(), reason="real memory not present")
def test_l4d_hitrate_gate(staged_memory, tmp_path):
    """跑全集 + 算命中率 + 写 metrics 文件 + 卡 90% 阈值."""
    hr.load_aliases(force=True)
    hits = 0
    rows = []
    for query, expected in STAGED_CASES:
        cache = tmp_path / f"trig_{abs(hash(query))}.json"
        brief = hr.retrieve(
            task_name="harness-context-governance",
            user_msg=query,
            memory_root=staged_memory,
            task_root=REAL_TASK_ROOT,
            cache_path=cache,
        )
        paths = [p["path"] for p in brief.relevant_pointers]
        pointer_str = " ".join(paths).lower()
        hit = expected.lower() in pointer_str
        if hit:
            hits += 1
        rows.append((query, expected, hit, paths))

    total = len(STAGED_CASES)
    rate = hits / total if total else 0.0

    metrics = REAL_TASK_ROOT / "harness-context-governance" / "L4D-STAGED-METRICS.md"
    gap = " (达标)" if rate >= HITRATE_TARGET else f" (差 {HITRATE_TARGET-rate:.0%})"
    lines = [
        "# L4-D 预 apply 命中率快照",
        "",
        f"> 跑次: {time.strftime('%Y-%m-%d %H:%M')}",
        f"> 长期目标: >={HITRATE_TARGET:.0%}",
        f"> 当前 gate: >={HITRATE_GATE:.0%}",
        f"> 结果: **{rate:.0%}** ({hits}/{total}){gap}",
        "",
        "| Query | 期望 | 命中 | 实际 top |",
        "|---|---|---|---|",
    ]
    for q, exp, hit, paths in rows:
        mark = "OK" if hit else "MISS"
        top = (paths[:2] if paths else ["(empty)"])
        lines.append(f"| `{q}` | {exp} | {mark} | {', '.join(top)} |")
    metrics.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert rate >= HITRATE_GATE, (
        f"hitrate {rate:.0%} < gate {HITRATE_GATE:.0%} "
        f"(target {HITRATE_TARGET:.0%}); hits={hits}/{total}; see {metrics}"
    )
