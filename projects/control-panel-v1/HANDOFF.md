# control-panel-v1 · HANDOFF

> 最后更新：2026-04-24
> 当前状态：V1.2 已实现，剩余 GUI 实机手动验收和提交/push。
> 仓库：当前 `global-memory` 工作区根目录

## 30 秒速读

本任务把 global-memory 的 harness engineering 维护工具做成了一个中文 Tkinter 主控台。当前 CLI、GUI、外部事件 API、AI 安全边界和说明文档都已落地；V1.2 把右侧默认视图改成“脚本提炼后的结论 + 下一步 + 关键数据”，命令行原文默认折叠。剩下主要是打开 GUI 做肉眼验收，然后决定是否 checkpoint 提交推送。

## 已确定决策

| 决策 | 内容 | 原因 |
|---|---|---|
| V1 使用 Tkinter | 不引入 PySide/Web/FastAPI | 当前环境无额外依赖，稳定优先。 |
| 主控 CLI 统一入口 | GUI 只调用 `maintain.py` 和 `ai_runner.py` | 避免 GUI 复制底层脚本逻辑。 |
| 外部 API 先用 JSONL | `panel_api.py notify` 写 `~/.claude/logs/control_panel_events.jsonl` | 无端口、无服务、AI/脚本都能调用。 |
| AI 不自动执行 | `execute` 模式明确拒绝 | 防止 AI 绕过人类确认修改仓库。 |
| README 保持轻量 | 详细说明放 `CONTROL_PANEL.md` 和 `MAINTENANCE.md` | 避免 README 重新变成杂烩。 |

## 已完成

- 新增 `harness/maintain.py` 主控 CLI。
- 新增 `harness/control_panel.py` 中文 GUI。
- 新增 `harness/control_panel.bat` 启动入口。
- 新增 `harness/ai_runner.py` AI adapter。
- 新增 `harness/panel_api.py` 本地事件 API。
- Stop hook 和 daemon 已委托 `maintain.py sync`。
- `smoke_test.py` 已改成只读冒烟。
- README、MAINTENANCE、CONTROL_PANEL 已更新。
- 本任务文档已放到 `projects/control-panel-v1/`。
- 同步页已有 Git 变更文件明细表。
- 事件页已有最近事件列表，并按 level 着色。
- 右侧默认展示结论面板，原始命令输出通过调试开关查看。
- 新增 `control_panel_model.py` 和 `test_control_panel_model.py`，模型测试已纳入 smoke。

## 当前验证结果

已跑过：

- `python -B harness\maintain.py doctor --json`：通过，唯一 warning 是当前工作区 dirty。
- `python -B harness\smoke_test.py --json`：`25 PASS / 0 WARN / 0 FAIL / 3 SKIP`。
- `python -B bootstrap.py check`：全绿。
- `python -B check_health.py --json`：`0 errors / 0 warnings`。
- `python -B harness\verify_memory.py`：`12 PASS / 1 WARNING / 0 ERROR`，warning 是文件数超过上限。
- `python -B harness\panel_api.py notify ... --json`：可写事件。
- `python -B harness\test_control_panel_model.py`：模型测试通过。

## 已知注意事项

1. GUI 尚未在当前回合启动窗口做肉眼验收。
2. `panel_api.py notify` 的测试事件写入了用户目录日志，不进入 Git。
3. 当前工作区有多项未提交变更，这是本任务产物，不是测试噪音。
4. `__pycache__` 目录存在但未被 Git 跟踪；不要提交。

## 下一步

1. 用户确认是否打开 `harness\control_panel.bat` 做 GUI 实机验收。
2. 验证左侧页签鼠标滚轮是否正常。
3. 运行一条 `panel_api.py notify`，确认 **事件** 页和右侧输出区同步显示。
4. 验证 **同步** 页能展示变更文件明细。
5. 验证右侧默认不是命令行输出，而是结论/下一步/关键数据。
6. 若 GUI 观感和交互 OK，运行 `python harness\maintain.py sync --preview --json` 预览。
7. 用户确认后再执行 checkpoint 同步或手动 git commit/push。
