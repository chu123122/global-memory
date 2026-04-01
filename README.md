# Global Memory

个人 AI 工作系统的记忆仓库，通过 Git 实现跨设备同步。

## 四层记忆架构

```
L1 身份层    CLAUDE.md（≤60 行，每次对话自动加载）
L2 领域层    MEMORY.md 索引 + Topic 文件（按需读取）
L3 会话层    对话中的临时记忆（不持久化）
L4 归档层    archives/（过时记忆的冷存储）
```

## 记忆分类

| 分类 | 存什么 | 文件数 |
|------|--------|:------:|
| **feedback/** | 行为纠正（代码风格、输出格式偏好） | 2 |
| **knowledge/** | 技术知识积累（C++/Lua/UE/Unity/系统设计） | 7 |
| **fixes/** | Bug 修复经验 | 1 |
| **interview/** | 面试弱项追踪、真题积累、模拟记录 | 3 |
| **decisions/** | 架构决策记录 | — |
| **archives/** | 归档（30 天+ 未访问的记忆） | — |

## 目录结构

```
global-memory/
├── MEMORY.md                              # L2 索引（始终参考）
├── feedback/
│   ├── feedback_code_style.md
│   └── feedback_output_format.md
├── knowledge/
│   ├── knowledge_cpp_pitfalls.md          # 智能指针/RAII/模板陷阱
│   ├── knowledge_cpp_multithreading.md    # 多线程（最高优先级短板）
│   ├── knowledge_lua_patterns.md
│   ├── knowledge_ue_internals.md          # UE TaskGraph/线程模型
│   ├── knowledge_unity_dots.md            # ECS/DOTS/Burst
│   ├── knowledge_skill_design.md
│   └── knowledge_system_design.md         # 四步法方法论
├── fixes/
│   └── fixes_common_build_errors.md
├── interview/
│   ├── interview_weakness_tracker.md      # 弱项追踪与改进进度
│   ├── interview_question_bank.md         # 真题按方向分类
│   └── interview_mock_history.md          # 模拟面试评分记录
├── decisions/
│   └── .gitkeep
├── archives/
│   └── .gitkeep
└── README.md
```

## 容量限制

| 层级 | 限制 |
|------|------|
| CLAUDE.md | ≤ 60 行 |
| MEMORY.md 索引 | ≤ 50 条 |
| 单个 Topic 文件 | ≤ 200 行（超过则拆分） |
| Topic 文件总数 | ≤ 50 个 |

## 写入规则

### 学习 Agent（积极记忆）
- 新概念 → knowledge/
- 错题/面试崩 → fixes/ 或 interview/
- 学习偏好 → feedback/
- "记住这个" → 立即写入

### 工作 Agent（克制记忆）
- Bug 3+ 轮才定位 → fixes/
- "以后都这样做" → feedback/
- 架构决策确认 → decisions/
- 其他一律不记

## 健康检查

```bash
python ~/.claude/skills-repo/memory-manager/scripts/memory_health_check.py
```

检查：CLAUDE.md 行数 → MEMORY.md 索引一致性 → Topic 文件容量 → 活跃度（30/60 天）

## 同步

由 `auto_sync_daemon.py` 守护进程自动处理，空闲 5 分钟后自动 push。

## 关联仓库

- **skills-repo**: https://github.com/chu123122/skills-repo.git — Skill 仓库 + 脚本 + 初始化工具
