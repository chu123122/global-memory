# 记忆写入详细规则

> 位置：~/.claude/global-memory/memory-rules.md（从 skills-repo/_bootstrap/ 同步）
> 用途：CLAUDE.md 的记忆规则补充，按需读取（不是每次对话都加载）
> CLAUDE.md 只保留写入条件摘要，本文件包含完整规则

---

## 写入方式
- **直接用工具修改文件**（不是只声明意图），写入后在回答中简要说明写了什么
- 写入后附 `[MEMORY_WRITTEN]` 标记（见 Agent 配置中的具体格式）

## 写入前去重
- 检查目标文件**最近 20 行**是否有明显重复（不需要全文搜索）
- 不确定时在追加内容前加 `<!-- 可能重复，待清理 -->`
- 月度维护时由 memory_cleanup.sh 统一清理

## CHANGELOG 规则（分级）
- knowledge/ 和 interview/ 的**追加**操作 → **不需要写 CHANGELOG**（高频低风险）
- decisions/、feedback/ 的任何操作 → **必须写 CHANGELOG**（影响全局行为）
- 任何文件的 UPDATE（覆盖已有内容）和 DELETE → **必须写 CHANGELOG**
- 批量操作合并为一条记录

### CHANGELOG 格式
```
### [YYYY-MM-DD HH:MM] [CREATE|UPDATE|DELETE] [文件路径]
- **来源项目**：[项目名]
- **变更内容**：[一句话]
- **原因/案例**：[为什么改]
```

## HANDOFF 归属
- 项目内交接 → `docs/HANDOFF.md`（随项目仓库）
- 跨项目交接 → `~/.claude/handoff/`（本地暂存，用完即删）
