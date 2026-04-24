#!/usr/bin/env python3
"""
verify_prompt_system.py — Prompt 系统一致性检查

检查 CLAUDE.md + learning-agent.md + work-agent.md 之间的：
1. 重复定义检测（同一规则在多处定义）
2. 过时引用检测（引用已归档/不存在的 Skill/文件）
3. 优先级违规检测（Agent 扩展了铁律中未标注例外的规则）
4. 格式一致性（MEMORY_WRITTEN 格式、compact 轮数等）
5. 数值同步检测（轮数、行数等具体数值在多处是否一致）

用法：
  python verify_prompt_system.py                  # 检查并报告
  python verify_prompt_system.py --report         # 详细报告
  python verify_prompt_system.py --fix            # 自动修复可修复的问题
  python verify_prompt_system.py --pre-commit     # 作为 git hook 使用
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from datetime import datetime

# ─── Windows 编码修复 ───
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── 路径配置 ───
HARNESS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR))
from _lib import AGENTS_DIR, MEMORY_DIR, REPO_DIR, SKILLS_DIR, TEMPLATES_DIR  # noqa: E402

CLAUDE_MD = AGENTS_DIR / "CLAUDE.md"
LEARNING_AGENT = AGENTS_DIR / "learning-agent.md"
WORK_AGENT = AGENTS_DIR / "work-agent.md"
ARCHIVED_DIR = SKILLS_DIR / "_archived"
REFERENCES_DIR = MEMORY_DIR / "knowledge" / "references"

# ─── 结果收集 ───
results = []

def record(check_id, level, message, fix_hint=None):
    """记录检查结果"""
    results.append({
        "id": check_id,
        "level": level,  # ERROR / WARNING / PASS
        "message": message,
        "fix_hint": fix_hint
    })

def read_file_safe(path):
    """安全读取文件"""
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return None

def extract_lines(content):
    """按行拆分"""
    return content.split("\n") if content else []

# ─── 检查 1：重复定义检测 ───
def check_duplicate_definitions():
    """检查同一规则是否在多处定义（应该只在 CLAUDE.md 定义一次）"""
    claude = read_file_safe(CLAUDE_MD) or ""
    learning = read_file_safe(LEARNING_AGENT) or ""
    work = read_file_safe(WORK_AGENT) or ""

    # 检查 compact 轮数
    compact_pattern = r"(\d+)\s*轮.*(?:compact|提醒)"
    claude_nums = set(re.findall(compact_pattern, claude))
    learning_nums = set(re.findall(compact_pattern, learning))
    work_nums = set(re.findall(compact_pattern, work))

    if learning_nums and claude_nums:
        if learning_nums == claude_nums:
            record("DUP-01", "WARNING",
                   f"compact 轮数在 CLAUDE.md 和 learning-agent.md 中重复定义（{claude_nums}）",
                   "learning-agent.md 应改为'遵循 CLAUDE.md 的上下文管理规则'")
        elif learning_nums != claude_nums:
            record("DUP-01", "ERROR",
                   f"compact 轮数不一致！CLAUDE.md={claude_nums}, learning-agent.md={learning_nums}",
                   "统一为 CLAUDE.md 中的数值")

    if work_nums and claude_nums:
        if work_nums == claude_nums:
            record("DUP-02", "WARNING",
                   f"compact 轮数在 CLAUDE.md 和 work-agent.md 中重复定义（{claude_nums}）",
                   "work-agent.md 应改为'遵循 CLAUDE.md 的上下文管理规则'")
        elif work_nums != claude_nums:
            record("DUP-02", "ERROR",
                   f"compact 轮数不一致！CLAUDE.md={claude_nums}, work-agent.md={work_nums}",
                   "统一为 CLAUDE.md 中的数值")

    if not claude_nums and not learning_nums and not work_nums:
        record("DUP-01", "PASS", "无 compact 轮数重复")
        record("DUP-02", "PASS", "无 compact 轮数重复")

    # 检查审查例外清单是否重述
    audit_exceptions_claude = re.findall(r"(?:可直接修|直接修复).*?[：:](.*?)(?:\n|$)", claude)
    audit_exceptions_work = re.findall(r"(?:可直接修|直接修复).*?[：:](.*?)(?:\n|$)", work)

    if audit_exceptions_work:
        # work-agent 重述了审查例外清单
        if any("CLAUDE.md" not in ex for ex in audit_exceptions_work):
            record("DUP-03", "WARNING",
                   "work-agent.md 重述了审查例外清单，应改为引用 CLAUDE.md",
                   "改为'直接修复的例外见 CLAUDE.md 铁律'")
        else:
            record("DUP-03", "PASS", "work-agent 正确引用了 CLAUDE.md 的审查例外")
    else:
        record("DUP-03", "PASS", "work-agent 未重述审查例外清单")

    # 检查去重行数是否一致
    dedup_pattern = r"最近\s*(\d+)\s*行"
    claude_dedup = set(re.findall(dedup_pattern, claude))
    learning_dedup = set(re.findall(dedup_pattern, learning))
    work_dedup = set(re.findall(dedup_pattern, work))

    all_dedup = claude_dedup | learning_dedup | work_dedup
    if len(all_dedup) > 1:
        record("DUP-04", "ERROR",
               f"去重行数不一致：CLAUDE.md={claude_dedup}, learning={learning_dedup}, work={work_dedup}",
               "统一为一个数值")
    elif len(all_dedup) == 1:
        dup_count = sum(1 for s in [claude_dedup, learning_dedup, work_dedup] if s)
        if dup_count > 1:
            record("DUP-04", "WARNING",
                   f"去重行数（{all_dedup.pop()}行）在多处重复定义",
                   "Agent 文件改为引用 CLAUDE.md 的去重规则")
        else:
            record("DUP-04", "PASS", "去重行数只在一处定义")
    else:
        record("DUP-04", "PASS", "无去重行数定义")

# ─── 检查 2：过时引用检测 ───
def check_stale_references():
    """检查是否引用了已归档/不存在的 Skill 或文件"""
    learning = read_file_safe(LEARNING_AGENT) or ""
    work = read_file_safe(WORK_AGENT) or ""
    claude = read_file_safe(CLAUDE_MD) or ""

    # 已归档的 Skill 名称
    archived_skills = set()
    if ARCHIVED_DIR.exists():
        for d in ARCHIVED_DIR.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                archived_skills.add(d.name)

    # 活跃的 Skill 名称
    active_skills = set()
    for d in SKILLS_DIR.iterdir():
        if d.is_dir() and not d.name.startswith(("_", ".")) and (d / "v1" / "SKILL.md").exists():
            active_skills.add(d.name)

    # 在 Agent 文件中搜索 Skill 引用
    all_agent_content = learning + "\n" + work
    
    # 搜索 "使用 XXX Skill" 或 "XXX (Skill)" 模式
    skill_refs = re.findall(r"(?:使用|触发|调用)\s+([\w-]+)\s+Skill", all_agent_content)
    skill_refs += re.findall(r"([\w-]+)\s+\(Skill\)", all_agent_content)
    
    stale_found = False
    for ref in skill_refs:
        ref_lower = ref.lower()
        if ref_lower in [s.lower() for s in archived_skills]:
            record("REF-01", "ERROR",
                   f"Agent 文件引用了已归档的 Skill: {ref}",
                   f"将引用更新为对应的 Reference 文件或 Template")
            stale_found = True
        elif ref_lower not in [s.lower() for s in active_skills]:
            record("REF-01", "WARNING",
                   f"Agent 文件引用了未找到的 Skill: {ref}",
                   f"确认 {ref} 是否存在于 global-memory/skills 中")
            stale_found = True

    if not stale_found:
        record("REF-01", "PASS", f"所有 Skill 引用有效（活跃: {len(active_skills)}, 归档: {len(archived_skills)}）")

    # 检查文件路径引用
    path_refs = re.findall(r"(?:参考|见|读取|检索)\s+([~\w/._-]+\.(?:md|py|json))", all_agent_content + "\n" + claude)
    
    missing_refs = []
    for ref_path in path_refs:
        # 展开 ~ 和相对路径
        expanded = ref_path.replace("~/.claude/", str(Path.home() / ".claude") + "/")
        expanded = expanded.replace("global-memory/", str(MEMORY_DIR) + "/")
        
        # 检查几个可能的基础路径
        candidates = [
            Path(expanded),
            MEMORY_DIR / ref_path.replace("global-memory/", ""),
            REPO_DIR / ref_path,
            SKILLS_DIR / ref_path,
        ]
        
        # 对于 knowledge/ 下的文件名引用
        if "/" not in ref_path:
            candidates.append(MEMORY_DIR / "knowledge" / ref_path)
            candidates.append(MEMORY_DIR / "knowledge" / "docs" / ref_path)
            candidates.append(MEMORY_DIR / "interview" / ref_path)
            candidates.append(MEMORY_DIR / "feedback" / ref_path)
            candidates.append(MEMORY_DIR / "fixes" / ref_path)
            candidates.append(MEMORY_DIR / "decisions" / ref_path)
            candidates.append(TEMPLATES_DIR / ref_path)
        
        found = any(p.exists() for p in candidates)
        if not found and not ref_path.startswith("knowledge/references/"):
            # 跳过明显是示例路径的引用
            if "xxx" not in ref_path and "example" not in ref_path.lower():
                missing_refs.append(ref_path)

    if missing_refs:
        for ref in missing_refs[:5]:  # 最多报 5 个
            record("REF-02", "WARNING",
                   f"引用的文件可能不存在: {ref}",
                   "确认文件路径是否正确")
    else:
        record("REF-02", "PASS", f"检查了 {len(path_refs)} 个文件引用，均有效")

# ─── 检查 3：优先级违规检测 ───
def check_priority_violations():
    """检查 Agent 是否扩展了铁律中未标注例外的规则"""
    claude = read_file_safe(CLAUDE_MD) or ""
    learning = read_file_safe(LEARNING_AGENT) or ""
    work = read_file_safe(WORK_AGENT) or ""

    # 检查写入条件是否标注了"Agent 可扩展"
    if "Agent 可" in claude and ("扩展" in claude or "覆盖" in claude):
        record("PRI-01", "PASS", "CLAUDE.md 写入条件标注了 Agent 可扩展")
    else:
        # 检查 Agent 是否实际扩展了写入条件
        claude_write_conditions = re.findall(r"写入条件.*?(?=\n##|\n-\s*写入方式|\Z)", claude, re.DOTALL)
        learning_write_conditions = re.findall(r"写入条件.*?(?=\n##|\n###\s*读取|\Z)", learning, re.DOTALL)
        work_write_conditions = re.findall(r"写入条件.*?(?=\n##|\n###\s*不要|\Z)", work, re.DOTALL)

        if learning_write_conditions or work_write_conditions:
            record("PRI-01", "WARNING",
                   "Agent 文件扩展了写入条件，但 CLAUDE.md 未标注'Agent 可扩展'",
                   "在 CLAUDE.md 写入条件处加注'Agent 可在此基础上扩展'")
        else:
            record("PRI-01", "PASS", "Agent 未扩展 CLAUDE.md 的写入条件")

    # 检查指令优先级定义是否存在
    if "指令优先级" in claude or "优先级" in claude:
        record("PRI-02", "PASS", "CLAUDE.md 定义了指令优先级")
    else:
        record("PRI-02", "WARNING",
               "CLAUDE.md 未定义指令优先级",
               "建议增加优先级定义：铁律 > Agent > WORKFLOW > 用户指令")

# ─── 检查 4：格式一致性 ───
def check_format_consistency():
    """检查 MEMORY_WRITTEN 格式、Skill 对照表格式等是否一致"""
    learning = read_file_safe(LEARNING_AGENT) or ""
    work = read_file_safe(WORK_AGENT) or ""

    # 检查 MEMORY_WRITTEN 格式
    learning_mem_format = re.findall(r"\[MEMORY_WRITTEN\].*?\[/MEMORY_WRITTEN\]", learning, re.DOTALL)
    work_mem_format = re.findall(r"\[MEMORY_WRITTEN\].*?\[/MEMORY_WRITTEN\]", work, re.DOTALL)

    if learning_mem_format and work_mem_format:
        # 提取字段名
        learning_fields = set(re.findall(r"^-\s+(.*?)[:：]", learning_mem_format[0], re.MULTILINE))
        work_fields = set(re.findall(r"^-\s+(.*?)[:：]", work_mem_format[0], re.MULTILINE))

        if learning_fields == work_fields:
            record("FMT-01", "PASS", f"MEMORY_WRITTEN 格式一致（字段: {learning_fields}）")
        else:
            only_learning = learning_fields - work_fields
            only_work = work_fields - learning_fields
            record("FMT-01", "ERROR",
                   f"MEMORY_WRITTEN 格式不一致！learning 独有: {only_learning}, work 独有: {only_work}",
                   "统一两个 Agent 的 MEMORY_WRITTEN 字段")
    elif learning_mem_format or work_mem_format:
        missing = "learning-agent" if not learning_mem_format else "work-agent"
        record("FMT-01", "ERROR",
               f"{missing}.md 缺少 MEMORY_WRITTEN 格式定义",
               f"补充 {missing}.md 的 MEMORY_WRITTEN 格式")
    else:
        record("FMT-01", "WARNING",
               "两个 Agent 都没有 MEMORY_WRITTEN 格式定义",
               "建议增加统一的 MEMORY_WRITTEN 格式")

    # 检查 Skill 对照表格式一致性
    learning_table = re.findall(r"\|\s*场景\s*\|.*?\n((?:\|.*\n)*)", learning)
    work_table = re.findall(r"\|\s*场景\s*\|.*?\n((?:\|.*\n)*)", work)

    if learning_table and work_table:
        # 检查表头列数
        learning_cols = len(re.findall(r"\|", learning_table[0].split("\n")[0])) - 1
        work_cols = len(re.findall(r"\|", work_table[0].split("\n")[0])) - 1

        if learning_cols == work_cols:
            record("FMT-02", "PASS", f"Skill 对照表列数一致（{learning_cols} 列）")
        else:
            record("FMT-02", "WARNING",
                   f"Skill 对照表列数不一致：learning={learning_cols}, work={work_cols}",
                   "统一对照表格式")
    else:
        record("FMT-02", "PASS", "Skill 对照表格式检查跳过（未找到完整表格）")

# ─── 检查 5：内容完整性 ───
def check_content_completeness():
    """检查必要的区块是否存在"""
    claude = read_file_safe(CLAUDE_MD) or ""
    learning = read_file_safe(LEARNING_AGENT) or ""
    work = read_file_safe(WORK_AGENT) or ""

    # CLAUDE.md 必须有的区块
    required_claude = {
        "铁律": "铁律",
        "启动协议": "启动协议|新对话",
        "记忆": "记忆",
        "金字塔": "金字塔|三层",
        "Agent 判定": "Agent.*判定|判定.*Agent",
    }

    for name, pattern in required_claude.items():
        if re.search(pattern, claude):
            record(f"CMP-C-{name[:3].upper()}", "PASS", f"CLAUDE.md 包含 [{name}] 区块")
        else:
            record(f"CMP-C-{name[:3].upper()}", "ERROR",
                   f"CLAUDE.md 缺少 [{name}] 区块",
                   f"补充 {name} 定义")

    # Agent 文件必须有的区块
    required_agent = {
        "角色定位": "角色定位",
        "核心行为": "核心行为",
        "记忆管理": "记忆管理",
        "会话管理": "会话管理",
        "Skill 对照": "Skill.*对照|触发对照",
        "子模式": "子模式",
        "MEMORY_WRITTEN": "MEMORY_WRITTEN",
        "转交判断": "转交判断|转交",
    }

    for agent_name, agent_content in [("learning", learning), ("work", work)]:
        for name, pattern in required_agent.items():
            if re.search(pattern, agent_content):
                pass  # 不报 PASS 来减少噪音
            else:
                record(f"CMP-{agent_name[0].upper()}-{name[:3].upper()}", "ERROR",
                       f"{agent_name}-agent.md 缺少 [{name}] 区块",
                       f"补充 {name} 定义")

    # 如果全部通过
    missing_count = sum(1 for r in results if r["id"].startswith("CMP-") and r["level"] == "ERROR")
    if missing_count == 0:
        record("CMP-ALL", "PASS", "所有必要区块完整")

# ─── 检查 6：交叉引用完整性 ───
def check_cross_references():
    """检查 Agent 引用 CLAUDE.md 时用的是引用而非重述"""
    learning = read_file_safe(LEARNING_AGENT) or ""
    work = read_file_safe(WORK_AGENT) or ""

    # 好的引用模式
    good_ref_patterns = [
        r"CLAUDE\.md.*(?:铁律|启动协议|规则)",
        r"遵循\s*CLAUDE\.md",
        r"见\s*CLAUDE\.md",
        r"执行\s*CLAUDE\.md",
    ]

    for agent_name, content in [("learning", learning), ("work", work)]:
        has_good_refs = any(re.search(p, content) for p in good_ref_patterns)
        if has_good_refs:
            record(f"XREF-{agent_name[0].upper()}01", "PASS",
                   f"{agent_name}-agent.md 正确引用了 CLAUDE.md（而非重述）")
        else:
            record(f"XREF-{agent_name[0].upper()}01", "WARNING",
                   f"{agent_name}-agent.md 可能在重述 CLAUDE.md 的规则而非引用",
                   "将重述改为'见 CLAUDE.md 的 XX 区块'")

# ─── 主程序 ───
def main():
    parser = argparse.ArgumentParser(description="Prompt 系统一致性检查")
    parser.add_argument("--report", action="store_true", help="输出详细报告")
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题（暂未实现）")
    parser.add_argument("--pre-commit", dest="pre_commit", action="store_true", help="作为 git hook：有 ERROR 时 exit 1")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    # 检查文件存在
    missing_files = []
    for path, name in [(CLAUDE_MD, "CLAUDE.md"), (LEARNING_AGENT, "learning-agent.md"), (WORK_AGENT, "work-agent.md")]:
        if not path.exists():
            missing_files.append({"name": name, "path": str(path)})
    if missing_files:
        if args.json:
            print(json.dumps({
                "results": [
                    {
                        "id": "required_file_exists",
                        "level": "ERROR",
                        "message": f"找不到 {item['name']}: {item['path']}",
                    }
                    for item in missing_files
                ],
                "summary": {"error": len(missing_files), "warning": 0, "pass": 0},
            }, ensure_ascii=False, indent=2))
            sys.exit(1)
        for item in missing_files:
            print(f"❌ 找不到 {item['name']}: {item['path']}")
        sys.exit(1)

    if not args.json:
        print("=" * 60)
        print(f"  verify_prompt_system.py — Prompt 系统一致性检查")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        print()

    # 运行所有检查
    check_duplicate_definitions()
    check_stale_references()
    check_priority_violations()
    check_format_consistency()
    check_content_completeness()
    check_cross_references()

    # 统计
    errors = [r for r in results if r["level"] == "ERROR"]
    warnings = [r for r in results if r["level"] == "WARNING"]
    passes = [r for r in results if r["level"] == "PASS"]

    if args.json:
        print(json.dumps({"results": results, "summary": {
            "error": len(errors), "warning": len(warnings), "pass": len(passes)
        }}, ensure_ascii=False, indent=2))
        sys.exit(1 if errors else 0)

    # 输出结果
    for r in results:
        if r["level"] == "ERROR":
            icon = "❌"
        elif r["level"] == "WARNING":
            icon = "⚠️ "
        else:
            if not args.report:
                continue  # 非详细模式下不显示 PASS
            icon = "✅"

        print(f"  {icon} [{r['id']}] {r['message']}")
        if r.get("fix_hint") and (args.report or r["level"] != "PASS"):
            print(f"      💡 {r['fix_hint']}")

    # 汇总
    print()
    print("─" * 50)
    print(f"  ✅ {len(passes)} PASS | ⚠️  {len(warnings)} WARNING | ❌ {len(errors)} ERROR")

    if errors:
        print(f"\n  ❌ 有 {len(errors)} 个 ERROR 需要修复")
    elif warnings:
        print(f"\n  ⚠️  {len(warnings)} 个 WARNING（非阻塞，建议优化）")
    else:
        print(f"\n  ✅ 全部通过！")

    # pre-commit 模式
    if args.pre_commit:
        if errors:
            print(f"\n  🚫 pre-commit: 阻止提交（{len(errors)} ERROR）")
            print(f"  💡 修复后重试，或 git commit --no-verify 跳过")
            sys.exit(1)

    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
