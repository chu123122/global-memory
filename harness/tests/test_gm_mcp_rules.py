"""Tests for gm.rule backend."""
from __future__ import annotations

from pathlib import Path

from harness.config import REPO_DIR
from harness.gm_mcp.rules import load_rules, lookup_rule


EXPECTED = {
    "R18_REVIEW_READONLY": "审查能不能顺手改代码",
    "R17_SAME_ERROR_STOP": "同一个错误反复出现该停吗",
    "R9_RECOVERY_BOUNDARY": "构建失败了能不能改环境重试",
    "MEMORY_WRITE_RULES": "记忆应该存在哪里以及 frontmatter 怎么办",
    "R13_TESTS_VERIFY_INTENT": "怎么防止 AI 写一堆全绿假测试",
    "TOOL_REGISTRY_MANIFEST": "新增 harness 脚本要登记到 registry 和 manifest 吗",
}


def test_rule_registry_covers_required_six_rules():
    rules = {rule.rule_id: rule for rule in load_rules()}
    assert set(EXPECTED).issubset(rules)


def test_rule_sources_and_anchors_are_greppable():
    for rule in load_rules():
        assert rule.sources, rule.rule_id
        for source in rule.sources:
            path = REPO_DIR / source.source_path
            text = path.read_text(encoding="utf-8", errors="replace")
            assert source.anchor_text in text


def test_lookup_hits_each_required_rule():
    for rule_id, query in EXPECTED.items():
        result = lookup_rule(query, top=1)
        assert result["hit"] is True
        assert result["results"][0]["rule_id"] == rule_id
        assert result["results"][0]["verdict"] != "informational"
        assert result["results"][0]["verdict_basis"] == "direct_rule_text"
        first_source = result["results"][0]["sources"][0]
        assert Path(first_source["source_path"]).suffix == ".md"
        assert first_source["anchor_text"] in first_source["rule_text"]


def test_weak_context_does_not_trigger_strong_review_verdict():
    result = lookup_rule("可以修改文件吗", top=1)

    assert result["results"][0]["rule_id"] == "R18_REVIEW_READONLY"
    assert result["results"][0]["verdict"] == "informational"
    assert result["results"][0]["verdict_basis"] == "informational"
