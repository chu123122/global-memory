# Global Memory

个人 AI 工作系统的记忆仓库。Git 同步，跨设备共享。

## 架构

```
L1 身份层    CLAUDE.md          ← 每次对话自动加载
L2 领域层    MEMORY.md + Topic  ← 按需读取
L3 会话层    对话临时记忆        ← 不持久化
L4 归档层    archives/          ← 30天+ 未访问的冷存储
```

## 目录

```
global-memory/
├── MEMORY.md               # 索引 + 活跃项目列表
├── CHANGELOG.md             # 变更审计日志
├── memory-rules.md          # CHANGELOG 分级规则（权威定义）
├── FIXLIST.md
│
├── feedback/                # 行为纠正（2 个）
│   ├── feedback_code_style.md
│   └── feedback_output_format.md
│
├── knowledge/               # 技术知识（7 个 Topic + 31 个 docs）
│   ├── knowledge_cpp_multithreading.md
│   ├── knowledge_cpp_pitfalls.md
│   ├── knowledge_lua_patterns.md
│   ├── knowledge_skill_design.md
│   ├── knowledge_system_design.md
│   ├── knowledge_ue_internals.md
│   ├── knowledge_unity_dots.md
│   ├── docs/                # 深度文档（31 个，不要求 YAML 头）
│   └── references/          # 外部资源索引
│
├── fixes/                   # Bug 修复经验（1 个）
│   └── fixes_common_build_errors.md
│
├── interview/               # 面试准备（5 个）
│   ├── interview_weakness_tracker.md
│   ├── interview_question_bank.md
│   ├── interview_mock_history.md
│   ├── career-strategy-2027.md
│   └── resume-versions.md
│
├── decisions/               # 架构决策 + 跨项目规范（1 个）
│   └── conventions.md       # 17 条规范，15 条 🔒 硬检查
│
├── projects/                # 项目级上下文
│   └── xindong-engine/
│       ├── dev-map.md
│       ├── onboarding-plan.md
│       └── task-board.md
│
├── retrospectives/          # 复盘记录
├── test-reports/            # 测试报告
└── archives/                # 归档
```

## 写入规则

**学习 Agent（积极记忆）**：新概念→knowledge/ | 错题→fixes/interview/ | 偏好→feedback/ | "记住"→立即写入

**工作 Agent（克制记忆）**：Bug 3+轮→fixes/ | "以后都这样"→feedback/ | 架构决策→decisions/ | 跨项目经验→PROMOTE 到 conventions.md

**CHANGELOG 规则**（详见 memory-rules.md）：

| 操作 | 写 CHANGELOG？ |
|------|:-:|
| 新建 / 大幅重写 Topic | 必须 |
| feedback / fixes / decisions 修改 | 必须 |
| knowledge / interview 追加 | 可省 |
| MEMORY.md 索引自动重建 | 可省 |

## 容量

| 项 | 上限 | 当前 |
|----|------|------|
| CLAUDE.md | 60 行 | 68 行 |
| MEMORY.md 索引 | 50 条 | 16 条 |
| 单个 Topic 文件 | 200 行 | — |
| Topic 文件总数（不含 docs） | 50 | 16 |

## 健康检查

```bash
python verify_memory.py            # 13 项健康检查
python verify_memory.py --report   # 含文件级详情
python verify_conventions.py <dir> # 对项目代码检查 🔒 规范
```

## 同步

`auto_sync_daemon.py` 守护进程：监听文件变更，空闲 5 分钟自动 git push。

## 关联

- **skills-repo**: https://github.com/chu123122/skills-repo.git

## 更新日志

- **2026-04-17**: 常规更新

- **2026-04-16**: 常规更新

- **2026-04-16**: 常规更新

- **2026-04-16**: 常规更新

- **2026-04-16**: 常规更新
