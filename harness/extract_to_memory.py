#!/usr/bin/env python3
"""
extract_to_memory.py — 从工作区日志提取内容到全局记忆

扫描 WorkBuddy 工作区的 daily log，提取有价值的内容，
建议或自动写入 global-memory 的 Topic 文件。

用法：
    python extract_to_memory.py                    # 扫描今天的日志
    python extract_to_memory.py --date 2026-04-13  # 扫描指定日期
    python extract_to_memory.py --scan-all         # 扫描所有日志
    python extract_to_memory.py --auto             # 自动写入（不用确认）

工作原理：
    1. 读取工作区日志（.workbuddy/memory/YYYY-MM-DD.md）
    2. 按关键词分类内容（知识/修复/决策/面试/反馈）
    3. 输出建议写入的 Topic 文件和内容
    4. --auto 模式下直接追加到 Topic 文件
"""

import io
import os
import re
import sys
import glob
from pathlib import Path
from datetime import datetime, date

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 配置 ──
MEMORY_DIR = Path.home() / ".claude" / "global-memory"
LOG_DIR = Path.home() / ".claude" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 关键词 → Topic 文件映射
KEYWORD_MAP = {
    "knowledge": {
        "keywords": ["设计决策", "关键设计", "架构", "技术选型", "方案对比",
                     "核心概念", "原理", "算法", "数据结构"],
        "targets": {
            "c++": "knowledge/knowledge_cpp_pitfalls.md",
            "多线程": "knowledge/knowledge_cpp_multithreading.md",
            "thread": "knowledge/knowledge_cpp_multithreading.md",
            "mutex": "knowledge/knowledge_cpp_multithreading.md",
            "atomic": "knowledge/knowledge_cpp_multithreading.md",
            "lua": "knowledge/knowledge_lua_patterns.md",
            "ue": "knowledge/knowledge_ue_internals.md",
            "unreal": "knowledge/knowledge_ue_internals.md",
            "unity": "knowledge/knowledge_unity_dots.md",
            "ecs": "knowledge/knowledge_unity_dots.md",
            "dots": "knowledge/knowledge_unity_dots.md",
            "skill": "knowledge/knowledge_skill_design.md",
            "系统设计": "knowledge/knowledge_system_design.md",
        }
    },
    "fixes": {
        "keywords": ["bug", "修复", "fix", "错误", "crash", "崩溃", "排查",
                     "WARNING", "ERROR", "修复后"],
        "target": "fixes/fixes_common_build_errors.md"
    },
    "interview": {
        "keywords": ["面试", "话术", "追问", "弱项", "interview", "weakness"],
        "targets": {
            "弱项": "interview/interview_weakness_tracker.md",
            "weakness": "interview/interview_weakness_tracker.md",
            "真题": "interview/interview_question_bank.md",
            "题目": "interview/interview_question_bank.md",
            "模拟": "interview/interview_mock_history.md",
        }
    },
    "feedback": {
        "keywords": ["代码风格", "命名约定", "输出格式", "偏好", "以后都这样"],
        "targets": {
            "风格": "feedback/feedback_code_style.md",
            "格式": "feedback/feedback_output_format.md",
        }
    },
    "decisions": {
        "keywords": ["规范", "convention", "PROMOTE", "跨项目", "全局规则"],
        "target": "decisions/conventions.md"
    }
}


def find_workbuddy_logs():
    """找到所有 WorkBuddy 工作区的日志目录"""
    wb_root = Path.home() / "WorkBuddy"
    if not wb_root.exists():
        return []
    
    logs = []
    for ws in wb_root.iterdir():
        if ws.is_dir():
            mem_dir = ws / ".workbuddy" / "memory"
            if mem_dir.exists():
                for f in sorted(mem_dir.glob("202?-??-??.md")):
                    logs.append(f)
    return logs


def extract_sections(content):
    """将 markdown 内容拆分为 ## 级别的段落"""
    sections = []
    current_title = ""
    current_lines = []
    
    for line in content.splitlines():
        if line.startswith("## "):
            if current_title:
                sections.append((current_title, "\n".join(current_lines)))
            current_title = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    
    if current_title:
        sections.append((current_title, "\n".join(current_lines)))
    
    return sections


def classify_section(title, content):
    """根据关键词判断一个段落应该写入哪个 Topic 文件"""
    text = (title + " " + content).lower()
    suggestions = []
    
    for category, config in KEYWORD_MAP.items():
        # 检查是否匹配该分类的关键词
        matched = any(kw.lower() in text for kw in config["keywords"])
        if not matched:
            continue
        
        # 确定具体的 target 文件
        if "targets" in config:
            for sub_kw, target in config["targets"].items():
                if sub_kw.lower() in text:
                    suggestions.append((category, target, title))
                    break
            else:
                # 匹配了分类但没匹配到具体 target
                if "target" in config:
                    suggestions.append((category, config["target"], title))
        elif "target" in config:
            suggestions.append((category, config["target"], title))
    
    return suggestions


