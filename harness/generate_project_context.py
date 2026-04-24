#!/usr/bin/env python3
"""
generate_project_context.py — 为项目生成 AI 上下文拼合文件

功能：
  1. 扫描项目 docs/ 下的关键文档（HANDOFF/SPEC/PROGRESS/TECHNICAL_DESIGN）
  2. 读取全局规范（conventions.md）和活跃项目信息（MEMORY.md）
  3. 拼合为一个 AI_CONTEXT.md，AI 只需读这一个文件就有完整上下文
  4. 同时生成 .workbuddy/RULES.md，让 WorkBuddy 自动注入启动协议

用法：
  python generate_project_context.py <项目目录>
  python generate_project_context.py <项目目录> --update   # 只更新，不覆盖手动编辑
  python generate_project_context.py <项目目录> --install   # 同时安装 .workbuddy/RULES.md
"""

import os
import sys
import datetime
import argparse
from pathlib import Path
import io

# Windows GBK 编码修复
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import MEMORY_DIR  # noqa: E402

# ─── 配置 ───────────────────────────────────────────────────

CONVENTIONS_FILE = MEMORY_DIR / "decisions" / "conventions.md"
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"

# 项目文档优先级（从高到低）
PROJECT_DOCS = [
    ("docs/HANDOFF.md", "交接文档（最重要，当前进度+下一步）"),
    ("docs/SPEC.md", "需求规格（做什么+验收标准）"),
    ("docs/PROGRESS.md", "实时进度表"),
    ("docs/TECHNICAL_DESIGN.md", "技术设计文档"),
    ("docs/HARNESS_REVIEW.md", "体系验证/复盘"),
]

# Topic 预判注入：关键词 → Topic 文件
# AI_CONTEXT 生成时，扫描项目文档内容，匹配关键词后自动注入对应 Topic 的前 N 行
TOPIC_KEYWORD_MAP = {
    "knowledge/knowledge_cpp_multithreading.md": [
        "多线程", "thread", "mutex", "atomic", "concurrent", "并发", "TaskGraph", "线程"],
    "knowledge/knowledge_cpp_pitfalls.md": [
        "智能指针", "shared_ptr", "unique_ptr", "RAII", "移动语义", "move", "模板"],
    "knowledge/knowledge_ue_internals.md": [
        "UE", "Unreal", "UObject", "GC", "反射", "Pak", "资源加载", "引擎"],
    "knowledge/knowledge_unity_dots.md": [
        "Unity", "ECS", "DOTS", "Burst", "JobSystem", "Archetype"],
    "knowledge/knowledge_lua_patterns.md": [
        "Lua", "require", "元表", "metatable", "LetsGo"],
    "knowledge/knowledge_system_design.md": [
        "系统设计", "架构", "模块", "四步法"],
    "knowledge/knowledge_skill_design.md": [
        "Skill", "SKILL.md", "防过拟合", "Few-shot"],
}

# ─── 辅助函数 ────────────────────────────────────────────────

def read_file_safe(path, max_lines=None):
    """安全读取文件，不存在返回 None"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            if max_lines:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"\n... (截断，完整内容见 {path})")
                        break
                    lines.append(line)
                return "".join(lines)
            return f.read()
    except (FileNotFoundError, PermissionError):
        return None


def extract_active_projects(memory_content):
    """从 MEMORY.md 提取活跃项目表"""
    if not memory_content:
        return None
    lines = memory_content.split("\n")
    in_section = False
    result = []
    for line in lines:
        if "当前活跃项目" in line or "🔥" in line:
            in_section = True
            result.append(line)
            continue
        if in_section:
            if line.startswith("##") and "活跃" not in line:
                break
            result.append(line)
    return "\n".join(result).strip() if result else None


def extract_conventions_summary(conv_content):
    """从 conventions.md 提取规范摘要（只取 ID + 规则名，不含案例）"""
    if not conv_content:
        return None
    lines = conv_content.split("\n")
    result = []
    for line in lines:
        # 提取 ### XXX-NN 🔒 ... 格式的规范标题
        stripped = line.strip()
        if stripped.startswith("### ") and any(
            prefix in stripped
            for prefix in ["DOC-", "CODE-", "GIT-", "MEM-", "HARNESS-"]
        ):
            result.append(stripped.replace("### ", "- "))
        # 提取规则行
        elif stripped.startswith("- **规则**："):
            result.append("  " + stripped)
    return "\n".join(result) if result else None


def detect_project_name(project_dir):
    """从项目目录推断项目名"""
    project_dir = Path(project_dir)
    # 尝试从 SPEC.md 提取
    spec = read_file_safe(project_dir / "docs" / "SPEC.md")
    if spec:
        for line in spec.split("\n"):
            if line.startswith("# SPEC:"):
                return line.replace("# SPEC:", "").strip()
    # 尝试从 HANDOFF.md 提取
    handoff = read_file_safe(project_dir / "docs" / "HANDOFF.md")
    if handoff:
        for line in handoff.split("\n"):
            if "·" in line and line.startswith("#"):
                return line.split("·")[0].replace("#", "").strip()
    # fallback: 目录名
    return project_dir.name


# ─── 生成 AI_CONTEXT.md ──────────────────────────────────────

def generate_context(project_dir, update_only=False):
    project_dir = Path(project_dir).resolve()
    output_file = project_dir / "AI_CONTEXT.md"

    if update_only and output_file.exists():
        print(f"  ⏭️  AI_CONTEXT.md 已存在，跳过（使用 --force 强制覆盖）")
        return str(output_file)

    project_name = detect_project_name(project_dir)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    sections = []

    # ─── 头部：启动协议 ───
    sections.append(f"""# AI 上下文：{project_name}

