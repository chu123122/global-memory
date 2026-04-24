# SPEC · control-panel-v1

> 文档类型：验收契约
> 日期：2026-04-24
> Status: implementation

## 1. 目标

把 global-memory 的 harness engineering 维护能力收束成一个稳定 V1 主控台：人类能看状态、预览同步、执行安全修复、管理 daemon、接收外部 AI/脚本事件，并理解所有按钮的副作用边界。

## 2. 交付物

| 输出 | 路径 |
|---|---|
| 主控 CLI | `harness/maintain.py` |
| 中文 GUI | `harness/control_panel.py`、`harness/control_panel.bat` |
| AI adapter | `harness/ai_runner.py` |
| 外部事件 API | `harness/panel_api.py` |
| 面板数据模型 | `harness/control_panel_model.py`、`harness/test_control_panel_model.py` |
| GUI 使用说明 | `CONTROL_PANEL.md` |
| 维护说明 | `README.md`、`MAINTENANCE.md` |
| 任务文档 | `projects/control-panel-v1/*.md` |

## 3. 验收清单

- [x] `maintain.py status --json` 可输出快速只读状态。
- [x] `maintain.py sync --preview --json` 可输出 checkpoint 候选摘要。
- [x] `status` 和 `sync --preview` 前后 `git status --short` 不变。
- [x] GUI 为中文界面，含总览、修复、同步、守护、AI、事件、历史页签。
- [x] GUI 左侧页签内容支持 scrollbar 和鼠标滚轮。
- [x] GUI 每 10 秒静默刷新快速状态。
- [x] GUI 每 2 秒读取外部事件日志。
- [x] `panel_api.py notify` 可让 AI/脚本写入面板事件。
- [x] 同步页展示 Git 变更文件明细，不只显示分组摘要。
- [x] 事件页展示最近事件列表，并按 level 做颜色区分。
- [x] 右侧默认显示脚本提炼后的结论和关键数据，不默认显示命令行原文。
- [x] 原始命令输出可通过调试开关打开。
- [x] 面板数据提炼逻辑从 Tkinter 中抽到纯函数模型层。
- [x] 面板数据模型有独立测试脚本并纳入 `smoke_test.py`。
- [x] `ai_runner.py --mode execute` 明确拒绝。
- [x] `CONTROL_PANEL.md` 用简单语言说明怎么用面板。
- [x] `README.md` 和 `MAINTENANCE.md` 链接到面板说明。
- [ ] 手动打开 GUI 验收真实滚轮和事件显示。

## 4. 不做事项

- 不引入新的 GUI 框架。
- 不开放 HTTP/WebSocket API。
- 不嵌入交互式终端。
- 不允许 AI 自动执行改仓库。
- 不实现完整任务中心/策略配置。

## 5. 验证命令

```powershell
python -B harness\maintain.py status --json
python -B harness\maintain.py sync --preview --json
python -B harness\panel_api.py notify --source test --level info --title "面板事件测试" --message "panel_api notify works" --json
python -B harness\test_control_panel_model.py
python -B harness\ai_runner.py "test" --provider claude --mode execute --json
python -B harness\maintain.py doctor --json
python -B harness\smoke_test.py --json
python -B bootstrap.py check
python -B check_health.py --json
python -B harness\verify_memory.py
```

## 6. 验收记录

- 2026-04-24：CLI、GUI、事件 API、文档说明均已实现。
- 2026-04-24：自动验证通过；剩余人工验收为 GUI 实机窗口滚轮和事件显示。
- 2026-04-24：V1.1 增强同步页变更文件明细、事件页结构化事件列表和 level 着色。
- 2026-04-24：V1.2 改为默认结论面板，原始命令输出折叠；新增 `control_panel_model.py` 和模型测试。