def format_extract(title, content, max_lines=10):
    """格式化提取的内容为适合写入 Topic 文件的格式"""
    lines = [l for l in content.strip().splitlines() if l.strip()]
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... (截断，共 {len(lines)} 行)"]
    
    result = f"\n### {title} ({date.today().isoformat()})\n"
    result += "\n".join(lines)
    return result


def append_to_topic(target_file, content, dry_run=False):
    """追加内容到 Topic 文件的更新日志之前"""
    filepath = MEMORY_DIR / target_file
    if not filepath.exists():
        print(f"  ⚠️ 文件不存在: {target_file}")
        return False
    
    if dry_run:
        print(f"  [DRY RUN] 会追加到 {target_file}")
        return True
    
    text = filepath.read_text(encoding="utf-8", errors="replace")
    
    # 在 "## 更新日志" 之前插入
    marker = "---\n## 更新日志"
    if marker in text:
        text = text.replace(marker, content + "\n\n" + marker)
    else:
        # 没有更新日志区块，追加到末尾
        text += "\n" + content
    
    filepath.write_text(text, encoding="utf-8")
    return True


def log_run(message):
    """留档"""
    log_file = LOG_DIR / "extract_to_memory.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {message}\n")
    # 轮转
    try:
        lines = log_file.read_text(encoding="utf-8").splitlines()
        if len(lines) > 500:
            log_file.write_text("\n".join(lines[-250:]) + "\n", encoding="utf-8")
    except Exception:
        pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description="从工作区日志提取到全局记忆")
    parser.add_argument("--date", help="指定日期 (YYYY-MM-DD)")
    parser.add_argument("--scan-all", action="store_true", help="扫描所有日志")
    parser.add_argument("--auto", action="store_true", help="自动写入不确认")
    parser.add_argument("--dry-run", action="store_true", help="只显示建议")
    args = parser.parse_args()
    
    print("=== extract_to_memory: 从工作区日志提取到全局记忆 ===\n")
    
    # 收集日志文件
    all_logs = find_workbuddy_logs()
    if not all_logs:
        print("  ⚠️ 未找到任何 WorkBuddy 工作区日志")
        return
    
    # 筛选
    if args.date:
        target_date = args.date
        logs = [f for f in all_logs if target_date in f.name]
    elif args.scan_all:
        logs = all_logs
    else:
        today = date.today().isoformat()
        logs = [f for f in all_logs if today in f.name]
    
    if not logs:
        print(f"  ⚠️ 未找到匹配的日志文件")
        return
    
    print(f"  扫描 {len(logs)} 个日志文件\n")
    
    # 提取
    all_suggestions = []
    for log_file in logs:
        content = log_file.read_text(encoding="utf-8", errors="replace")
        sections = extract_sections(content)
        
        for title, body in sections:
            suggestions = classify_section(title, body)
            for category, target, sec_title in suggestions:
                extract = format_extract(sec_title, body)
                all_suggestions.append({
                    "source": log_file.name,
                    "category": category,
                    "target": target,
                    "title": sec_title,
                    "content": extract,
                    "body": body,
                })
    
    if not all_suggestions:
        print("  ✅ 没有需要提取的内容")
        log_run("scan: 0 suggestions")
        return
    
    # 去重（同一个 target + title 只保留一个）
    seen = set()
    unique = []
    for s in all_suggestions:
        key = (s["target"], s["title"])
        if key not in seen:
            seen.add(key)
            unique.append(s)
    
    print(f"  找到 {len(unique)} 条建议：\n")
    
    for i, s in enumerate(unique, 1):
        print(f"  [{i}] {s['category'].upper()} → {s['target']}")
        print(f"      来源: {s['source']} / {s['title']}")
        preview = s['body'][:100].replace('\n', ' ')
        print(f"      预览: {preview}...")
        print()
    
    # 写入
    if args.dry_run:
        print(f"  [DRY RUN] 共 {len(unique)} 条建议，不执行写入")
        log_run(f"dry-run: {len(unique)} suggestions")
        return
    
    if args.auto:
        written = 0
        for s in unique:
            if append_to_topic(s["target"], s["content"]):
                print(f"  ✅ 已写入 {s['target']}")
                written += 1
        print(f"\n  共写入 {written} / {len(unique)} 条")
        log_run(f"auto: {written}/{len(unique)} written")
    else:
        print(f"  共 {len(unique)} 条建议。使用 --auto 自动写入，或手动处理。")
        log_run(f"scan: {len(unique)} suggestions (manual)")


if __name__ == "__main__":
    main()
