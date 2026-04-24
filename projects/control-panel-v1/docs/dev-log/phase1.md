# control-panel-v1 · Phase 1 Dev Log

日期：2026-04-24

## 完成内容

- 实现并收尾 AI Harness Desktop V1 主控台。
- 修复左侧页签区域鼠标滚轮支持。
- 补齐 `projects/control-panel-v1/` 下的 work 流程交付文档。
- 增加旧版 workflow 校验所需的 `docs/` 桥接产物。
- V1.1：同步页增加 Git 变更文件明细表，事件页增加结构化事件列表和 level 着色。
- V1.2：右侧默认改成结论面板，原始命令输出折叠；新增模型层和模型测试。

## 验证记录

- `python -B harness\fix_hardcoded_paths.py`
- `python -B harness\smoke_test.py --json`
- `python -B harness\maintain.py doctor --json`
- `python -B harness\maintain.py status --json`
- `python -B harness\maintain.py sync --preview --source gui --json`
- `python -B harness\test_control_panel_model.py`
- `python -B check_health.py --json`
- `python -B -c "import harness.control_panel, harness.maintain, harness.ai_runner, harness.panel_api; print('imports ok')"`

## 已知剩余

- GUI 窗口尚需人工打开做肉眼验收。
- 当前工作区 dirty 是本任务新增/修改文件导致，等待用户决定是否 checkpoint 提交。
