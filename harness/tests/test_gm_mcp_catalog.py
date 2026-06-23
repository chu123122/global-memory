"""Golden tests for gm_mcp structured catalog navigation."""
from __future__ import annotations

from harness.gm_mcp import catalog


def test_locate_work_continue_returns_minimal_reads():
    result = catalog.locate("work 继续任务要读什么")

    assert result["tool"] == "gm.locate"
    assert result["hit"] is True
    assert result["count"] <= 3
    paths = [item["path"] for item in result["min_reads"]]
    assert "skills/work/SKILL.md" in paths
    assert "docs/task-lifecycle.md" in paths
    assert result["fallback_used"] is False
    assert result["authority"] == "catalog"


def test_locate_new_harness_script_registration_points_to_registry_and_manifest():
    result = catalog.locate("新增 harness 脚本要登记哪里")

    assert result["hit"] is True
    paths = [item["path"] for item in result["min_reads"]]
    assert "docs/scripts-registry.md" in paths
    assert "harness/capability_manifest.json" in paths
    assert result["count"] <= 3


def test_inspect_skill_and_capability():
    skill = catalog.inspect_object("skill", id_="work")
    assert skill["hit"] is True
    assert skill["results"][0]["path"] == "skills/work/SKILL.md"

    cap = catalog.inspect_object("capability", id_="pull_memory_tools")
    assert cap["hit"] is True
    assert cap["results"][0]["path"] == "harness/capability_manifest.json"


def test_map_returns_core_modules():
    result = catalog.map_modules()

    ids = {item["id"] for item in result["modules"]}
    assert {"rules", "skills", "harness", "docs"}.issubset(ids)
    assert result["fallback_used"] is False
