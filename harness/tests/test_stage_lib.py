#!/usr/bin/env python3
"""
test_stage_lib.py — work agent 双轨文档体系 stage_lib 单元测试（v3.1）

覆盖：
- V1 阶段判定准确（discussion / implementation / archived）
- V2/V3 doc_gate 阶段感知由集成测试覆盖（test_doc_gate.py）
- V8 向后兼容（unknown 阶段退回 required_docs）
- V9 配置一致性自检（sanity check 阻断）
- V10 Status 一致性校验（不一致 → unknown + 诊断）
- V11 missing-status 显式诊断
- V12 archived 行为
- 评审 (c) _read_status 严格 yaml 边界（lines[0]=='---' 才走 yaml 模式）

运行：python ~/.claude/scripts/tests/test_stage_lib.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stage_lib import (  # noqa: E402
    _read_status,
    detect_stage,
    get_required_docs,
    sanity_check_registry,
    sanity_check_task_paths,
)


REGISTRY_OK = {
    "human_doc_patterns": ["REQUIREMENTS.md", "DESIGN.md"],
    "stage_status_field": "Status",
    "required_docs_by_stage": {
        "discussion": ["REQUIREMENTS.md", "DESIGN.md"],
        "implementation": ["REQUIREMENTS.md", "DESIGN.md", "SPEC.md", "HANDOFF.md"],
    },
    "required_docs": ["SPEC.md", "HANDOFF.md", "HARNESS_REVIEW.md", "WORKFLOW.md"],
}


def make_doc(task_dir: Path, name: str, status: str | None, extra: str = ""):
    """在 task_dir 下创建一份带（或不带） Status 的文档。"""
    parts = [f"# {name.replace('.md', '')}"]
    if status is not None:
        parts.append(f"> Status: {status}")
    parts.append("")
    parts.append(extra or "正文内容")
    (task_dir / name).write_text("\n".join(parts), encoding="utf-8")


class TestReadStatus(unittest.TestCase):
    """V11 + 评审 (c)：_read_status 行为"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_status_in_quote_block(self):
        make_doc(self.dir, "REQUIREMENTS.md", "discussion")
        self.assertEqual(_read_status(self.dir / "REQUIREMENTS.md", "Status"), "discussion")

    def test_status_missing(self):
        make_doc(self.dir, "REQUIREMENTS.md", None)
        self.assertIsNone(_read_status(self.dir / "REQUIREMENTS.md", "Status"))

    def test_status_value_normalized_lowercase(self):
        make_doc(self.dir, "REQUIREMENTS.md", "Implementation")
        self.assertEqual(_read_status(self.dir / "REQUIREMENTS.md", "Status"), "implementation")

    def test_yaml_frontmatter_strict(self):
        """lines[0]=='---' → 进入 yaml 模式，找闭合 --- 之间提取"""
        path = self.dir / "X.md"
        path.write_text(
            "---\nStatus: archived\nfoo: bar\n---\n# Title\n", encoding="utf-8"
        )
        self.assertEqual(_read_status(path, "Status"), "archived")

    def test_body_horizontal_rule_not_treated_as_yaml(self):
        """评审 (c)：lines[0] 不是 ---，正文里的 --- 不应作 frontmatter 边界

        构造：第一行是标题，后面有正文 ---，Status 在 --- 之后第 4 行 → 应能读到
        旧实现会在第一个 --- 处截断 → 读不到 Status
        """
        path = self.dir / "X.md"
        path.write_text(
            "# Title\n\n正文段一\n---\n\n> Status: discussion\n",
            encoding="utf-8",
        )
        self.assertEqual(_read_status(path, "Status"), "discussion")

    def test_status_beyond_50_lines(self):
        """Status 在第 51 行之后 → 读不到（设计预期）"""
        body = "\n".join(["filler"] * 60)
        path = self.dir / "X.md"
        path.write_text(f"# Title\n{body}\n> Status: discussion\n", encoding="utf-8")
        self.assertIsNone(_read_status(path, "Status"))


