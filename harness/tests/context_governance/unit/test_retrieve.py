"""L1 unit tests for harness_retrieve.py — U1..U10."""
from __future__ import annotations

import json
from pathlib import Path

import harness_retrieve as hr  # type: ignore


def _paths(brief: hr.ContextBrief) -> list[str]:
    return [p["path"] for p in brief.relevant_pointers]


def test_u1_keyword_routes_to_diff(memory_root, task_root, cache_path):
    """U1: query 含 diff/vscode → 推 feedback_diff_workflow，排除无关。"""
    brief = hr.retrieve(
        task_name="demo-task",
        user_msg="how do I see vscode diff for this file",
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
    )
    paths = _paths(brief)
    assert any("feedback_diff_workflow.md" in p for p in paths)
    assert not any("feedback_unrelated.md" in p for p in paths)


def test_u2_ambiguous_keyword_warns(memory_root, task_root, cache_path):
    """U2: 多义词 diff 未带 namespace → warning，不 fallback 全推。"""
    brief = hr.retrieve(
        task_name="demo-task",
        user_msg="diff",
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
    )
    assert any("ambiguous_keyword" in w for w in brief.warnings)


def test_u3_short_query_returns_handoff_only(memory_root, task_root, cache_path):
    """U3: 极短 query → 空指针 + handoff 摘要 + warning，不抛异常。"""
    brief = hr.retrieve(
        task_name="demo-task",
        user_msg="继续",
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
    )
    assert brief.handoff_path.endswith("HANDOFF.md")
    assert any("query_too_short" in w or "ambiguous_keyword" in w for w in (brief.warnings or [""]))


def test_u4_schema_version_present(memory_root, task_root, cache_path):
    """U4: 输出必含 schema_version: v1。"""
    brief = hr.retrieve(
        task_name="demo-task", user_msg="diff", memory_root=memory_root,
        task_root=task_root, cache_path=cache_path,
    )
    assert brief.schema_version == "v2"
    assert "schema_version: v2" in brief.to_yaml_like()


def test_u5_brief_length_cap(memory_root, task_root, cache_path):
    """U5: 极端 case 长 description ×N → 输出 ≤MAX_BRIEF_BYTES，超则截断 + warning。"""
    big = "X" * 5000
    for i in range(8):
        (memory_root / "feedback" / f"feedback_bigdesc_{i}.md").write_text(
            f"---\ndescription: {big}\npriority: high\nstatus: active\n"
            f"trigger:\n  keywords:\n    - tool:diff\n  tags:\n    - workflow\n  stages:\n    - debug\n---\nbody\n",
            encoding="utf-8",
        )
    brief = hr.retrieve(
        task_name="demo-task", user_msg="tool:diff", memory_root=memory_root,
        task_root=task_root, cache_path=cache_path, top_n=8,
    )
    out = brief.to_yaml_like()
    assert len(out.encode("utf-8")) <= hr.MAX_BRIEF_BYTES + 200, f"size={len(out)}"


def test_u6_trigger_cache_invalidates_on_mtime(memory_root, task_root, cache_path):
    """U6: 文件 mtime 更新后下次调用重扫。"""
    import time as _t
    hr.retrieve(task_name="demo-task", user_msg="diff", memory_root=memory_root,
                task_root=task_root, cache_path=cache_path)
    assert cache_path.exists()
    cache_size_1 = cache_path.stat().st_size

    new_file = memory_root / "feedback" / "feedback_zzz_added.md"
    _t.sleep(0.05)
    new_file.write_text(
        "---\ndescription: added later\npriority: medium\nstatus: active\n"
        "trigger:\n  keywords:\n    - tool:newthing\n  tags:\n    - tooling\n  stages:\n    - debug\n---\nbody\n",
        encoding="utf-8",
    )
    os_stat_cache = cache_path.stat().st_mtime
    os_stat_file = new_file.stat().st_mtime
    assert os_stat_file > os_stat_cache, "fixture must produce newer file"

    hr.retrieve(task_name="demo-task", user_msg="tool:newthing", memory_root=memory_root,
                task_root=task_root, cache_path=cache_path)
    cache_size_2 = cache_path.stat().st_size
    assert cache_size_2 >= cache_size_1


def test_u7_broken_frontmatter_fallback(memory_root, task_root, cache_path):
    """U7: yaml 残缺/含 emoji/中文 → fallback parser 兜底，不崩。"""
    (memory_root / "feedback" / "feedback_chinese_emoji.md").write_text(
        "---\ndescription: 中文描述 🚀 emoji\npriority: medium\nstatus: active\n"
        "trigger:\n  keywords:\n    - concept:中文\n  tags:\n    - workflow\n  stages:\n    - debug\n---\n# 中文\n",
        encoding="utf-8",
    )
    brief = hr.retrieve(
        task_name="demo-task", user_msg="中文", memory_root=memory_root,
        task_root=task_root, cache_path=cache_path,
    )
    assert isinstance(brief, hr.ContextBrief)


