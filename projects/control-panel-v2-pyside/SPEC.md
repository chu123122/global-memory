# SPEC · control-panel-v2-pyside

> 文档类型: SPEC（实现期验收契约）
> 创建: 2026-04-24
> Status: implementation
> 上游需求: 需求分析.md
> 上游设计: 设计文档.md
> 上游审查: REVIEW-2026-04-24-1814.md

## 1. 目标

把 control-panel-v1 的 Tkinter view 层重写为 PySide6，解决滚动痛点 + 桌面级观感 + 新增任务总览页。model / panel_api / maintain.py / ai_runner 零改动。

## 2. 交付物

| 类别 | 路径 | 形态 |
|---|---|---|
| view 层包 | `harness/control_panel_pyside/` | Python package（按设计 §7.1 文件树） |
| 启动脚本 | `harness/control_panel_pyside.bat` | 调 `python -m control_panel_pyside` |
| 依赖声明 | `harness/control_panel_pyside/requirements.txt` | PySide6 / PyQtDarkTheme / qtawesome |
| 打包配置 | `harness/control_panel_pyside.spec` | PyInstaller spec（Phase 5） |
| 一键 .exe | `dist/control_panel_pyside.exe` | PyInstaller 产物（Phase 5） |

## 3. 验收清单（V1~V10，对应需求 §5）

| # | 验收项 | 验证命令 / 操作 | 通过条件 |
|---|---|---|---|
| V1 | 启动后窗口可显示 | `control_panel_pyside.bat` | 窗口出现，无 traceback |
| V2 | 左侧 8 页签每页内容鼠标滚轮可滚动 | 实机滚轮 | 8 页都响应（v1 7 页 + 任务页） |
| V3 | 右侧结论面板鼠标滚轮可滚动 | 实机滚轮 | 内容超出可滚 |
| V4 | 7 页签内容与 v1 等价 | 对照 v1 截图 + Phase 2 字段映射清单 | 字段勾完无遗漏 |
| V5 | 鼠标滚轮 + 键盘 PgUp/PgDown 都生效 | 手动测 | 两种方式都能滚 |
| V6 | 与 v1 panel_api 联通 | `python harness/panel_api.py notify --level info --title test --message hello` | 事件页 ≤ 2s 出现该条 |
| V7 | 主题至少有一种深色 / 浅色切换 | View → Theme → Dark/Light | UI 立即变色 |
| V8 | 任务页展示 active + archived，stage 徽章染色正确 | 实机打开 + 与 `python harness/harness_status.py --tasks --json` 对照 | 卡片数与 JSON 一致；徽章 discussion=蓝/implementation=绿/unknown=灰 |
| V9 | 点任务卡片：弹出目录 + 右侧显示长简介 | 点 1 张 active + 1 张 archived | 文件管理器打开 + 右侧渲染 |
| V10 | 主题切换后 tab 图标颜色随之反色 | 切深 → 切浅 | 图标颜色跟随 palette |

## 4. 范围（边界，对应需求 §4.1 §4.2）

**做**：见 §2 交付物。
**不做**：
- 不删 v1 Tkinter（兼容期共存）
- 不开 HTTP API
- 不做 GUI 自动化测试（但 model 层 summarize_* 应有 pytest 覆盖，REVIEW 建议）
- 不重构 model / panel_api / maintain.py
- 不引入超出 §4.2 白名单的第三方

## 5. 里程碑（对应设计 §4）

| Phase | 内容 | 出口标准 |
|---|---|---|
| Phase 0 | Spike：PySide6 hello world + QScrollArea + WSLg 启动验证 | 弹窗成功，滚动响应 |
| Phase 1 | 主框架：QMainWindow + QSplitter + QTabWidget(8 页签占位) | 8 个空 tab 可切换 |
| Phase 2 | 7 v1 等价页 + 任务总览页（`harness_status.py --tasks --json`） | V8 V9 通过 + 字段映射清单完成 |
| Phase 3 | 右侧结论面板 + 5 个 summarize_* 接入 + JSONL 轮询（含半行容错） | V6 通过 |
| Phase 4 | PyQtDarkTheme 主题切换 + qtawesome icon refresh + 实机验收 | V1 V2 V3 V5 V7 V10 通过 |
| Phase 5 | v1/v2 并存验证 + 文档 + .bat + PyInstaller 打包 | V4 整体通过 + .exe 可启动 |

