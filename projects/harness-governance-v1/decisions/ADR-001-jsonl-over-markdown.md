# ADR-001 · JSONL 而非 markdown 作为机器可读载体

- **状态**:Accepted
- **创建**:2026-04-24
- **关联 Phase**:4-A(任务结果账本)、所有 audit 类 hook、面板事件总线
- **关联横切原则**:DESIGN §1.4 第 1、5 条

## 背景

harness 治理体系需要持续记录"运行证据/任务结果/事件"三类机器可读数据。两种主流载体:

- **markdown 累加**:在 `task-outcome-ledger.md` / `RUN_LOG.md` 等文件追加段落
- **JSONL append**:每条记录一行 JSON,只追加不修改

用户原始诉求里(see REQUIREMENTS §3 缺口 5)曾考虑用 markdown 写"task-outcome-ledger.md"。但当前 memory 已 60/50 超限(REQUIREMENTS §3 缺口 3),markdown 累加会复刻同样的污染问题。

## 候选方案

### A. markdown 累加

每完成一个任务在 `task-outcome-ledger.md` 末尾追加一段:

```markdown
## 2026-04-24 14:30 — harness-governance-v1 Phase 0
- 任务类型:文件名约定迁移
- 完成 / 返工 1 次 / 工具调用 17 次
- 教训:registry 字段顺序影响 fallback 优先级
```

**优**:人类可直接读;markdown 工具链成熟。
**劣**:文件越长越难 grep + load 越慢;有结构但非机器结构(parser 要写正则);跟 memory 一样会膨胀到污染源;无法天然轮转(append 段落不切分)。

### B. JSONL append

```json
{"ts": "2026-04-24T14:30:12Z", "task": "harness-governance-v1", "phase": "0", "type": "doc-only", "outcome": "completed", "rework": 1, "tools": 17, "lesson": "registry 字段顺序影响 fallback 优先级", "schema_version": 1}
```

**优**:每条记录独立、机器结构化、可 stream parse;天然支持按文件大小/行数轮转;reader 用 `last_offset` 增量读 O(1);跟现有 hook audit jsonl 同载体(tool_audit / subagent_audit / control_panel_events 都是 JSONL)。
**劣**:人类直读不方便(需 `jq` 或 reader 渲染);schema 演化要靠 `schema_version` 字段管。

### C. 混合:JSONL 是真值源,markdown 渲染做派生

JSONL 是写入端,reader 渲染成 markdown 报告供人读。
**优**:两全;**劣**:多一个渲染管道,Phase 4-A 范围超载。

## 选定

**B(JSONL append)**。

理由:
- 与现有 `tool_audit.jsonl` / `subagent_audit.jsonl` / `control_panel_events.jsonl` 三条载体形成统一,reader 复用同一套 last_offset 机制
- 避免重蹈 memory 60/50 覆辙,JSONL 天然适合"机器消费 + 人偶尔抽查"场景
- 渲染人类可读视图(C 方案)推迟到 Phase 4-B 做,Phase 4-A 只做写入端,符合 §1.4 第 1 条"创造 > 减损,骨架先行"

## 后果

**优**:
- Phase 4-A 实现极轻量(append 一行 = 5 行 Python)
- 未来度量层(L5)和运行证据层(audit)可以共用 reader 框架
- schema 演化由 ADR + version 字段管,不污染历史数据

**劣**:
- 用户 cat 看到的是 JSON,不直观——靠 control_panel GUI / Phase 4-B reader 渲染弥补
- 调试时需要 `jq` 这类工具

**风险**:
- schema 早期反复改 → 由 ADR-007(待写)的 schema_version 字段兜底
- JSONL 文件膨胀 → 由 ADR-005 的轮转策略兜底

## 关联

- 落实在:Phase 4-A 写入端 / Phase 4-B reader / 所有 audit hook
- 触发本 ADR 的横切原则:DESIGN §1.4 第 1 条
- 后续依赖 ADR:ADR-005(轮转)、ADR-007(schema_version)
