# Architecture Decision Records · harness-governance-v1

> 每个文件记一个架构决策。模板:Michael Nygard 4 段式(背景 / 选项 / 选定 / 后果)。

## 索引

| ADR | 标题 | 状态 | 关联 Phase |
|---|---|---|---|
| [ADR-001](ADR-001-jsonl-over-markdown.md) | JSONL 而非 markdown 作为机器可读载体 | Accepted | 4-A / 4-B / 所有 audit 类 |
| [ADR-002](ADR-002-registry-single-source-of-truth.md) | registry 作为单一数据源 | Accepted | 0 / 1-B / 2-A / 2-B |
| [ADR-003](ADR-003-smoke-test-id-shared-schema.md) | smoke_test_id 作为 RULE_MATRIX 与 smoke 的共享 schema | Accepted | 1-B / 3 |
| [ADR-004](ADR-004-chinese-human-english-ai.md) | 中文人类向 + 英文 AI 派生 | Accepted | 0 |
| [ADR-005](ADR-005-jsonl-append-only-rotation.md) | JSONL append-only + 按大小/行数轮转 | Accepted | 4-A / 所有 audit |
| [ADR-006](ADR-006-change-compat-window-and-split-commits.md) | 变更兼容期 + 拆 commit | Accepted | 0 / 4-A / 所有 schema 变更 |
| [ADR-007](ADR-007-schema-version-field.md) | schema_version 字段兜底 | Accepted | 4-A / 未来 jsonl/registry 演化 |

## 状态枚举

- **Proposed** — 起草中,未被引用
- **Accepted** — 当前有效
- **Superseded by ADR-NNN** — 已被新 ADR 替换,内容保留
- **Deprecated** — 不再使用,无替代

## 写作约定

- 文件名:`ADR-NNN-kebab-case-title.md`,NNN 三位编号,全局递增不复用
- **不删除已 Accepted 的 ADR**,只能 supersede(见 §1.7 治理规则 G3)
- 章节固定:背景 / 候选方案 / 选定 / 后果(优 + 劣 + 风险) / 关联