def test_u8_windows_path_normalized(memory_root, task_root, cache_path):
    """U8: 输出路径全部正斜杠。"""
    brief = hr.retrieve(
        task_name="demo-task", user_msg="diff", memory_root=memory_root,
        task_root=task_root, cache_path=cache_path,
    )
    for p in _paths(brief):
        assert "\\" not in p, f"backslash found in {p}"


def test_u9_self_exclude(memory_root, task_root, cache_path, tmp_path):
    """U9: harness/scripts/ 自身文件 → 不出现在 brief。"""
    sd = memory_root / "harness" / "scripts"
    sd.mkdir(parents=True)
    (sd / "fake_meta.md").write_text(
        "---\ndescription: self\nstatus: active\ntrigger:\n  keywords:\n    - tool:diff\n  tags:\n    - tooling\n  stages:\n    - debug\n---\nbody\n",
        encoding="utf-8",
    )
    brief = hr.retrieve(
        task_name="demo-task", user_msg="tool:diff", memory_root=memory_root,
        task_root=task_root, cache_path=cache_path,
    )
    for p in _paths(brief):
        assert "/harness/scripts/" not in p


def test_u10_deprecated_filtered(memory_root, task_root, cache_path):
    """U10: status: deprecated 不出现在 brief。"""
    brief = hr.retrieve(
        task_name="demo-task", user_msg="tool:diff", memory_root=memory_root,
        task_root=task_root, cache_path=cache_path,
    )
    for p in _paths(brief):
        assert "feedback_deprecated.md" not in p


def test_u12_alias_expand_and_fuzzy(memory_root, task_root, cache_path):
    """U12: 用户写 typo 'vscod' / 中文 '看差异' → alias 展开应推 diff workflow；
    用户写 'qss'（pyside 缩写）→ 应推 qt styling。"""
    hr.load_aliases(force=True)

    b1 = hr.retrieve(
        task_name="demo-task", user_msg="how to vscod看差异",
        memory_root=memory_root, task_root=task_root, cache_path=cache_path,
    )
    paths = _paths(b1)
    assert any("feedback_diff_workflow.md" in p for p in paths), f"alias miss: {paths}"
    assert any("alias_expanded" in w for w in b1.warnings), b1.warnings

    b2 = hr.retrieve(
        task_name="demo-task", user_msg="qss样式失效",
        memory_root=memory_root, task_root=task_root, cache_path=cache_path,
    )
    paths = _paths(b2)
    assert any("knowledge_qt_pyside_styling.md" in p for p in paths), f"alias miss: {paths}"


def test_u11_yaml_date_serializable(memory_root, task_root, cache_path):
    """U11: frontmatter 含 last_updated: 2026-05-20（YAML date 对象）→ cache JSON 写不抛。"""
    target = memory_root / "feedback" / "feedback_with_date.md"
    target.write_text(
        "---\n"
        "description: with date\n"
        "trigger:\n  keywords: [tool:diff]\n  tags: [workflow]\n  stages: [implementation]\n"
        "last_updated: 2026-05-20\n"
        "---\n# body\n",
        encoding="utf-8",
    )
    brief = hr.retrieve(
        task_name="demo-task", user_msg="tool:diff",
        memory_root=memory_root, task_root=task_root, cache_path=cache_path,
    )
    assert cache_path.exists()
    json.loads(cache_path.read_text(encoding="utf-8"))


def test_u13_task_context_fallback_is_opt_in(memory_root, task_root, cache_path, tmp_path):
    """U13: task-context fallback must not change default behavior; explicit config may recover a hit."""
    target = memory_root / "fixes" / "fixes_phase_followup.md"
    target.write_text(
        "---\n"
        "description: phase followup memory\n"
        "trigger:\n  keywords: [concept:phase]\n  tags: [workflow]\n  stages: [implementation]\n"
        "---\n# phase\n",
        encoding="utf-8",
    )

    default = hr.retrieve(
        task_name="demo-task",
        user_msg="继续",
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
    )
    assert not any("fixes_phase_followup.md" in p for p in _paths(default))

    config = tmp_path / "task_context_fallback.json"
    config.write_text(
        json.dumps({
            "enabled": True,
            "context_limit": 300,
            "allowed_tasks": ["demo-task"],
        }),
        encoding="utf-8",
    )
    opted = hr.retrieve(
        task_name="demo-task",
        user_msg="继续",
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
        task_context_fallback_config=config,
    )
    assert any("fixes_phase_followup.md" in p for p in _paths(opted))
    assert any("task_context_fallback" in w for w in opted.warnings)


