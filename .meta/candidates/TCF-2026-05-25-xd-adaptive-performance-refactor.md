# Task-Context Fallback Candidate: xd-adaptive-performance-refactor

- recommendation / 建议: `REJECT`
- risk / 风险: `HIGH`
- zero_hit / 空召回: `17`
- short_followup_rate / 短追问比例: `0.7059`
- new_hits / 新命中: `2/3`
- still_empty / 仍为空: `0`
- concrete_pointer_rate / 具体指针比例: `0.0`
- generic_pointer_rate / 泛指针比例: `1.0`
- reason_codes / 原因: `weak_or_risky_simulation`

## Samples / 样本

### NEW_HIT - 这个落地本地文档
- shape / 形态: `short_followup`
- context_chars / 注入字符数: `54`
- default_paths / 默认路径: `-`
- expanded_paths / fallback 路径: `~/.claude/global-memory/docs/task-lifecycle.md`
- trace_top / 最高候选:
  - rank 1 score=2.0 `~/.claude/global-memory/docs/task-lifecycle.md` - kw:concept:task
  - rank 2 score=0.3 `~/.claude/global-memory/feedback/feedback_work_skill_doc_only_tasks.md` - desc-token

### CHANGED - 1 ：任务启动摘要  静默吧，就输出一句当前xx任务已启动。2 卡片只做本地写，不走hook， 3 这是什么？ 4 ok 5 这是什么
- shape / 形态: `task_specific`
- context_chars / 注入字符数: `54`
- default_paths / 默认路径: `~/.claude/global-memory/docs/hook-chain.md`
- expanded_paths / fallback 路径: `~/.claude/global-memory/docs/hook-chain.md, ~/.claude/global-memory/docs/task-lifecycle.md`
- trace_top / 最高候选:
  - rank 1 score=2.0 `~/.claude/global-memory/docs/hook-chain.md` - kw:concept:hook
  - rank 2 score=2.0 `~/.claude/global-memory/docs/task-lifecycle.md` - kw:concept:task
  - rank 3 score=0.3 `~/.claude/global-memory/feedback/feedback_ai_summary_drift.md` - desc-token

### NEW_HIT - 任务 上下文治理 已加载 2 STATUS.md这是什么 3 目前字段是哪些？ 4 ok
- shape / 形态: `short_followup`
- context_chars / 注入字符数: `54`
- default_paths / 默认路径: `-`
- expanded_paths / fallback 路径: `~/.claude/global-memory/docs/task-lifecycle.md`
- trace_top / 最高候选:
  - rank 1 score=2.0 `~/.claude/global-memory/docs/task-lifecycle.md` - kw:concept:task
  - rank 2 score=0.3 `~/.claude/global-memory/feedback/feedback_ai_summary_drift.md` - desc-token
  - rank 3 score=0.3 `~/.claude/global-memory/feedback/feedback_diff_workflow.md` - desc-token