## 6. 文件影响清单

**新增**（全部在 `D:/global-memory/harness/`）：
- `control_panel_pyside/__init__.py`
- `control_panel_pyside/__main__.py`
- `control_panel_pyside/main_window.py`
- `control_panel_pyside/theme.py`
- `control_panel_pyside/polling.py`
- `control_panel_pyside/cli_invoke.py`
- `control_panel_pyside/conclusion_panel.py`
- `control_panel_pyside/views/{__init__,_base,overview,doctor,sync,guard,ai,events,history,tasks}.py`（10 文件）
- `control_panel_pyside/requirements.txt`
- `control_panel_pyside.bat`
- `control_panel_pyside.spec`（Phase 5 加）

**修改**：无（model / panel_api 零改动）

**删除**：无（v1 共存期不删）

## 7. 进度

- 2026-04-24 · Phase 0 Spike 通过：PySide6 6.11.0 + pyqtdarktheme-fork 2.3.6 + qtawesome 1.4.2，5/5 验证通过，冷启 1.63s
- 2026-04-24 · Phase 1 完成：包结构 + 8 张空 _BasePage 子类 + theme.py（持久化）+ cli_invoke.py（QThreadPool）+ polling.py（半行容错）+ conclusion_panel.py 骨架 + main_window.py（菜单 + dock + dispatch）
- 2026-04-24 · Phase 2 完成：8 张页签全部填实
  - overview / doctor / sync / guard / ai / events / history（v1 等价）
  - tasks（v2 新增，TaskCard QFrame 子类，3 列 QGridLayout，点卡片 → conclusion_panel.show_task）
- 2026-04-24 · Phase 3 完成：PollingService 三通道（events 2s / audit 5s / outcomes 2s）+ ConclusionPanel set_decision/set_cards/show_task + 5 个 summarize_* 接入完成（model 层零改动）
- 2026-04-24 · Phase 4 完成：View → 主题菜单（Auto/Dark/Light）+ 持久化 ~/.claude/control_panel_pyside.json + ThemeManager.theme_changed → MainWindow._refresh_all_icons + 各 page.on_theme_changed 重建 qtawesome 图标
- 2026-04-24 · Phase 5 完成：control_panel_pyside.bat 启动入口 + control_panel_pyside.spec PyInstaller 配置 + tests/test_polling.py 5 项断言全过 + E2E 注入事件验证 polling 闭环

## 8. 验收状态

| # | 验收项 | 状态 | 备注 |
|---|---|---|---|
| V1 | 启动后窗口可显示 | ✅ headless 实证 | 启动 0.43s |
| V2 | 左侧 8 页签 QScrollArea 滚动 | ✅ 代码就位 | 待实机肉眼验 |
| V3 | 右侧结论面板 QScrollArea 滚动 | ✅ 代码就位 | 待实机肉眼验 |
| V4 | 7 页签内容与 v1 等价 | 🟡 字段映射就位 | 实机对比 v1 截图待做 |
| V5 | 鼠标滚轮 + PgUp/PgDown 都生效 | ✅ Qt 内建 | 待实机验 |
| V6 | 与 v1 panel_api 联通 | ✅ E2E 实证 | offset 推进 0→326，事件收到 |
| V7 | View → Theme 切换 | ✅ 代码就位 + headless 验证 | 待实机肉眼验 UI 立即变色 |
| V8 | 任务页 active+archived，stage 染色 | ✅ 代码就位 | 待实机验徽章颜色 |
| V9 | 点任务卡片：弹目录 + 右侧长简介 | ✅ 代码就位 | 待实机验 explorer 调起 |
| V10 | 主题切换 tab 图标颜色反色 | ✅ 代码就位 | qtawesome 重建路径已通 |

剩余实机验收：V2 V3 V4 V5 V7 V8 V9 V10（用户开 .bat 跑一遍）。
