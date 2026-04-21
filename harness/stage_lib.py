"""
stage_lib.py — work agent 双轨文档体系 阶段感知共享库（v3.1）

供 doc_gate.py / check_doc_status.py / check_doc_sync.py 共用。

核心 API：
    detect_stage(task_dir, registry) -> (stage, diagnostic)
    get_required_docs(task_dir, registry) -> (required_list, diagnostic)
    sanity_check_registry(registry) -> diagnostic | None

阶段定义：
    discussion       — 讨论期，仅要求人类文档
    implementation   — 实现期，要求人类文档 + AI 文档
    archived         — 归档，跳过检查
    unknown          — 完全无人类文档，旧任务降级走 required_docs
    missing-status   — 有人类文档但 Status 缺/错/不一致 → 阻断 + 诊断

设计文档：D:/ClaudeTasks/active/work-agent-doc-redesign/DESIGN.md
"""

import re
from pathlib import Path

HEAD_LINE_LIMIT = 50
VALID_STAGES = ("discussion", "implementation", "archived")


def _read_status(doc_path: Path, status_field: str) -> str | None:
    """读单份文档的 Status 值；找不到返回 None。

    截断策略（v3.1 评审 c）：
    - 仅当 lines[0].strip() == '---' 才进入 yaml frontmatter 模式（找闭合 ---）
    - 否则纯 HEAD_LINE_LIMIT 行截断
    - 不混合两种语义，避免误把正文水平分割线 '---' 当 frontmatter 边界
    """
    try:
        content = doc_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    lines = content.split("\n")
    if lines and lines[0].strip() == "---":
        yaml_end = next(
            (i for i, ln in enumerate(lines[1:HEAD_LINE_LIMIT], start=1) if ln.strip() == "---"),
            None,
        )
        cutoff = yaml_end if yaml_end is not None else HEAD_LINE_LIMIT
    else:
        cutoff = HEAD_LINE_LIMIT
    head = "\n".join(lines[:cutoff])

    pattern = rf"^>?\s*{re.escape(status_field)}:\s*(\w[\w-]*)"
    m = re.search(pattern, head, re.MULTILINE)
    return m.group(1).lower() if m else None


def detect_stage(task_dir: Path, registry: dict) -> tuple[str, str | None]:
    """返回 (stage, diagnostic)。diagnostic 仅在 unknown/missing-status 非空。"""
    patterns = registry.get("human_doc_patterns", [])
    status_field = registry.get("stage_status_field", "Status")

    if not patterns:
        return ("unknown", None)

    human_docs = [task_dir / p for p in patterns if (task_dir / p).exists()]
    if not human_docs:
        return ("unknown", None)

    statuses = {d.name: _read_status(d, status_field) for d in human_docs}

    if all(s is None for s in statuses.values()):
        names = ", ".join(statuses.keys())
        return (
            "missing-status",
            f"检测到 {names} 但 Status 字段缺失/异常，请在文档头部加 `> Status: discussion`",
        )

    if any(s is None for s in statuses.values()):
        missing = [n for n, s in statuses.items() if s is None]
        return (
            "missing-status",
            f"以下文档缺 Status 字段: {', '.join(missing)}",
        )

    unique = set(statuses.values())
    if len(unique) > 1:
        diag = "两份人类文档 Status 不一致: " + ", ".join(
            f"{n}={s}" for n, s in statuses.items()
        )
        return ("unknown", diag)

    val = unique.pop()
    if val not in VALID_STAGES:
        return ("unknown", f"Status 值非法: {val}（合法值: {', '.join(VALID_STAGES)}）")

    return (val, None)


def sanity_check_registry(registry: dict) -> str | None:
    """配置漂移检测（v3.1 评审 b：失败时返回诊断字符串供调用方阻断）。

    检查 human_doc_patterns 与 required_docs_by_stage.discussion 是否一致。
    返回 None 表示通过；返回字符串表示失败诊断。
    """
    patterns = registry.get("human_doc_patterns")
    by_stage = registry.get("required_docs_by_stage", {})
    discussion = by_stage.get("discussion") if isinstance(by_stage, dict) else None

    # 两个字段都未配置 → 视为旧 registry，跳过检查（向后兼容）
    if patterns is None and discussion is None:
        return None

    if patterns is None or discussion is None:
        return (
            "registry 配置不完整：human_doc_patterns 与 required_docs_by_stage.discussion 必须同时存在或同时缺失。"
            f"\n当前 human_doc_patterns={patterns}, required_docs_by_stage.discussion={discussion}"
            "\n请编辑 ~/.claude/projects/project_registry.json 同步两者"
        )

    if set(patterns) != set(discussion):
        return (
            f"registry 配置漂移：human_doc_patterns={sorted(patterns)} ≠ required_docs_by_stage.discussion={sorted(discussion)}"
            "\n两者必须保持一致（discussion 阶段必填 = 人类文档全集）"
            "\n请编辑 ~/.claude/projects/project_registry.json 让两者一致"
        )

    return None


def get_required_docs(task_dir: Path, registry: dict) -> tuple[list, str | None, str]:
    """按阶段返回必填文档清单 + 诊断 + 阶段名。

    返回 (required_list, diagnostic, stage):
      - missing-status / archived 的 required_list 为 []，调用方需要看 stage 决定行为
      - missing-status：调用方应阻断 + 输出 diagnostic
      - archived：调用方应跳过检查
      - unknown / 配置缺失：退回旧 required_docs（向后兼容）
    """
    stage, diag = detect_stage(task_dir, registry)
    by_stage = registry.get("required_docs_by_stage", {})

    if stage == "missing-status":
        return ([], diag, stage)

    if stage == "archived":
        return ([], None, stage)

    if stage == "unknown" or not by_stage:
        return (registry.get("required_docs", ["SPEC.md"]), diag, stage)

    return (by_stage.get(stage, []), None, stage)