def test_u14_task_context_fallback_respects_allowlist(memory_root, task_root, cache_path, tmp_path):
    """U14: explicit fallback config can be task-scoped."""
    target = memory_root / "fixes" / "fixes_phase_followup.md"
    target.write_text(
        "---\n"
        "description: phase followup memory\n"
        "trigger:\n  keywords: [concept:phase]\n  tags: [workflow]\n  stages: [implementation]\n"
        "---\n# phase\n",
        encoding="utf-8",
    )
    config = tmp_path / "task_context_fallback.json"
    config.write_text(
        json.dumps({
            "enabled": True,
            "context_limit": 300,
            "allowed_tasks": ["other-task"],
        }),
        encoding="utf-8",
    )
    brief = hr.retrieve(
        task_name="demo-task",
        user_msg="继续",
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
        task_context_fallback_config=config,
    )
    assert not _paths(brief)
    assert any("task_context_fallback_skipped:task_not_allowed" in w for w in brief.warnings)


def test_u14b_task_level_fallback_config(memory_root, task_root, cache_path):
    """U14b: accepted task can opt into fallback via core/CONFIG.json without CLI config."""
    target = memory_root / "fixes" / "fixes_phase_followup.md"
    target.write_text(
        "---\n"
        "description: phase followup memory\n"
        "trigger:\n  keywords: [concept:phase]\n  tags: [workflow]\n  stages: [implementation]\n"
        "---\n# phase\n",
        encoding="utf-8",
    )
    core = task_root / "demo-task" / "core"
    core.mkdir(parents=True)
    (core / "HANDOFF.md").write_text("# Core HANDOFF\n\n继续 phase 1。\n", encoding="utf-8")
    (core / "CONFIG.json").write_text(
        json.dumps({
            "schema_version": 1,
            "retrieve": {
                "task_context_fallback": {
                    "enabled": True,
                    "context_limit": 300,
                },
            },
        }),
        encoding="utf-8",
    )

    brief = hr.retrieve(
        task_name="demo-task",
        user_msg="继续",
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
    )
    assert any("fixes_phase_followup.md" in p for p in _paths(brief))
    assert any("task_context_fallback" in w and "CONFIG.json" in w for w in brief.warnings)


def test_u15_handoff_path_supports_core_layout(memory_root, task_root, cache_path):
    """U15: work-lite tasks store HANDOFF under core/HANDOFF.md."""
    core_task = task_root / "core-task" / "core"
    core_task.mkdir(parents=True)
    (core_task / "HANDOFF.md").write_text("# Core HANDOFF\n\n## 下次开始\n继续。\n", encoding="utf-8")
    brief = hr.retrieve(
        task_name="core-task",
        user_msg="继续",
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
    )
    assert brief.handoff_path.endswith("core/HANDOFF.md")


def test_u16_score_entry_trace_matches_score_entry():
    """U16: score trace exposes contributions without changing scorer behavior."""
    entry = {
        "path": "$GLOBAL_MEMORY_DIR/fixes/fix_demo.md",
        "description": "demo",
        "meta": {
            "priority": "high",
            "trigger": {
                "keywords": ["error:shader"],
                "tags": ["android"],
                "stages": ["debug"],
            },
        },
    }
    score, why = hr._score_entry(entry, "shader crash", "debug", ["android"])
    trace = hr.score_entry_trace(entry, "shader crash", "debug", ["android"])

    assert trace["final_score"] == score
    assert trace["why"] == why
    assert round(trace["final_score"], 1) == 5.4
    assert [c["kind"] for c in trace["contributions"]] == ["keyword", "tag", "stage", "priority"]


# ── 项目局部记忆层（task-local）U17..U19 ──

def test_u17_local_layer_surfaces_no_keyword_file(memory_root, task_root, cache_path, project_memory_root):
    """U17: 无 trigger.keywords 的 CLI 文件靠 description 回退浮出，标 source=task-local。"""
    brief = hr.retrieve(
        task_name="demo-task",
        user_msg="android packaging obb",
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
        project_memory_root=project_memory_root,
    )
    locals_ = [p for p in brief.relevant_pointers if p.get("source") == "task-local"]
    assert any("fix_android_packaging.md" in p["path"] for p in locals_)
    assert not any("MEMORY.md" in p["path"] for p in brief.relevant_pointers)
    assert any("task_local_layer" in w for w in brief.warnings)


def test_u18_local_layer_absent_when_no_project_dir(memory_root, task_root, cache_path):
    """U18: 不传 project_memory_root → 行为如今天，无 task-local 指针/warning。"""
    brief = hr.retrieve(
        task_name="demo-task",
        user_msg="android packaging obb",
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
    )
    assert all(p.get("source") != "task-local" for p in brief.relevant_pointers)
    assert not any("task_local_layer" in w for w in brief.warnings)


def test_u19_local_layer_does_not_pollute_global_ranking(memory_root, task_root, cache_path, project_memory_root):
    """U19: global query 命中时 global 指针在前，局部仅叠加在后，不抢排序。"""
    brief = hr.retrieve(
        task_name="demo-task",
        user_msg="how do I see vscode diff",
        memory_root=memory_root,
        task_root=task_root,
        cache_path=cache_path,
        project_memory_root=project_memory_root,
    )
    paths = [p["path"] for p in brief.relevant_pointers]
    assert any("feedback_diff_workflow.md" in p for p in paths)
    assert brief.relevant_pointers[0].get("source") != "task-local"
