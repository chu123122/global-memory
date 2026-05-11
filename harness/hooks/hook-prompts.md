# Hook Prompts

> 集中存放 hook 拦截/警告时注入的提示文案。
> `_prompt_loader.py` 按 `<!-- hook: ID -->` ... `<!-- hook-end -->` 解析。
> 改文案无需改 hook 代码。

---

<!-- hook: large-file/CHANGELOG.md -->
⚠️ **CHANGELOG.md 全文读取已拦截**——此类文件常超 2000 行，全文 Read 浪费大量 token。

**典型结构**：
- `# CHANGELOG · ...`：标题（第 1 行）
- `## YYYY-MM-DD`：日期分段（最新在上）
- `### Added/Changed/Fixed/Removed · <一句标题>`：单条变更

**按需用以下方式之一**：
1. **看最近改了什么** → `Read` 带 `offset=1, limit=200`（取最新一两段）
2. **定位某个日期** → `Grep -nE '^## ' <file>` 列出所有日期行号 → `Read` 带 `offset=<行号>, limit=400`
3. **找某个主题/文件** → `Grep -n '<关键词>' <file>` → 按命中行号精读
4. **统计变更类型** → `Grep -nE '^### (Added|Changed|Fixed|Removed)' <file>`

**确实需要全文** → `Read` 带 `limit=99999`（显式表态后放行）。
<!-- hook-end -->
