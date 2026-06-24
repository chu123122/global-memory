# style-refs/ — 人类向文档风格参考池

## 用途

用户认可的"理想长相"样例。AI 在写 `REQUIREMENTS.md` / `DESIGN.md` 前必须 Read：

1. `~/.claude/skills/work/HUMAN_DOC_STYLE.md`（风格规则）
2. 本目录下任一样例（取语境最贴近的一份）

## 投放规则

- **何时进**：用户写完一份自己满意的需求/设计文档（"能拿去给同事看"的水准）
- **如何命名**：保留原文件名（含中文/方括号都 OK），便于追溯出处
- **何时退**：发现样例不再符合最新审美 → 用户手动删除并通知 AI 更新 `HUMAN_DOC_STYLE.md`

## 当前样例

| 文件 | 来源任务 | 类型 |
|---|---|---|
| `【需求分析】 XDAdaptivePerformance 插件重构.md` | xd-adaptive-performance-refactor | 需求分析 |
| `【设计文档】XDAdaptivePerformance 插件重构.md` | xd-adaptive-performance-refactor | 设计文档 |
