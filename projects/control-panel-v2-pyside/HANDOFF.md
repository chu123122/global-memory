# HANDOFF · control-panel-v2-pyside

> 文档类型: HANDOFF（跨对话交接）
> 创建: 2026-04-24
> 当前阶段: implementation / **v2.1 收窄重构待执行**（v2.0 已交付）

## 30 秒速读

把 v1 Tkinter 重写为 PySide6，仅换 view 层。**v2.0 已一次性 Phase 0~5+ 完成**（8 tab 全部填实 + 「花と嵐」主题 + .exe 打包），但 2026-04-24 用户实机反馈"复杂了，是为减复杂度引入的"。**v2.1 决策范围收窄**：8 tab → 3 tab（状态/变更/任务）+ 1 常驻文档侧栏 + 1 折叠调试区；删 AI/事件/历史/同步；总览/守护/修复 合并到状态页（含一键修复按钮）；右侧 ConclusionPanel 整体下线；不再依赖 harness-governance-v1 Phase 4-B 任何接口。**下一步**：执行 Phase R1~R4（设计 §4.2 / SPEC §5.2）。任务实际目录在 `~/.claude/global-memory/projects/control-panel-v2-pyside/`，`D:/ClaudeTasks/active/` 下是 junction。

## 已确定决策

| 决策点 | 选定 | 出处 |
|---|---|---|
| GUI 库 | PySide6（vs Tkinter/CustomTkinter/Web/PyQt6） | 需求 §3 |
| 第三方边界 | 放宽白名单：pyqtdarktheme-fork / qtawesome / PyInstaller | 需求 §4.2 |
| UI 描述方式 | 纯 Python widget 树（不用 Qt Designer .ui） | 设计 §7.1 |
| 代码组织 | 按页签拆模块（`views/*.py` + `_BasePage` 基类） | 设计 §7.1 |
| 主题 | pyqtdarktheme-fork + 局部 QSS 微调 + 「花と嵐」 4 套 | 设计 §7.3 + Phase 5+ |
| 图标 | qtawesome（字体图标，主题切换需 refresh） | 设计 §7.4 |
| 信号槽 | 混合（同文件 lambda + 跨文件 @Slot） | 设计 §7.2 |
| 轮询 | QTimer + git 10s 异步；events/audit/outcomes 通道 v2.1 删除 | 设计 §3 |
| 任务总览数据源 | `harness_status.py --tasks --json`（不重复造） | 设计 §7.7 |
| 包管理 | requirements.txt + .bat 兜底 pip install | 设计 §8.1 |
| 打包 | PyInstaller --onefile（启动 3-5s 接受） | 设计 §8.2 |
| **v2.1 范围收窄**（2026-04-24） | 8 tab → 3 tab（状态/变更/任务）+ 文档侧栏 + 折叠调试区；ConclusionPanel 下线；不再依赖 harness-governance-v1 Phase 4-B | 需求 §4.1 + 设计 §1 + SPEC §5.2 |
| **新电脑部署** | 不在面板内做按钮，独立 `bootstrap.bat`（本任务不实现） | 需求 §4.2 |

## 已完成

- ✅ 需求分析定稿（含 V1~V10 验收，2026-04-24）
- ✅ 设计文档定稿（§1~§8 全填实，2026-04-24）
- ✅ 设计审查（REVIEW-2026-04-24-1814.md，🟡 CONDITIONAL）
- ✅ 6 项中风险全部修复
- ✅ 路径错位用 junction 临时解决
- ✅ Phase 0 Spike 通过（2026-04-24）
  - PySide6 6.11.0 + pyqtdarktheme-fork 2.3.6 + qtawesome 1.4.2
  - 冷启 1.63s / 暖启 0.52s（含 2× 主题切换）—— 远低于预算 3-5s
  - 窗口/滚轮/暗色/图标/主题切换+图标反色 五项全过
  - spike 路径: `~/.claude/global-memory/harness/control_panel_pyside_spike/`（可丢）
- ✅ Phase 1-5 一次性完成（2026-04-24）
  - 包：`~/.claude/global-memory/harness/control_panel_pyside/`（10 个 view + main_window + theme + cli_invoke + polling + conclusion_panel + tests）
  - 启动入口：`~/.claude/global-memory/harness/control_panel_pyside.bat`（pip install + python -m）
  - 打包配置：`~/.claude/global-memory/harness/control_panel_pyside.spec`（PyInstaller onefile）
  - polling 单元测试 5/5 通过：`python -m control_panel_pyside.tests.test_polling`
  - 全链路 headless 烟测：startup 0.43s，8 tab + 2 主题切换无崩
  - E2E：panel_api notify 注入事件 → PollingService offset 0→326 → EventsPage 收到
- ✅ Phase 5+ 主题扩展：花と嵐（2026-04-24）
  - 第 4 套主题选项「花と嵐（日式文学）」加入 View → 主题菜单
  - 调色与博客 redesign-astro 同源：暖白底 #faf8f5 / 克制赤 #c47b6b / 灰青 #7b9bb5 / 灰绿 #8baa7d
  - 衬线字体栈：Shippori Mincho / Zen Old Mincho / Noto Serif SC（fallback 系统衬线）
  - 状态栏右下角"春の花びらが風に散る"耳语：18% 透明度（其他主题）/ 42%（hanaarashi 主题）
  - QSS 实现技巧：append 到 qdarktheme 的 stylesheet 而不是 replace（避免冲掉 widget 默认样式）
  - 副作用 refactor：清掉 8 个 view 的内联 setStyleSheet（盲点：内联样式覆盖 app QSS），改用 setObjectName + theme.py 的 _base_card_qss 跨主题统一 palette() 引用
  - 4 主题切换 headless 全过，1.50s 切完