class TestDetectStage(unittest.TestCase):
    """V1 / V10 / V11 / V12 阶段判定"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_discussion(self):
        make_doc(self.dir, "REQUIREMENTS.md", "discussion")
        make_doc(self.dir, "DESIGN.md", "discussion")
        stage, diag = detect_stage(self.dir, REGISTRY_OK)
        self.assertEqual(stage, "discussion")
        self.assertIsNone(diag)

    def test_implementation(self):
        make_doc(self.dir, "REQUIREMENTS.md", "implementation")
        make_doc(self.dir, "DESIGN.md", "implementation")
        stage, _ = detect_stage(self.dir, REGISTRY_OK)
        self.assertEqual(stage, "implementation")

    def test_archived(self):
        """V12"""
        make_doc(self.dir, "REQUIREMENTS.md", "archived")
        make_doc(self.dir, "DESIGN.md", "archived")
        stage, _ = detect_stage(self.dir, REGISTRY_OK)
        self.assertEqual(stage, "archived")

    def test_unknown_no_human_docs(self):
        """V8 向后兼容"""
        stage, _ = detect_stage(self.dir, REGISTRY_OK)
        self.assertEqual(stage, "unknown")

    def test_missing_status_all(self):
        """V11 全缺 Status"""
        make_doc(self.dir, "REQUIREMENTS.md", None)
        make_doc(self.dir, "DESIGN.md", None)
        stage, diag = detect_stage(self.dir, REGISTRY_OK)
        self.assertEqual(stage, "missing-status")
        self.assertIn("Status", diag)

    def test_missing_status_partial(self):
        """V11 部分缺 Status"""
        make_doc(self.dir, "REQUIREMENTS.md", "discussion")
        make_doc(self.dir, "DESIGN.md", None)
        stage, diag = detect_stage(self.dir, REGISTRY_OK)
        self.assertEqual(stage, "missing-status")
        self.assertIn("DESIGN.md", diag)

    def test_status_inconsistent(self):
        """V10 两份不一致 → v3.2 升级为 missing-status（硬阻断）"""
        make_doc(self.dir, "REQUIREMENTS.md", "discussion")
        make_doc(self.dir, "DESIGN.md", "implementation")
        stage, diag = detect_stage(self.dir, REGISTRY_OK)
        self.assertEqual(stage, "missing-status")
        self.assertIn("不一致", diag)

    def test_status_invalid_value(self):
        """v3.2 非法值 → missing-status（硬阻断）"""
        make_doc(self.dir, "REQUIREMENTS.md", "wip")
        make_doc(self.dir, "DESIGN.md", "wip")
        stage, diag = detect_stage(self.dir, REGISTRY_OK)
        self.assertEqual(stage, "missing-status")
        self.assertIn("非法", diag)

    def test_only_one_human_doc(self):
        """仅一份人类文档存在 + Status=discussion → discussion"""
        make_doc(self.dir, "REQUIREMENTS.md", "discussion")
        stage, _ = detect_stage(self.dir, REGISTRY_OK)
        self.assertEqual(stage, "discussion")


class TestSanityCheck(unittest.TestCase):
    """V9 配置一致性自检（评审 b：失败应阻断，调用方读返回值决定）"""

    def test_consistent(self):
        self.assertIsNone(sanity_check_registry(REGISTRY_OK))

    def test_drift(self):
        bad = {
            "human_doc_patterns": ["REQUIREMENTS.md", "DESIGN.md"],
            "required_docs_by_stage": {
                "discussion": ["REQUIREMENTS.md"],  # 漂移
            },
        }
        diag = sanity_check_registry(bad)
        self.assertIsNotNone(diag)
        self.assertIn("漂移", diag)

    def test_one_side_missing(self):
        bad = {
            "human_doc_patterns": ["REQUIREMENTS.md"],
            "required_docs_by_stage": {},
        }
        diag = sanity_check_registry(bad)
        self.assertIsNotNone(diag)

    def test_legacy_registry(self):
        """旧 registry（两个字段都没有）→ 通过（向后兼容）"""
        legacy = {"required_docs": ["SPEC.md"]}
        self.assertIsNone(sanity_check_registry(legacy))


class TestGetRequiredDocs(unittest.TestCase):
    """V1-V3 / V8 阶段感知必填清单"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_discussion_returns_human_only(self):
        make_doc(self.dir, "REQUIREMENTS.md", "discussion")
        make_doc(self.dir, "DESIGN.md", "discussion")
        required, diag, stage = get_required_docs(self.dir, REGISTRY_OK)
        self.assertEqual(set(required), {"REQUIREMENTS.md", "DESIGN.md"})
        self.assertEqual(stage, "discussion")
        self.assertIsNone(diag)

    def test_implementation_returns_full_set(self):
        make_doc(self.dir, "REQUIREMENTS.md", "implementation")
        make_doc(self.dir, "DESIGN.md", "implementation")
        required, _, stage = get_required_docs(self.dir, REGISTRY_OK)
        self.assertEqual(
            set(required),
            {"REQUIREMENTS.md", "DESIGN.md", "SPEC.md", "HANDOFF.md"},
        )
        self.assertEqual(stage, "implementation")

    def test_archived_returns_empty(self):
        """V12 archived 返回空 list（调用方应跳过）"""
        make_doc(self.dir, "REQUIREMENTS.md", "archived")
        make_doc(self.dir, "DESIGN.md", "archived")
        required, _, stage = get_required_docs(self.dir, REGISTRY_OK)
        self.assertEqual(required, [])
        self.assertEqual(stage, "archived")

    def test_unknown_falls_back(self):
        """V8 unknown 退回旧 required_docs"""
        required, _, stage = get_required_docs(self.dir, REGISTRY_OK)
        self.assertEqual(stage, "unknown")
        self.assertEqual(
            set(required),
            {"SPEC.md", "HANDOFF.md", "HARNESS_REVIEW.md", "WORKFLOW.md"},
        )

    def test_missing_status_returns_empty_with_diag(self):
        """V11 missing-status 返回空 list + 诊断（调用方应阻断 + 输出诊断）"""
        make_doc(self.dir, "REQUIREMENTS.md", None)
        make_doc(self.dir, "DESIGN.md", None)
        required, diag, stage = get_required_docs(self.dir, REGISTRY_OK)
        self.assertEqual(required, [])
        self.assertEqual(stage, "missing-status")
        self.assertIsNotNone(diag)


