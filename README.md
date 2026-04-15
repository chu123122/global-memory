# Global Memory

个人 AI 工作系统的记忆仓库，通过 Git 实现跨设备同步。含知识积累、面试追踪、行为偏好、跨项目规范和变更审计。

## 四层记忆架构

```
L1 身份层    CLAUDE.md（≤60 行核心约束，每次对话自动加载）
L2 领域层    MEMORY.md 索引 + Topic 文件（按需读取）
L3 会话层    对话中的临时记忆（不持久化）
L4 归档层    archives/（过时记忆的冷存储）
```

## 记忆分类

| 分类 | 存什么 | 文件数 |
|------|--------|:------:|
| **feedback/** | 行为纠正（代码风格、输出格式偏好） | 2 |
| **knowledge/** | 技术知识积累（C++/Lua/UE/Unity/系统设计） | 7 |
| **knowledge/docs/** | 深度知识文档（UE 全景图/多线程/面试追问链等） | 8 |
| **fixes/** | Bug 修复经验 | 1 |
| **interview/** | 面试弱项追踪、真题积累、模拟记录、速查卡 | 4 |
| **decisions/** | 架构决策 + **跨项目规范 (conventions.md)** | 1 |
| **archives/** | 归档（30 天+ 未访问的记忆） | — |

## 变更审计

修改记忆文件后在 `CHANGELOG.md` 追加记录，规则如下（权威定义见 `memory-rules.md`）：

| 操作 | 是否写 CHANGELOG |
|------|:---:|
| 新建 / 大幅重写任何 Topic 文件 | ✅ 必须 |
| feedback / fixes / decisions 任何修改 | ✅ 必须 |
| knowledge / interview 的追加（append） | ❌ 可省略 |
| MEMORY.md 索引自动重建 | ❌ 可省略 |

格式：

```markdown
### [YYYY-MM-DD] 来源项目 · 变更类型

- **变更**：做了什么
- **原因**：为什么改
- **影响**：影响了哪些文件
```

这是跨项目沉淀的追踪机制——一个项目里总结的经验写入记忆后，另一个项目的 AI 读到时能知道这条记忆从哪来、为什么加。

## 跨项目规范

`decisions/conventions.md` 存放所有项目共同遵守的规范，每条标注：
- 🔒 = 有脚本硬检查（`verify_conventions.py` 自动验证）
- 📋 = 软约束（靠 AI 自觉）

当前 15 条规范，14 条有硬检查。

## 健康检查

```bash
# 记忆仓库全量健康检查（13 项）
python E:/CS-Study/Vibe/skills-repo/_bootstrap/scripts/verify_memory.py

# 详细报告模式（含每个文件的行数/大小/YAML 状态）
python E:/CS-Study/Vibe/skills-repo/_bootstrap/scripts/verify_memory.py --report

# 规范合规检查（对项目代码）
python E:/CS-Study/Vibe/skills-repo/_bootstrap/scripts/verify_conventions.py <项目目录> --all
```

### verify_memory.py 检查项（13 项）

| ID | 检查内容 |
|----|---------|
| MEM-01 | 索引完整性（Topic 文件 → MEMORY.md 索引） |
| MEM-02 | 索引无死链（索引 → 文件存在） |
| MEM-03 | Topic 文件 YAML 头格式（6 个必填字段） |
| MEM-04 | 更新日志区块存在 |
| MEM-05 | docs/ 大文件格式（标题层级） |
| MEM-06 | CHANGELOG.md 存在 |
| MEM-07 | CHANGELOG 时效性（7 天内有记录） |
| MEM-08 | 活跃项目交接文档引用 |
| MEM-09 | 文件总数上限（≤50） |
| MEM-10 | 文件内容非空 |
| MEM-11 | 孤儿文件检测 |
| MEM-12 | 规范硬检查覆盖率 |
| MEM-13 | 内容重复检测 |

## 目录结构

```
global-memory/
├── MEMORY.md                              # L2 索引 + 活跃项目列表
├── CHANGELOG.md                           # ★ 变更审计日志
├── README.md
│
├── feedback/
│   ├── feedback_code_style.md
│   └── feedback_output_format.md
│
├── knowledge/
│   ├── knowledge_cpp_pitfalls.md          # 智能指针/RAII/模板陷阱
│   ├── knowledge_cpp_multithreading.md    # 多线程（重点短板）
│   ├── knowledge_lua_patterns.md
│   ├── knowledge_ue_internals.md          # UE TaskGraph/线程模型
│   ├── knowledge_unity_dots.md            # ECS/DOTS/Burst
│   ├── knowledge_skill_design.md
│   ├── knowledge_system_design.md         # 四步法方法论
│   └── docs/                              # 深度知识文档
│       ├── ue-engine-internals-guide.md   # 852 行 · UE 10 大模块全景图
│       ├── cpp-multithreading-guide.md    # 754 行 · 5 章 + 30 道面试题
│       ├── prompt-engineering-system.md   # 503 行 · 8 场景 + 6 阶段 SOP
│       ├── interview-deep-dive-chains.md  # 268 行 · 12 知识点追问链
│       ├── project-interview-scripts.md   # 171 行 · 4 项目面试话术
│       ├── code-review-blog-templates.md  # 198 行 · 25 条 Review + 5 种博客模板
│       ├── async-resource-loading-preresearch.md  # 692 行 · 多线程资源加载预研
│       └── interview-cheatsheet.md        # 118 行 · 面试速查卡
│
├── fixes/
│   └── fixes_common_build_errors.md
│
├── interview/
│   ├── interview_weakness_tracker.md      # 弱项追踪与改进进度
│   ├── interview_question_bank.md         # 真题按方向分类
│   └── interview_mock_history.md          # 模拟面试评分记录
│
├── decisions/
│   └── conventions.md                     # ★ 跨项目规范（12 条，8 条硬检查）
│
├── projects/                              # 项目级上下文
│   └── xindong-engine/
│       ├── dev-map.md                     # 项目导航
│       └── task-board.md                  # 任务看板
│
└── archives/
    └── .gitkeep
```

## 容量限制

| 层级 | 限制 |
|------|------|
| CLAUDE.md | ≤ 60 行 |
| MEMORY.md 索引 | ≤ 50 条 |
| 单个 Topic 文件 | ≤ 200 行（超过则拆分） |
| Topic 文件总数 | ≤ 50 个（当前 22） |

## 写入规则

### 学习 Agent（积极记忆）
- 新概念 → knowledge/
- 错题/面试崩 → fixes/ 或 interview/
- 学习偏好 → feedback/
- "记住这个" → 立即写入
- 写入后按上表规则决定是否写 CHANGELOG

### 工作 Agent（克制记忆）
- Bug 3+ 轮才定位 → fixes/
- "以后都这样做" → feedback/
- 架构决策确认 → decisions/
- 跨项目可复用经验 → PROMOTE 到 conventions.md
- 写入后按上表规则决定是否写 CHANGELOG

## 同步

由 `auto_sync_daemon.py` 守护进程自动处理，空闲 5 分钟后自动 push。

## 关联仓库

- **skills-repo**: https://github.com/chu123122/skills-repo.git — Skill 仓库 + 脚本 + Harness 模板 + 初始化工具

## 更新日志

- **2026-04-13**: 常规更新

- **2026-04-13**: 拆分 maintain_memory.py 为 6 个单一职责脚本 + 共享库 _lib.py，新增 update_readme.py 自动更新 README，所有脚本加运行留档
