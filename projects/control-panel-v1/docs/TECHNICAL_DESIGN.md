# control-panel-v1 · TECHNICAL DESIGN 桥接文档

> 本文件用于兼容 `harness/verify_workflow.py` 的旧版 `docs/` 产物约定。

权威设计文档在上一层：

- `../DESIGN.md`

核心设计摘要：

- `harness/control_panel.py` 是 Tkinter 中文桌面壳。
- `harness/maintain.py` 是所有维护动作的统一主控入口。
- `harness/panel_api.py` 提供本地 JSONL 事件入口，供 AI/脚本通知面板。
- `harness/ai_runner.py` 只开放诊断和计划，执行模式在 V1 明确拒绝。
- `CONTROL_PANEL.md` 是人类使用说明入口。

