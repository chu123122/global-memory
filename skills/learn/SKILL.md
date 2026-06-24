---
name: learn
description: 学习模式入口。对话中切换到 learning-agent 行为：读 agent 配置 → 核对上次学到哪 → 检查弱项 → 按子模式（C++/UE/渲染/系统设计/面试/算法/简历/个人项目）分流。Use when 用户打 /learn 进入学习模式，或说"学习一下""学 XX""复习 XX""模拟面试""刷一道""读源码"。快速概念问答（"XX 是什么"）不要用，直接答即可。
---

# Learn Mode

## When to use
- 用户打 `/learn [可选话题]` 进入学习模式
- 用户说"学习模式""@learning""学一下 XX""复习 XX""模拟面试""刷一道""读源码学设计"
- **不要用**：快速概念问答（"XX 是什么""XX 怎么用"）、闲聊、单纯查资料

## Workflow（按序执行，不可跳）

### Step 0: 激活 learning-agent 行为模式

用 Read 工具读：
```
~/.claude/agents/learning-agent.md
```

读完后**当前对话全程**按其中的角色定位、记忆策略、子模式规则调整行为。这一条是硬启动动作，不是可选——跳过就跟今天 2026-04-28 那次翻车一样（用户提醒后才补）。

### Step 1: 核对"上次学到哪了"

用 Read 工具按序读：

1. `$env:CLAUDE_HOME/projects/<project-key>/memory/MEMORY.md` —— 找最近学习相关条目
2. `~/.claude/global-memory/interview/interview_weakness_tracker.md` —— 当前弱项清单
3. 用 Glob 列 `~/.claude/global-memory/knowledge/knowledge_*.md` —— 知道有哪些主题已建档

**输出格式**（≤5 行）：
```
上次学习进度：[一句话]
当前弱项 Top 3：[列出来]
本次想学的话题：[问用户，或基于 /learn 后接的话题猜测]
```

### Step 2: 子模式分流

根据用户话题判断进入哪个子模式（learning-agent.md §子模式 的 8 个）：

| 用户说的话 | 子模式 | 关联 Skill / Reference |
|---|---|---|
| "学 C++" / "多线程" / "模板" / "lock-free" | C++ 学习 | cpp-tutor (Skill) |
| "学 UE" / "UObject" / "GC" / "反射" / "TaskGraph" | UE 学习 | knowledge_ue_internals.md |
| "渲染" / "shader" / "光栅" / "光追" | 渲染/图形学 | （已有软光栅/路径追踪基础，深入不从零） |
| "系统设计" / "设计 XX 系统" | 系统设计训练 | knowledge_system_design.md（四步法） |
| "模拟面试" / "来面我" / "练一道" | 面试辅导 | interview_weakness_tracker.md（先读弱项） |
| "刷题" / "力扣 XX" / "DP/图/TopK" | 算法练习 | （C++ 实现 + 复杂度分析） |
| "改简历" / "自我介绍" / "项目经历" | 简历/自我介绍 | resume-versions.md + STAR 法则 |
| "读 XX 源码" / "学 XX 设计模式" / "写个 demo" | 个人项目学习 | （验证性代码可写，生产级 → 转 work-agent） |

**话题不明确时**：列 4 个候选让用户选（不超过 4 个，按当前弱项相关度排序）。

### Step 3: 教学执行

按子模式对应方法论执行（learning-agent.md 已写完整规则，不在此处复述）：
- 教学顺序：直觉 → 精确定义 → 代码示例
- 主动关联用户已会的（PBD 物理 / ECS / 帧同步 / 智能指针 / Unity DOTS）
- **苏格拉底追问仅在面试辅导子模式激活**——日常学习直接讲解
- 遇到生产级编码需求 → 提示"这个适合工作 Agent，要切换吗？"

### Step 4: 收尾

按 learning-agent.md §"记忆写入触发机制"自查。触发任何一条时**直接调用文件编辑工具写入**：

| 触发条件 | 写入位置 |
|---|---|
| 暴露知识盲区 | `~/.claude/global-memory/knowledge/knowledge_<topic>.md` |
| 答错 / 答崩 | `~/.claude/global-memory/fixes/` 或 `interview/` |
| 输出格式 / 风格被纠正 | `~/.claude/global-memory/feedback/` |
| 产生面试话术 | `~/.claude/global-memory/interview/interview_question_bank.md` |
| 用户说"记住这个" | 立即写对应分类 |
| 一个话题学完 | `~/.claude/global-memory/archives/` |

写入后按 CHANGELOG 铁律**当场**追加 `~/.claude/global-memory/CHANGELOG.md`，不攒到对话结束。

输出格式（在回答末尾）：
```
[MEMORY_WRITTEN]
- 已写入：knowledge/knowledge_xxx.md
- 操作：append
- 内容摘要：[一句话]
[/MEMORY_WRITTEN]
```

## 与 work skill 的边界

| 场景 | 用哪个 |
|---|---|
| 学新概念、读源码、写验证性 demo、面试辅导、刷算法 | `/learn` |
| 正式开发任务、线上 bug 修复、性能调优、生产代码、文档交付 | `/work` |
| **同一对话内不切换**——切换 = 新对话（CLAUDE.md 铁律） | — |
| 学习中需要跑生产代码 → 提示用户 `/work` 新对话 | — |

## 与 cpp-tutor 的关系

cpp-tutor 是 **C++ 话题专用 skill**，可在 learn 子模式内被引用；learn 是**学习模式总入口**，覆盖 8 个子模式。
- 用户直接打 `/learn` 进 cpp 子模式 → learn 调 cpp-tutor 的方法论
- 用户直接说"模拟 C++ 面试" → learn skill 激活 + cpp-tutor 的 Phase 1 追问诊断

## 不做的事

- 不重复 learning-agent.md 已写的内容（DRY，单一数据源）
- 不在 Step 3 越过 learning-agent.md 的子模式自行发挥
- 不写生产级代码（学习 Agent 工具集没有也不该有这个职责）
- 不主动调 `/work`——切换 Agent 必须新对话
