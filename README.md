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
├── feedback/                # 行为纠正（3 个）
│   ├── feedback_code_style.md
│   ├── feedback_infra_ops_windows.md
│   └── feedback_output_format.md
│
├── knowledge/               # 技术知识（8 个 Topic + 32 个 docs）
│   ├── knowledge_cpp_multithreading.md
│   ├── knowledge_cpp_pitfalls.md
│   ├── knowledge_lua_patterns.md
│   ├── knowledge_skill_design.md
│   ├── knowledge_system_design.md
│   ├── knowledge_ue_internals.md
│   ├── knowledge_unity_dots.md
│   ├── knowledge_windows_dev_env.md
│   ├── docs/                # 深度文档（32 个，含 INDEX.md，不要求 YAML 头）
│   └── references/          # 外部资源索引
│
├── fixes/                   # Bug 修复经验（2 个）
│   ├── fixes_android_apk_build.md
│   └── fixes_common_build_errors.md
│
├── interview/               # 面试准备（6 个）
│   ├── autumn-positioning-2026-04-17.md
│   ├── interview_weakness_tracker.md
│   ├── interview_question_bank.md
│   ├── interview_mock_history.md
│   ├── career-strategy-2027.md
│   └── resume-versions.md
│
├── decisions/               # 架构决策 + 跨项目规范（2 个）
│   ├── conventions.md       # 17 条规范，15 条 🔒 硬检查
│   └── decision_work_mode_workflow.md
│
├── projects/                # 项目级上下文
│   └── xindong-engine/
│       ├── SPEC.md
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
| 计入统计的记忆文件总数 | 50 | 53 |
| Topic 文件总数（不含 docs） | 50 | 21 |
| 单个 Topic 文件（规则上限） | 200 行 | — |
| 单个 Topic 文件（当前最大） | 200 行 | 198 |

## 健康检查

```bash
python check_health.py        # 6 项健康检查
python check_health.py --fix  # 自动修复索引/统计，并检查 git 状态
python check_health.py --json # 机器可读输出
```

> 旧文档里出现的 `verify_memory.py` / `verify_conventions.py` 属于历史命名；当前仓库内可直接运行的入口是 `check_health.py`。

## 同步与自动维护

当前仓库只保存记忆数据与本地健康检查脚本。

自动维护发生在部署环境：
- `Stop` hook 调用 `~/.claude/skills-repo/_bootstrap/scripts/post_task_hook.py --auto-fix`
- `post_task_hook.py` 需要时再调用 `sync_index.py` / `update_stats.py`
- `MEMORY.md` 的 `AUTO-INDEX` 区块由这套部署侧脚本维护，不在本仓库内直接实现

## 关联

- **skills-repo**: https://github.com/chu123122/skills-repo.git