> **自动生成** by `generate_project_context.py` | 更新时间：{now}
> **用途**：AI 助手打开此项目时，先读这个文件获取完整上下文
> **重新生成**：`python ~/.claude/scripts/generate_project_context.py "{project_dir}"`

---

## ⚠️ 启动协议（必须遵守）

1. 你已经在读这个文件了 ✅
2. 通读下面的项目文档摘要，理解当前进度
3. 用 2-3 句话和用户核对："上次做到 XX，接下来是 YY，对吗？"
4. **用户确认后再开始干活**
5. 完成后运行：`python ~/.claude/scripts/task_complete.py "{project_dir}" --fix`
""")

    # ─── 活跃项目全景 ───
    memory_content = read_file_safe(MEMORY_INDEX)
    active_projects = extract_active_projects(memory_content)
    if active_projects:
        sections.append(f"""---

## 📋 全局活跃项目

{active_projects}
""")

    # ─── 项目文档 ───
    found_docs = []
    for rel_path, desc in PROJECT_DOCS:
        full_path = project_dir / rel_path
        content = read_file_safe(full_path, max_lines=200)
        if content:
            found_docs.append((rel_path, desc, content))

    if found_docs:
        sections.append("---\n\n## 📂 项目文档\n")
        for rel_path, desc, content in found_docs:
            sections.append(f"""### {rel_path} — {desc}

<details open>
<summary>展开查看</summary>

{content.strip()}

</details>
""")
    else:
        sections.append("""---

## 📂 项目文档

> ⚠️ 未找到任何项目文档（docs/HANDOFF.md, docs/SPEC.md 等）
> 建议先创建 docs/SPEC.md 定义任务目标和验收标准
""")

    # ─── Topic 预判注入（方案 A）───
    # 扫描项目文档内容，匹配关键词后注入对应 Topic 的核心内容
    all_doc_text = " ".join(content for _, _, content in found_docs).lower()
    matched_topics = []
    for topic_rel, keywords in TOPIC_KEYWORD_MAP.items():
        topic_path = MEMORY_DIR / topic_rel
        if any(kw.lower() in all_doc_text for kw in keywords):
            topic_content = read_file_safe(topic_path, max_lines=30)
            if topic_content:
                # 过滤掉 YAML 头部和空壳内容
                lines = topic_content.split("\n")
                body_lines = []
                in_yaml = False
                for line in lines:
                    if line.strip() == "---":
                        in_yaml = not in_yaml
                        continue
                    if in_yaml:
                        continue
                    if "（随" in line and "积累）" in line:
                        continue  # 跳过空壳占位行
                    if line.strip():
                        body_lines.append(line)
                if len(body_lines) > 3:  # 至少有实质内容才注入
                    matched_topics.append((topic_rel, "\n".join(body_lines[:20])))

    if matched_topics:
        sections.append("---\n\n## 🧠 相关知识上下文（自动匹配注入）\n")
        sections.append("> 以下 Topic 内容基于项目文档关键词自动匹配。详细内容见对应文件。\n")
        for topic_rel, body in matched_topics:
            topic_name = Path(topic_rel).stem.replace("knowledge_", "")
            sections.append(f"""### {topic_name}
> 文件：`~/.claude/global-memory/{topic_rel}`

{body}
""")

    # ─── 跨项目规范摘要 ───
    conv_content = read_file_safe(CONVENTIONS_FILE)
    conv_summary = extract_conventions_summary(conv_content)
    if conv_summary:
        sections.append(f"""---

## 📐 跨项目规范（摘要）

> 完整版见 `~/.claude/global-memory/decisions/conventions.md`
> 标注 🔒 的规范由脚本硬检查，违反会被 `verify_conventions.py` 拦截

{conv_summary}
""")

    # ─── 收尾提醒 ───
    sections.append(f"""---

## 🔧 任务收尾清单

完成工作后，运行以下脚本确保合规：

```bash
# 一键收尾（检查+修复+同步）
python ~/.claude/scripts/task_complete.py "{project_dir}" --fix

# 或分步执行
python ~/.claude/scripts/verify_conventions.py "{project_dir}" --all
python ~/.claude/scripts/post_task_hook.py --auto-fix
```

