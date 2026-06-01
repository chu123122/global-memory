# 全局记忆索引（指针模式）

> 不在此文件预加载内容。具体记忆按需取：
> - **自动**：UserPromptSubmit 触发 `retrieve_inject.py`，注入 Context Brief（top-5 指针 + HANDOFF 摘要）
> - **手动**：`python ~/.claude/global-memory/harness/scripts/harness_retrieve.py --task <name> --query <text>`
> - **人类查阅全索引**：见同目录 `MEMORY-LEGACY.md`

## 分类入口

- `feedback/`  — 行为纠正（用户告诉过 AI 的偏好与禁忌）
- `knowledge/` — 跨任务知识沉淀
- `fixes/`     — Bug 修复经验
- `decisions/` — 架构 / 工作流决策
- `interview/` — 面试专用
- `procedure/` — 操作 runbook
- `reference/` — 外部资源指针
- `projects/`  — 长期参考项目（非任务）
- `retrospectives/` — 项目复盘
- `tasks/`     — 跨项目任务构想

## 启动协议

- 正式任务：读 `D:/ClaudeTasks/active/<task>/HANDOFF.md` → 核对进度 → 确认动手
- 快速提问（≤3 轮）：直接答，不读记忆
- 任务切换：触发 retrieve 重刷 brief（自动）

## 检索机制

- trigger metadata：每条记忆 frontmatter 含 `trigger.keywords` + `trigger.tags`
- alias 词表：`harness/scripts/triggers_aliases.yaml`（同义词/typo 映射）
- vocab 约束：tags 必须来自 `harness/scripts/triggers_vocab.yaml` 的 `domains` 列表
- 写新记忆：`memory_lint_gate.py` PreToolUse 拦截缺 frontmatter 的写入

## 维护

- 写入规范：`CLAUDE.md` § "记忆文件写入规范"
- 模板：`templates/memory_*.tmpl`
- 自检：`python harness/scripts/harness_memory_lint.py <file>`
- 旧全索引：`MEMORY-LEGACY.md`（仅人类查阅；sync_index.py 不再注入本文件）
