# ADR-007 · schema_version 字段兜底

- **状态**:Accepted
- **创建**:2026-04-24
- **关联 Phase**:4-A(JSONL schema)、未来所有 jsonl/registry 演化
- **关联横切原则**:DESIGN §1.4 第 7 条

## 背景

`task_outcomes.jsonl` 和 `project_registry.json` 的 schema 必然随实战演化(加字段、改字段含义)。如果不带版本标识,reader 在面对历史数据时会:

- 把缺失字段当成"未发生"(可能误统计)
- 把改语义的字段按新语义解读(可能错误归因)
- 升级 reader 后无法回滚(老 reader 读不懂新数据)

## 候选方案

### A. 不带版本字段

**优**:schema 简单。
**劣**:演化时所有 reader 都要改,且历史数据无法重读;无法新旧 reader 共存。

### B. `schema_version` 整型字段(本 ADR 选定)

JSONL 每行带 `"schema_version": N`(N 从 1 开始递增);registry 顶层带 `"schema_version": N`。reader 按 version 分支处理。

**优**:简单;reader 显式声明支持的 version 范围;新 reader 可读老数据,老 reader 看到 newer version 主动 abort 而非 silent 错读。
**劣**:每行/每文件多一个字段(JSONL 每行多 18 byte);bump version 时 reader 需要写 migration code。

### C. SemVer(`"schema_version": "1.2.3"`)

**优**:支持 major/minor/patch 区分。
**劣**:对 JSONL 这种简单结构是过度设计;reader 解析复杂;我们没有"只改 patch 不动 reader"的真实场景。

## 选定

**B(整型)**。

理由:
- 简单是最大优势;account ledger 这种结构不需要 SemVer 的语义
- 老 reader 看到 `schema_version > 自己支持` → 主动 abort,silent 错误的概率降到 0
- bump 触发条件明确:只要加必填字段、改字段语义、删字段——其他改动(加可选字段)不需 bump

## 后果

**优**:
- 历史数据不再是不可读的化石
- 新 reader 可以做多 version 兼容(`if schema_version == 1: ... elif schema_version == 2: ...`)
- 升级失败可回退老 reader,不丢数据

**劣**:
- JSONL 每行多 18 byte(`,"schema_version":1`),账本场景每年顶多 100 行,可忽略
- 每次 bump 要写 migration code 或 reader 兼容分支

**风险**:
- 忘了 bump → reader silently 错读 → 由 Phase 2-B 漂移扫描加规则:**所有 jsonl 写入端必须显式带 schema_version;reader 必须有 fallback 分支**
- bump 频率失控(每改一个字段就 bump)→ ADR 内文规定:**只有破坏性改动才 bump**(加必填、改语义、删字段);加可选字段不 bump

## 关联

- 落实在:Phase 4-A schema(`task_outcomes.jsonl` 每行带 `schema_version: 1`)、Phase 4-B reader(按 version 分支)
- 未来扩展:registry.json 也加 `schema_version` 顶层字段(本期不做)
- 与 ADR-006 互补:ADR-006 管"约定切换",ADR-007 管"schema 字段演化"
- 触发本 ADR 的横切原则:DESIGN §1.4 第 7 条
