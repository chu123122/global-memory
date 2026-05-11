#!/usr/bin/env python3
"""单元测试 · overview_verdict.build_overview_verdict

回归点（必须长期有效）：
  - test_timeline_no_data_does_not_pollute_verdict
    回归 UX-REVIEW D1：token saver 没数据，结论卡 severity 不应被劫持。
    timeline 永远不进 severity 计算——本测试是这条铁律的硬看门人。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from overview_verdict import build_overview_verdict  # noqa: E402


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_in(needle, haystack, label: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"{label}: expected {needle!r} in {haystack!r}")


# ----------------------- 测试样例 -----------------------


def _clean_status() -> dict:
    return {
        "git": {"dirty": False, "ahead": 0, "behind": 0, "change_count": 0},
        "daemon": {"running": True, "process_count": 2},
    }


def _doctor_all_pass() -> dict:
    return {"summary": {"PASS": 6, "WARNING": 0, "ERROR": 0}}


# ----------------------- 4 测试 -----------------------


def test_verdict_all_green() -> None:
    """全绿：4 子系统全 ok → severity ok / headline 一切正常。"""
    v = build_overview_verdict(
        status_json=_clean_status(),
        doctor_summary=_doctor_all_pass(),
        health_signals=[
            {"check_id": "x", "status": "ok", "headline": "ok"},
            {"check_id": "y", "status": "ok", "headline": "ok"},
        ],
    )
    assert_equal(v["severity"], "ok", "全绿 severity")
    assert_equal(v["headline"], "一切正常", "全绿 headline")
    assert_equal(v["next_action"], "无需操作", "全绿 next_action")
    assert_equal(v["primary_button"], None, "Q7 决策：无按钮")
    assert_equal(len(v["subsystems"]), 4, "subsystem 数量")


def test_verdict_takes_max_severity() -> None:
    """子系统级别合并：取最严。一个 warning health signal → 整体 warning。"""
    v = build_overview_verdict(
        status_json=_clean_status(),
        doctor_summary=_doctor_all_pass(),
        health_signals=[
            {"check_id": "x", "status": "ok", "headline": "ok"},
            {"check_id": "y", "status": "warning", "headline": "drift detected"},
        ],
    )
    assert_equal(v["severity"], "warning", "max severity")
    # headline 不再含"Health"字（A2.5 改人话）；用 worst subsystem 的 summary 验证
    health_sub = next(s for s in v["subsystems"] if s["name"] == "Health")
    assert_in(health_sub["summary"], v["headline"], "headline 含 worst subsystem 的 summary")

    # critical 应被映射成 error
    v2 = build_overview_verdict(
        status_json=_clean_status(),
        doctor_summary=_doctor_all_pass(),
        health_signals=[{"check_id": "x", "status": "critical", "headline": "boom"}],
    )
    assert_equal(v2["severity"], "error", "critical → error 映射")


def test_verdict_dirty_git_is_warning_not_error() -> None:
    """脏工作树：warning，不是 error。dirty 是日常状态，不该红字。"""
    v = build_overview_verdict(
        status_json={
            "git": {"dirty": True, "ahead": 0, "behind": 0, "change_count": 5},
            "daemon": {"running": True, "process_count": 2},
        },
        doctor_summary=_doctor_all_pass(),
        health_signals=[],
    )
    assert_equal(v["severity"], "warning", "dirty 是 warning 不是 error")
    git_sub = next(s for s in v["subsystems"] if s["name"] == "Git")
    assert_equal(git_sub["severity"], "warning", "Git 子系统")
    assert_in("5", git_sub["summary"], "Git 摘要含变更数")


def test_timeline_no_data_does_not_pollute_verdict() -> None:
    """**回归 UX-REVIEW D1**：token saver / AI timeline 数据**永远不进 severity**。

    场景：所有真实健康源都 ok，但 timeline_evidence 全 0
    （work_ai=0 / audit_ai=0），原 status.py 会判定 "未解决：token saver
    还没有运行证据" 并把首屏染红。
    本函数签名根本不接 timeline——这条断言通过 = 劫持路径已切断。
    """
    # 注意：函数签名不接收 timeline_evidence，本身就是硬保护
    v = build_overview_verdict(
        status_json=_clean_status(),
        doctor_summary=_doctor_all_pass(),
        health_signals=[],  # 健康也没跑过
    )
    # 真实健康源全干净 → severity 必须能落到 ok（不被任何子问题劫持）
    # 注意：health_signals=[] 时 Health subsystem 是 info（"未运行"），
    # 所以 severity = info，不是 ok。这是合理的——告诉用户健康没跑过，
    # 但绝不应该是 warning/error。
    assert v["severity"] in ("ok", "info"), \
        f"timeline 无数据不应导致 warning/error，实际：{v['severity']}"
    # 强保证：headline 不含 token / saver / AI / audit / 调用 任何一个词
    forbidden = ["token", "saver", "AI", "audit", "调用证据", "未解决"]
    for word in forbidden:
        if word in v["headline"]:
            raise AssertionError(
                f"D1 回归失败：headline 含 token saver 字眼 {word!r}: {v['headline']!r}"
            )


# ----------------------- 跑测试 -----------------------


def main() -> int:
    tests = [
        test_verdict_all_green,
        test_verdict_takes_max_severity,
        test_verdict_dirty_git_is_warning_not_error,
        test_timeline_no_data_does_not_pollute_verdict,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
    if failed:
        print(f"\n{failed} / {len(tests)} 失败")
        return 1
    print(f"\n{len(tests)} 测试全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
