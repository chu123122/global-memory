#!/usr/bin/env python3
"""
verify_doc_drift.py - Phase 2-B: 文档与实现漂移扫描

依赖:RULE_ENFORCEMENT_MATRIX.md(Phase 1-B 产物,真值源)

核心规则(8 条):
  D1: 矩阵 enforcer 字段引用的脚本/hook 文件存在
  D2: smoke_test_id 字段可解析(TBD-Phase3 / SMK-NNN / manual)
  D3: hooks 近 7 天有实际触发证据(audit jsonl)
  D4: registry 关键字段被脚本引用(human_doc_patterns / required_docs_by_stage / tasks_root)
  D5: 文档断言与 decision 一致(work skill 的 subagent vs work-mode 决策)
  D6 (G2): Phase 设计文档前 N 行包含"§1 引用区"字串
  D7 (G3): decisions/ 下被引用的 ADR 真实存在
  D8 (G3): ADR 的 Supersedes 链完整(被 supersede 的 ADR 顶部有"已废弃"标)

输出:
  --json 机器可读 / 默认人类可读
  退出码:0 = 全 PASS;1 = 有 WARN;2 = 有 FAIL
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import MEMORY_DIR, CLAUDE_DIR, LOG_DIR  # noqa: E402

RULE_MATRIX = MEMORY_DIR / "RULE_ENFORCEMENT_MATRIX.md"
REGISTRY = CLAUDE_DIR / "projects" / "project_registry.json"
HARNESS_DIR = MEMORY_DIR / "harness"
TASK_PROJECT_DIRS = [MEMORY_DIR / "projects"]
ADR_GLOB_PATTERN = "decisions/ADR-*.md"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_matrix_rows() -> list[dict]:
    """从 RULE_ENFORCEMENT_MATRIX.md 抽取表格行,返回 [{rule_id, ..., enforcer, smoke_test_id, ...}]"""
    if not RULE_MATRIX.exists():
        return []
    text = RULE_MATRIX.read_text(encoding="utf-8")
    rows = []
    # 匹配 "| **RULE-NNN** | desc | strength | enforcer | failure | smoke_test_id | source |" 行
    pattern = re.compile(
        r"^\|\s*\*\*?(RULE-\d+)\*\*?\s*\|\s*(.+?)\s*\|\s*(\w+(?:\(.+?\))?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*([\w-]+)\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE,
    )
    for m in pattern.finditer(text):
        rows.append({
            "rule_id": m.group(1),
            "description": m.group(2),
            "strength": m.group(3).split("(")[0],
            "enforcer": m.group(4),
            "failure_behavior": m.group(5),
            "smoke_test_id": m.group(6),
            "source": m.group(7),
        })
    return rows


def check_d1_enforcer_exists(rows: list[dict]) -> dict:
    """D1: 每条 rule 的 enforcer 引用的脚本/hook 文件存在"""
    findings = []
    for r in rows:
        enforcer = r["enforcer"].strip("`")
        if enforcer in ("AI/human", "AI", "human"):
            continue  # S3 自觉规则跳过
        # 抽出第一个看起来像路径的部分
        path_match = re.search(r"`?([\w/.-]+\.\w+)`?", enforcer)
        if not path_match:
            findings.append({"rule": r["rule_id"], "error": f"无法抽出路径: {enforcer}"})
            continue
        path = path_match.group(1)
        # 相对路径基于 MEMORY_DIR
        full_path = MEMORY_DIR / path if not Path(path).is_absolute() else Path(path)
        if not full_path.exists():
            findings.append({"rule": r["rule_id"], "error": f"enforcer 文件不存在: {path}"})
    level = "FAIL" if findings else "PASS"
    return {"check": "D1", "name": "enforcer 文件存在", "level": level, "findings": findings}


def check_d2_smoke_test_id(rows: list[dict]) -> dict:
    """D2: smoke_test_id 必须是 TBD-Phase3 / SMK-NNN / manual 之一"""
    findings = []
    valid_pattern = re.compile(r"^(TBD-Phase\d+|SMK-\d+|manual)$")
    for r in rows:
        if not valid_pattern.match(r["smoke_test_id"]):
            findings.append({"rule": r["rule_id"], "error": f"smoke_test_id 格式非法: {r['smoke_test_id']}"})
    level = "FAIL" if findings else "PASS"
    return {"check": "D2", "name": "smoke_test_id 格式", "level": level, "findings": findings}


def check_d3_hooks_recent_activity(rows: list[dict]) -> dict:
    """D3: 每个 S1 hook 近 7 天 audit jsonl 有触发证据"""
    findings = []
    cutoff = datetime.now() - timedelta(days=7)
    audit_paths = [LOG_DIR / "tool_audit.jsonl", LOG_DIR / "subagent_audit.jsonl"]

    # 收集近 7 天的 hook 触发 set
    recent_text = ""
    for ap in audit_paths:
        if not ap.exists():
            continue
        try:
            for line in ap.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]:
                try:
                    obj = json.loads(line)
                    ts_str = obj.get("timestamp") or obj.get("ts", "")
                    if ts_str and datetime.fromisoformat(ts_str.replace("Z", "").split("+")[0]) >= cutoff:
                        recent_text += line + "\n"
                except Exception:
                    continue
        except Exception:
            continue

    for r in rows:
        if r["strength"] != "S1":
            continue
        # 从 enforcer 抽 hook 名(取 basename 去 .py)
        path_match = re.search(r"`?([\w/.-]+\.py)`?", r["enforcer"])
        if not path_match:
            continue
        hook_name = Path(path_match.group(1)).stem
        if hook_name not in recent_text:
            findings.append({
                "rule": r["rule_id"],
                "warning": f"S1 hook '{hook_name}' 近 7 天无 audit 触发证据(可能未被使用或未记录)",
            })
    level = "WARN" if findings else "PASS"
    return {"check": "D3", "name": "hooks 近 7 天触发证据", "level": level, "findings": findings}


def check_d4_registry_fields_used(rows: list[dict]) -> dict:
    """D4: registry 关键字段被脚本引用"""
    findings = []
    key_fields = ["human_doc_patterns", "required_docs_by_stage", "tasks_root", "active_tasks"]
    grep_targets = list(HARNESS_DIR.rglob("*.py"))
    grep_text = ""
    for tp in grep_targets:
        try:
            grep_text += tp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
    for field in key_fields:
        if field not in grep_text:
            findings.append({"field": field, "warning": f"registry 字段 '{field}' 未在 harness/*.py 中被引用"})
    level = "WARN" if findings else "PASS"
    return {"check": "D4", "name": "registry 字段被脚本引用", "level": level, "findings": findings}


def check_d5_doc_decision_consistency() -> dict:
    """D5: work skill 的 subagent 描述应与 work-mode 决策一致(V9 漂移检测)"""
    findings = []
    operations_md = Path("D:/skills-repo/_bootstrap/docs/OPERATIONS.md")
    if operations_md.exists():
        text = operations_md.read_text(encoding="utf-8", errors="replace")
        # 简单启发式:如果 OPERATIONS.md 仍把 learning/work 放在 "Subagents" 章节
        if re.search(r"Subagents.*?(learning|work)\s*Agent", text, re.DOTALL | re.IGNORECASE):
            findings.append({
                "doc": "OPERATIONS.md",
                "warning": "learning/work 仍在 Subagents 语义下,与 decision_work_mode_workflow 决策不一致(V9 待 Phase 5 收敛)",
            })
    level = "WARN" if findings else "PASS"
    return {"check": "D5", "name": "文档断言与决策一致", "level": level, "findings": findings}


def check_d6_phase_design_reference_block() -> dict:
    """D6 (G2): Phase 详细设计前几行有"§1 引用区"标识"""
    findings = []
    for proj_dir in TASK_PROJECT_DIRS:
        if not proj_dir.exists():
            continue
        for design in proj_dir.glob("*/设计文档.md"):
            head = "\n".join(design.read_text(encoding="utf-8", errors="replace").splitlines()[:80])
            # 找 ## 2/3 章节是否有"§1 引用区"
            sections = re.findall(r"^##\s+\d+\.\s.*", head, re.MULTILINE)
            if not sections:
                continue
            # 如果有 §1 之外的章节,但没有"§1 引用区"字串 → 漂移
            has_phase_section = any("Phase" in s or "详细设计" in s for s in sections)
            text = design.read_text(encoding="utf-8", errors="replace")
            if has_phase_section and "§1 引用区" not in text:
                findings.append({
                    "doc": str(design.relative_to(MEMORY_DIR)),
                    "warning": "存在 Phase 详细设计章节但无 '§1 引用区' 字串(违反 G2)",
                })
    level = "WARN" if findings else "PASS"
    return {"check": "D6", "name": "G2 Phase 设计有 §1 引用区", "level": level, "findings": findings}


def check_d7_adr_references_exist() -> dict:
    """D7 (G3): decisions/ 中被矩阵或文档引用的 ADR 真实存在"""
    findings = []
    # 从 RULE_MATRIX + DESIGN 收集 ADR 引用
    refs = set()
    for f in [RULE_MATRIX] + list((MEMORY_DIR / "projects").rglob("设计文档.md")):
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        refs.update(re.findall(r"ADR-\d{3}", text))
    # 检查每个引用的 ADR 文件是否存在
    for proj_dir in TASK_PROJECT_DIRS:
        if not proj_dir.exists():
            continue
        for task_dir in proj_dir.iterdir():
            if not task_dir.is_dir():
                continue
            adrs_present = set()
            for adr in task_dir.glob(ADR_GLOB_PATTERN):
                m = re.match(r"(ADR-\d{3})", adr.name)
                if m:
                    adrs_present.add(m.group(1))
            # 在该任务目录检查它的 设计文档.md 引用的 ADR 是否在本任务 decisions/ 内
            design = task_dir / "设计文档.md"
            if not design.exists():
                continue
            design_refs = set(re.findall(r"ADR-\d{3}", design.read_text(encoding="utf-8", errors="replace")))
            missing = design_refs - adrs_present
            if missing:
                findings.append({
                    "task": task_dir.name,
                    "missing_adrs": sorted(missing),
                    "warning": f"设计文档.md 引用了 {sorted(missing)} 但 decisions/ 下不存在对应文件",
                })
    level = "FAIL" if findings else "PASS"
    return {"check": "D7", "name": "G3 ADR 引用真实存在", "level": level, "findings": findings}


def check_d8_adr_supersedes_chain() -> dict:
    """D8 (G3): ADR 标 'Supersedes ADR-NNN' 时被 supersede 的 ADR 顶部要有 '已废弃'/'Superseded by' 标"""
    findings = []
    for proj_dir in TASK_PROJECT_DIRS:
        if not proj_dir.exists():
            continue
        for adr in proj_dir.rglob("ADR-*.md"):
            text = adr.read_text(encoding="utf-8", errors="replace")
            # 找 Supersedes ADR-NNN
            for m in re.finditer(r"Supersedes\s+(ADR-\d{3})", text):
                target = m.group(1)
                target_path = adr.parent / f"{target}-*.md"
                target_files = list(adr.parent.glob(f"{target}-*.md"))
                if not target_files:
                    findings.append({"adr": adr.name, "warning": f"Supersedes {target} 但目标 ADR 文件不存在"})
                    continue
                target_text = target_files[0].read_text(encoding="utf-8", errors="replace")
                # 顶部 30 行是否含"已废弃"/"Superseded by"
                head = "\n".join(target_text.splitlines()[:30])
                if "已废弃" not in head and "Superseded by" not in head:
                    findings.append({
                        "adr": target_files[0].name,
                        "warning": f"被 {adr.name} supersede 但顶部无 '已废弃' / 'Superseded by' 标",
                    })
    level = "WARN" if findings else "PASS"
    return {"check": "D8", "name": "G3 ADR Supersedes 链完整", "level": level, "findings": findings}


def main() -> int:
    p = argparse.ArgumentParser(description="verify_doc_drift — Phase 2-B 漂移扫描")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    rows = parse_matrix_rows()

    checks = [
        check_d1_enforcer_exists(rows),
        check_d2_smoke_test_id(rows),
        check_d3_hooks_recent_activity(rows),
        check_d4_registry_fields_used(rows),
        check_d5_doc_decision_consistency(),
        check_d6_phase_design_reference_block(),
        check_d7_adr_references_exist(),
        check_d8_adr_supersedes_chain(),
    ]

    summary = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for c in checks:
        summary[c["level"]] += 1

    report = {
        "timestamp": now_iso(),
        "matrix_rows": len(rows),
        "checks": checks,
        "summary": summary,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[verify_doc_drift] matrix rows = {len(rows)}\n")
        for c in checks:
            icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[c["level"]]
            print(f"{icon} [{c['check']}] {c['name']}: {c['level']}")
            for f in c["findings"]:
                msg = f.get("error") or f.get("warning") or json.dumps(f, ensure_ascii=False)
                print(f"    - {msg}")
        print(f"\n  结果:{summary['PASS']} PASS / {summary['WARN']} WARN / {summary['FAIL']} FAIL")

    return 2 if summary["FAIL"] else (1 if summary["WARN"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
