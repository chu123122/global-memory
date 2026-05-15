#!/usr/bin/env python3
"""单元测试 · issue_tracker D1 范围

回归点：
  - test_issue_id_stability：同一 signal 多次重算 ID 必须一致；evidence 含时间戳/计数
    噪音也不影响 ID（这是 V2 验收的命脉）
  - test_extract_dedup_and_count：从 health_checks.jsonl 末尾提取至少 5 个 check 的
    issue（V1）；连续跑 2 次 extract，第 2 次新增数应为 0（V2 去重）
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reporting"))

from issue_tracker import (  # noqa: E402
    Issue,
    IssueNotFoundError,
    IssueStateError,
    SOURCE_HEALTH,
    _strip_volatile,
    archive_issue,
    compute_issue_id,
    extract_from_health,
    reopen_issue,
)


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_true(cond, label: str) -> None:
    if not cond:
        raise AssertionError(label)


# ----------------------- 测试 1：issue_id 稳定性 -----------------------


def test_issue_id_stability() -> None:
    """同一 signal 评估多次必须 ID 不变；时间戳/计数变化不影响 ID。"""
    base_evidence = [
        "[2026-04-28T09:17:14+00:00] sync attempt failed",
        "近 30 次 sync 中 5 次失败",
        "remote: rejected push to master",
    ]
    id1 = compute_issue_id(SOURCE_HEALTH, "sync_failures", base_evidence)

    # 同样 signal，时间戳变（通常每次 detector run 都会变）
    evidence_later = [
        "[2026-04-29T15:22:08+00:00] sync attempt failed",  # 时间戳变了
        "近 30 次 sync 中 5 次失败",                            # 计数没变
        "remote: rejected push to master",
    ]
    id2 = compute_issue_id(SOURCE_HEALTH, "sync_failures", evidence_later)
    assert_equal(id2, id1, "时间戳变化不应影响 issue_id")

    # 同样 signal，计数微变（30→31，5→6）——这种微小数字浮动也不该破 id
    evidence_drift = [
        "[2026-04-30T10:00:00+00:00] sync attempt failed",
        "近 31 次 sync 中 6 次失败",                            # 计数变了
        "remote: rejected push to master",
    ]
    id3 = compute_issue_id(SOURCE_HEALTH, "sync_failures", evidence_drift)
    assert_equal(id3, id1, "计数变化不应影响 issue_id（只要 evidence 主体没变）")

    # 真不同的问题（evidence 主体变了）→ id 必须不同
    evidence_diff = [
        "[2026-04-28T09:17:14+00:00] memory.md 占用 65/80",
        "MEMORY.md 已含 65 条记忆",
        "建议归档 cold knowledge",
    ]
    id_other = compute_issue_id(SOURCE_HEALTH, "memory_usage", evidence_diff)
    assert_true(id_other != id1, "不同 check 的 issue_id 必须不同")

    # _strip_volatile 单点验证
    assert_equal(
        _strip_volatile("[2026-04-28T09:17:14+00:00] foo 7/9"),
        "[<TS>] foo <N/M>",
        "_strip_volatile 时间戳 + N/M",
    )
    assert_equal(
        _strip_volatile("近 30 次 sync 中 5 次失败"),
        "近 <N> 次 sync 中 <N> 次失败",
        "_strip_volatile 纯数字",
    )


# ----------------------- 测试 2：ETL + 去重 -----------------------


def _make_health_record(signals: list[dict]) -> dict:
    return {"ts": "2026-04-28T09:17:14+00:00", "signals": signals}


def _make_signal(check_id: str, status: str = "warning", evidence_n: int = 1) -> dict:
    return {
        "check_id": check_id,
        "status": status,
        "headline": f"{check_id} 出问题了",
        "value": "X",
        "evidence": [f"evidence line {i} for {check_id}" for i in range(evidence_n)],
        "fix_hint": f"修 {check_id}",
        "ts": "2026-04-28T09:17:14+00:00",
    }


def test_extract_dedup_and_count() -> None:
    """从健康检查 jsonl 提取多个 check + 跑 2 次第二次应为 0（V1+V2）。"""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        health_path = td_path / "health_checks.jsonl"
        issues_path = td_path / "issues.jsonl"

        # 造一份 health record 含 5 个不同 check 的非 ok signal + 2 个 ok（应被忽略）
        signals = [
            _make_signal("sync_failures", "critical", evidence_n=3),
            _make_signal("memory_usage", "warning", evidence_n=2),
            _make_signal("knowledge_unread", "critical", evidence_n=4),
            _make_signal("changelog_drift", "warning", evidence_n=2),
            _make_signal("ghost_refs", "warning", evidence_n=3),
            _make_signal("traffic_imbalance", "ok"),  # 应被忽略
            _make_signal("invocation_freq", "ok"),    # 应被忽略
        ]
        record = _make_health_record(signals)
        health_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

        # 第 1 次 extract：应得 5 条新 issue（5 个非 ok signal）
        new1 = extract_from_health(health_path=health_path, issues_path=issues_path)
        assert_true(len(new1) >= 5, f"V1: 应至少提取 5 个不同 check 的 issue，实得 {len(new1)}")
        # 检查 5 个 check_id 都到位
        check_ids_extracted = {i.issue_id.split(".", 2)[1] for i in new1}
        for expected_check in ("sync_failures", "memory_usage", "knowledge_unread"):
            assert_true(
                expected_check in check_ids_extracted,
                f"应包含 {expected_check}，实得 {check_ids_extracted}",
            )
        # ok signal 不应进 issue
        for i in new1:
            assert_true("traffic_imbalance" not in i.issue_id, "ok signal 不应被提取")

        # 文件该有 5 行
        lines_after_1 = issues_path.read_text(encoding="utf-8").splitlines()
        assert_equal(len(lines_after_1), len(new1), "issues.jsonl 行数应等于新增数")

        # 第 2 次 extract：同一 health record，应得 0 条新 issue（V2 去重）
        new2 = extract_from_health(health_path=health_path, issues_path=issues_path)
        assert_equal(len(new2), 0, "V2: 同 issue 已开着，第 2 次 extract 不应新增")

        lines_after_2 = issues_path.read_text(encoding="utf-8").splitlines()
        assert_equal(
            len(lines_after_2), len(lines_after_1), "issues.jsonl 行数不应变（无 append）",
        )

        # 检查 evidence_hash 与 issue_id 后段一致
        sample = json.loads(lines_after_1[0])
        assert_equal(
            sample["evidence_hash"],
            sample["issue_id"].rsplit(".", 1)[-1],
            "evidence_hash 应等于 issue_id 末段",
        )

        # 检查 detected event + actor=auto + severity 映射
        for line in lines_after_1:
            r = json.loads(line)
            assert_equal(r["event"], "detected", f"D1 仅产 detected event：{r}")
            assert_equal(r["actor"], "auto", f"D1 ETL 来源应为 auto：{r}")
            assert_equal(r["source"], SOURCE_HEALTH, f"source 应为 health：{r}")


# ----------------------- 测试 3：自动 fixed（V4） -----------------------


def test_auto_fixed_when_issue_disappears() -> None:
    """detector 重跑后该 issue_id 不再出现 → 自动 append fixed。"""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        health_path = td_path / "health_checks.jsonl"
        issues_path = td_path / "issues.jsonl"

        # 第 1 跑：health 报 2 个非 ok
        rec1 = _make_health_record([
            _make_signal("sync_failures", "warning", evidence_n=2),
            _make_signal("memory_usage", "warning", evidence_n=2),
        ])
        health_path.write_text(json.dumps(rec1, ensure_ascii=False) + "\n", encoding="utf-8")
        new1 = extract_from_health(health_path=health_path, issues_path=issues_path)
        assert_equal(len(new1), 2, "第 1 跑应得 2 detected")

        # 第 2 跑：health 只报 1 个（sync_failures 修好了，memory_usage 还在）
        rec2 = _make_health_record([
            _make_signal("memory_usage", "warning", evidence_n=2),
        ])
        # 覆盖（health_checks.jsonl 是 append-only，但 ETL 只看末尾，
        # 这里直接覆盖等同于"末尾就是新 record"）
        health_path.write_text(
            json.dumps(rec1, ensure_ascii=False) + "\n"
            + json.dumps(rec2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        new2 = extract_from_health(health_path=health_path, issues_path=issues_path)
        # 期望：memory_usage 已开着，跳过；sync_failures 消失 → 自动 fixed
        assert_equal(len(new2), 1, f"第 2 跑应得 1 自动 fixed，实得 {len(new2)}")
        assert_equal(new2[0].event, "fixed", f"event 应为 fixed：{new2[0]}")
        assert_true("sync_failures" in new2[0].issue_id, f"应是 sync_failures：{new2[0].issue_id}")

        # 第 3 跑：health 又报告了 sync_failures（同 evidence → 同 id）→ reopened
        rec3 = _make_health_record([
            _make_signal("sync_failures", "warning", evidence_n=2),
            _make_signal("memory_usage", "warning", evidence_n=2),
        ])
        health_path.write_text(
            json.dumps(rec1, ensure_ascii=False) + "\n"
            + json.dumps(rec2, ensure_ascii=False) + "\n"
            + json.dumps(rec3, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        new3 = extract_from_health(health_path=health_path, issues_path=issues_path)
        # memory_usage 仍开着跳过；sync_failures 之前是 fixed → reopened
        assert_equal(len(new3), 1, f"第 3 跑应得 1 reopened，实得 {len(new3)}")
        assert_equal(new3[0].event, "reopened", f"event 应为 reopened：{new3[0]}")
        assert_true("sync_failures" in new3[0].issue_id, "应是 sync_failures id")


# ----------------------- 测试 4：archive + 沉淀建议（V3+V5） -----------------------


def test_archive_outputs_learning_target() -> None:
    """archive_issue 返回 (issue, suggestion)，suggestion 含 fixes/ 路径。"""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        health_path = td_path / "health_checks.jsonl"
        issues_path = td_path / "issues.jsonl"

        # 造一条 detected
        rec = _make_health_record([_make_signal("sync_failures", "warning", evidence_n=2)])
        health_path.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
        new = extract_from_health(health_path=health_path, issues_path=issues_path)
        assert_equal(len(new), 1, "extract 应产生 1 detected")
        the_id = new[0].issue_id

        # archive 它
        archived, suggestion = archive_issue(
            the_id, note="手动归档测试", issues_path=issues_path,
        )
        assert_equal(archived.event, "archived", "event 应为 archived")
        assert_equal(archived.actor, "user", "actor 应为 user（CLI 触发）")
        assert_equal(archived.note, "手动归档测试", "note 应原样保留")

        # V5 沉淀建议必须含 fixes/ 前缀 + check_id
        assert_true("fixes/" in suggestion, f"建议路径应含 fixes/：{suggestion}")
        assert_true("sync_failures" in suggestion, f"建议路径应含 check_id：{suggestion}")
        assert_true(suggestion.endswith(".md"), f"建议路径应是 .md：{suggestion}")

        # 文件应该有 2 行（detected + archived）
        lines = issues_path.read_text(encoding="utf-8").splitlines()
        assert_equal(len(lines), 2, f"应 append 1 条 archived，总 2 行，实得 {len(lines)}")
        last_record = json.loads(lines[-1])
        assert_equal(last_record["event"], "archived", "末尾应为 archived")
        assert_equal(last_record["issue_id"], the_id, "issue_id 应一致")

        # archive 已 archived 的应抛 IssueStateError
        try:
            archive_issue(the_id, issues_path=issues_path)
            raise AssertionError("应抛 IssueStateError")
        except IssueStateError:
            pass

        # reopen archived 的应成功
        reopened = reopen_issue(the_id, note="手动 reopen", issues_path=issues_path)
        assert_equal(reopened.event, "reopened", "event 应为 reopened")
        assert_equal(reopened.actor, "user", "actor 应为 user")

        # archive 不存在的应抛 IssueNotFoundError
        try:
            archive_issue("health.fake.deadbeef", issues_path=issues_path)
            raise AssertionError("应抛 IssueNotFoundError")
        except IssueNotFoundError:
            pass


# ----------------------- runner -----------------------


def main() -> int:
    tests = [
        test_issue_id_stability,
        test_extract_dedup_and_count,
        test_auto_fixed_when_issue_disappears,
        test_archive_outputs_learning_target,
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