## 当前验证结果

Phase 0 Spike 5/5 通过：

| 项 | 结果 |
|---|---|
| 窗口启动 | OK，720×520 |
| 滚轮 | OK，50 行 QLabel 顺滑 |
| 暗色主题 | OK |
| qtawesome 图标渲染 | OK（fa5s.sync / fa5s.adjust） |
| 主题切换 + icon 反色 | OK（custom Signal `theme_changed` 触发 `_refresh_all_icons`） |

启动耗时：冷启 1.63s / 暖启 0.52s。

## 已知注意事项

1. **任务路径**：实际目录在 `~/.claude/global-memory/projects/control-panel-v2-pyside/`，`D:/ClaudeTasks/active/` 下是 junction（mklink /J）。所有读写以实际目录为准；junction 删除不影响真实文件。**长期根治需要 harness-governance-v1 修脚本支持 task_paths 回退**。
2. **~~外部依赖：账本页等 Phase 4-B~~** → **v2.1 已移除该依赖**。账本页删，事件页删，本任务可独立完结。
3. **JSONL 半行风险**：v2.0 polling.py 已按设计 §3.2 实现容错；v2.1 不再 wire（events/audit/outcomes 通道全删），代码保留作以后可能恢复使用。
4. **qtawesome icon 不会自动随主题反色**，主题切换信号必须连 `_refresh_all_icons`，否则 V10 落空。v2.1 R3 重做 main_window 时不要丢这个连线。
5. **REVIEW-2026-04-24-2012 仍未处理项**：(R2.2) polling CRLF 漂移、(R2.3) git status 并发上界、(R4.1) V4 字段对照清单。v2.1 R2/R3/R4 期间顺手处理。
6. **v1 §3.2 引用**：v2 文档曾错误引用 v1 §3.2，已修正为准确章节，未来不要回写到 §3.2。
7. **qdarktheme 包改名**：requirements.txt 必须写 `pyqtdarktheme-fork>=2.3`（PyPI 原包 0.1.7 不含 setup_theme）。业务代码 `import qdarktheme` 命名空间不变。**v2.1 SPEC §6 已对齐**，与 v2.0 设计 §7.3/§8.1 文字仍写 PyQtDarkTheme 不一致——以 SPEC 为准。
8. **qdarktheme 不暴露主题切换信号**：用主窗口定义的自定义 `Signal(str)`，调用 `setup_theme()` 后手动 `emit`。v2.0 spike 范本：`__main__.py:23,76-86`。
9. **「花と嵐」主题 QSS append vs replace（v2.0 Phase 5+ 经验）**：append 到 qdarktheme 的 stylesheet（不 replace），避免冲掉 widget 默认样式。v2.1 R3 加文档侧栏/调试区时新写的 QSS 同样要 append。
10. **view 内不要写 setStyleSheet 内联样式**（v2.0 Phase 5+ 教训）：用 setObjectName + theme.py 的 `_base_card_qss` 跨主题统一 palette() 引用。v2.1 R2/R3 新增的 `views/status.py` / `views/changelog.py` / `widgets/*` 必须遵守。

## 下一步（v2.1 R1~R4，详见 SPEC §5.2 / 设计 §4.2）

1. **R1 删除**：删 `views/{ai,events,history,sync,overview,doctor,guard}.py` × 7 + `conclusion_panel.py`；`main_window.py` 拆 ConclusionPanel + PollingService wire。出口：窗口只剩任务 tab，无 traceback。
2. **R2 合并**：新增 `views/status.py`（合并 overview/doctor/guard 字段）+ 一键修复按钮（QThreadPool 跑 `maintain.py --fix`）。出口：V4 + V12 通过。
3. **R3 新增**：`views/changelog.py` + `widgets/doc_sidebar.py` + `widgets/debug_dock.py`。出口：V11 + V3 + V13 通过。
4. **R4 验收**：实机肉眼验 V1~V5 + V7~V13；补 V4 字段对照清单（YAML/JSON）；headless smoke 加"启动→切 3 tab→切 4 主题"；PyInstaller 重打 .exe。

**实机验收命令**：
```bat
~/.claude/global-memory/harness/control_panel_pyside.bat
```

**PyInstaller 重打**：
```bat
cd ~/.claude/global-memory/harness
pyinstaller control_panel_pyside.spec
```

**已知未做**：
- 不删 v1 Tkinter（兼容期共存）
- 不接 HTTP API
- 不写 GUI 自动化测试
- 不在面板内做"新电脑部署"按钮（独立 bootstrap.bat，本任务不实现）

## 相关文件

- 任务文档: `~/.claude/global-memory/projects/control-panel-v2-pyside/`
  - 需求分析.md / 设计文档.md / SPEC.md / HANDOFF.md / REVIEW-2026-04-24-1814.md
- 实现位置: `~/.claude/global-memory/harness/control_panel_pyside/`（待 Phase 1 创建）
- 复用代码: `~/.claude/global-memory/harness/control_panel_model.py` / `panel_api.py`
- 上游 v1: `~/.claude/global-memory/projects/control-panel-v1/` + `~/.claude/global-memory/harness/control_panel.py`
- 并行任务: `~/.claude/global-memory/projects/harness-governance-v1/`（账本 reader 提供方）