class TestSanityCheckTaskPaths(unittest.TestCase):
    """v3.2 task_paths 一致性自检"""

    def test_no_task_paths_returns_none(self):
        """缺 task_paths → 视为旧 registry，跳过（向后兼容）"""
        self.assertIsNone(sanity_check_task_paths({"active_tasks": ["a", "b"]}))

    def test_consistent(self):
        reg = {"active_tasks": ["a", "b"], "task_paths": {"a": ["x"], "b": []}}
        self.assertIsNone(sanity_check_task_paths(reg))

    def test_active_task_missing_in_task_paths(self):
        """active_tasks 有 b 但 task_paths 没有 → 报错"""
        reg = {"active_tasks": ["a", "b"], "task_paths": {"a": ["x"]}}
        diag = sanity_check_task_paths(reg)
        self.assertIsNotNone(diag)
        self.assertIn("'b'", diag)

    def test_orphan_in_task_paths(self):
        """task_paths 有 b 但 active_tasks 没有 → 死配置报错"""
        reg = {"active_tasks": ["a"], "task_paths": {"a": [], "b": ["x"]}}
        diag = sanity_check_task_paths(reg)
        self.assertIsNotNone(diag)
        self.assertIn("'b'", diag)

    def test_wrong_top_type(self):
        reg = {"active_tasks": ["a"], "task_paths": "not-a-dict"}
        diag = sanity_check_task_paths(reg)
        self.assertIsNotNone(diag)
        self.assertIn("dict", diag)

    def test_wrong_value_type(self):
        reg = {"active_tasks": ["a"], "task_paths": {"a": "string-not-list"}}
        diag = sanity_check_task_paths(reg)
        self.assertIsNotNone(diag)
        self.assertIn("list", diag)

    def test_non_string_path_fragment(self):
        reg = {"active_tasks": ["a"], "task_paths": {"a": ["ok", 123]}}
        diag = sanity_check_task_paths(reg)
        self.assertIsNotNone(diag)
        self.assertIn("字符串", diag)


if __name__ == "__main__":
    unittest.main(verbosity=2)