> 🔒 git commit 时会自动运行 pre-commit hook 拦截不合规的提交
""")

    # ─── 写入 ───
    full_content = "\n".join(sections)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"  ✅ 已生成 {output_file}")
    print(f"     项目名: {project_name}")
    print(f"     包含文档: {len(found_docs)} 个")
    print(f"     包含规范: {'是' if conv_summary else '否'}")

    return str(output_file)


# ─── 生成 .workbuddy/RULES.md ────────────────────────────────

def install_workbuddy_rules(project_dir):
    """在项目中安装 .workbuddy/RULES.md，让 WorkBuddy 自动注入启动协议"""
    project_dir = Path(project_dir).resolve()
    wb_dir = project_dir / ".workbuddy"
    rules_file = wb_dir / "RULES.md"

    wb_dir.mkdir(exist_ok=True)

    project_name = detect_project_name(project_dir)

    rules_content = f"""# 项目规则：{project_name}

## 启动协议（每次新对话必须执行）

**在回答任何问题之前，你必须先执行以下步骤：**

1. 读取本项目的 `AI_CONTEXT.md`（如果存在）— 这是项目的完整上下文拼合文件
2. 如果 `AI_CONTEXT.md` 不存在，依次读取：
   - `docs/HANDOFF.md`（交接文档，最重要）
   - `docs/SPEC.md`（需求规格）
   - `docs/PROGRESS.md`（进度表）
3. 用 2-3 句话和用户核对当前进度，确认后再开始工作
4. **绝对不要跳过这些步骤直接开始开发**

## 跨项目规范

本项目遵循 `~/.claude/global-memory/decisions/conventions.md` 中的跨项目规范。
关键规范（🔒 = 脚本硬检查）：

- 🔒 DOC-01: 项目必须有 SPEC + HANDOFF
- 🔒 DOC-02: HANDOFF 必须包含已确定的设计决策
- 🔒 CODE-02: C# 文件必须有 namespace
- 🔒 CODE-03: C++ header 必须有 pragma once
- 🔒 GIT-01: commit message 使用 conventional commits
- 🔒 MEM-01: 修改记忆文件必须写 CHANGELOG

## 任务收尾

每次完成工作后运行：
```bash
python ~/.claude/scripts/task_complete.py "{project_dir}" --fix
```

## 用户画像

- 游戏客户端/引擎开发，C++/C#(Unity)/Lua(UE)
- 偏好：直接给方案+trade-off，少说废话
- 不确定的事明说"不确定"
"""

    with open(rules_file, "w", encoding="utf-8") as f:
        f.write(rules_content)

    # 确保 .gitignore 包含 .workbuddy/
    gitignore = project_dir / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if ".workbuddy/" not in content:
            with open(gitignore, "a", encoding="utf-8") as f:
                f.write("\n# WorkBuddy 本地配置\n.workbuddy/\n")
            print(f"  ✅ 已添加 .workbuddy/ 到 .gitignore")
    else:
        with open(gitignore, "w", encoding="utf-8") as f:
            f.write("# WorkBuddy 本地配置\n.workbuddy/\n")
        print(f"  ✅ 已创建 .gitignore（含 .workbuddy/）")

    print(f"  ✅ 已安装 {rules_file}")
    return str(rules_file)


# ─── 主入口 ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="为项目生成 AI 上下文拼合文件"
    )
    parser.add_argument("project_dir", help="项目根目录")
    parser.add_argument(
        "--update", action="store_true",
        help="只更新，已存在则跳过"
    )
    parser.add_argument(
        "--install", action="store_true",
        help="同时安装 .workbuddy/RULES.md"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="强制覆盖已存在的文件"
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    if not project_dir.is_dir():
        print(f"  ❌ 目录不存在: {project_dir}")
        sys.exit(1)

    print("=" * 60)
    print("  generate_project_context.py")
    print("=" * 60)
    print()

    # 生成 AI_CONTEXT.md
    update_only = args.update and not args.force
    context_file = generate_context(project_dir, update_only)
    print()

    # 安装 .workbuddy/RULES.md
    if args.install:
        install_workbuddy_rules(project_dir)
        print()

    print("=" * 60)
    print("  完成！")
    print()
    print(f"  AI 打开项目时会自动获取上下文：")
    if args.install:
        print(f"  1. .workbuddy/RULES.md → WorkBuddy 自动注入启动协议")
        print(f"  2. AI_CONTEXT.md → 项目文档 + 规范 + 收尾清单")
    else:
        print(f"  1. AI_CONTEXT.md → 项目文档 + 规范 + 收尾清单")
        print(f"  💡 加 --install 同时安装 .workbuddy/RULES.md（推荐）")
    print("=" * 60)


if __name__ == "__main__":
    main()
