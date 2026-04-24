# SPEC · control-panel-v2-pyside

> 文档类型: SPEC（实现期验收契约）
> 创建: 2026-04-24
> Status: implementation
> 上游需求: 需求分析.md
> 上游设计: 设计文档.md
> 上游审查: REVIEW-2026-04-24-1814.md

## 1. 目标

把 control-panel-v1 的 Tkinter view 层重写为 PySide6，解决滚动痛点 + 桌面级观感 + 新增任务总览页。model / panel_api / maintain.py / ai_runner 零改动。

**v2.1 范围收窄**(2026-04-24,本对话决定):用户实机使用 v2.0 反馈"主控台复杂了,引入它是为了减少复杂度,不是增加"。范围从 8 tab 砍到 3 tab(状态/变更/任务),AI/事件/历史/同步 删除,守护/修复 并入状态页;新增关键文档常驻侧栏 + 调试输出折叠区。详见 §3 V11~V13、§5 v2.1 重构 Phase。

## 2. 交付物

| 类别 | 路径 | 形态 |
|---|---|---|
| view 层包 | `harness/control_panel_pyside/` | Python package（按设计 §7.1 v2.1 文件树） |
| 启动脚本 | `harness/control_panel_pyside.bat` | 调 `python -m control_panel_pyside` |
| 依赖声明 | `harness/control_panel_pyside/requirements.txt` | PySide6 / pyqtdarktheme-fork / qtawesome |
| 打包配置 | `harness/control_panel_pyside.spec` | PyInstaller spec（v2.1 R4 重打） |
| 一键 .exe | `dist/control_panel_pyside.exe` | PyInstaller 产物（v2.1 R4 重打） |

## 3. 验收清单（V1~V13，v2.1 修订，对应需求 §5）

| # | 验收项 | 验证命令 / 操作 | 通过条件 |
|---|---|---|---|
| V1 | 启动后窗口可显示 | `control_panel_pyside.bat` | 窗口出现，无 traceback |
| V2 | **3 页签**（状态/变更/任务）每页内容鼠标滚轮可滚动 | 实机滚轮 | 3 页都响应 |
| V3 | **关键文档侧栏**点击=用默认编辑器打开对应文件 | 点 4 个固定项 + 2 个动态项 | 各打开成功 |
| V4 | **状态页**字段与 v1 总览/守护/修复 3 页合并后等价 | 对照 v1 3 页截图 + R2 字段映射清单 | 字段无遗漏 |
| V5 | 鼠标滚轮 + 键盘 PgUp/PgDown 都生效 | 手动测 | 两种方式都能滚 |
| ~~V6~~ | ~~与 v1 panel_api 联通~~ | — | **删除**（事件页删，无渲染目标） |
| V7 | 主题至少 4 套（Auto/Dark/Light/hanaarashi） | View → 主题 → 切换 | UI 立即变色 |
| V8 | 任务页展示 active + archived，stage 徽章染色正确 | 实机打开 + 与 `python harness/harness_status.py --tasks --json` 对照 | 卡片数与 JSON 一致；徽章 discussion=蓝/implementation=绿/unknown=灰 |
| V9 | 点任务卡片：**仅**弹出系统文件管理器到该任务目录 | 点 1 张 active + 1 张 archived | 各打开成功（不再触发右侧面板） |
| V10 | 主题切换后 tab 图标颜色随之反色 | 切深 → 切浅 | 图标颜色跟随 palette |
| **V11** | **变更页**展示 CHANGELOG.md 倒序最近 20 条；可选中条目看完整段落；[打开完整 CHANGELOG] 按钮可调起编辑器 | 切到变更页 + `head -100 CHANGELOG.md` 比对 | 顶部 20 条字段一致 |
| **V12** | **一键修复**按钮异步跑 `maintain.py --fix`；按钮状态 spinner 反馈；完成后状态页"最近修复"卡片自动刷新 | 点按钮 + 看状态变化 | 不卡 UI；完成后卡片更新 |
| **V13** | **调试输出区**默认折叠（顶部一行 `▸ 调试输出`），可手动展开 | 启动后看默认状态 + 点展开 | 默认折叠；展开后能看到 CLI 输出 |

## 4. 范围（边界，对应需求 §4.1 §4.2）

**做**：见 §2 交付物。
**不做**：
- 不删 v1 Tkinter（兼容期共存）
- 不开 HTTP API
- 不做 GUI 自动化测试（但 model 层 summarize_* 应有 pytest 覆盖，REVIEW 建议）
- 不重构 model / panel_api / maintain.py
- 不引入超出 §4.2 白名单的第三方

## 5. 里程碑

### 5.1 v2.0 Phase（已完成，2026-04-24，保留作历史）

| Phase | 内容 | 状态 |
|---|---|---|
| Phase 0 | Spike：PySide6 hello world + QScrollArea + WSLg 启动验证 | ✅ |
| Phase 1 | 主框架：QMainWindow + QSplitter + QTabWidget(8 页签占位) | ✅ |
| Phase 2 | 7 v1 等价页 + 任务总览页 | ✅ |
| Phase 3 | 右侧结论面板 + 5 个 summarize_* 接入 + JSONL 轮询 | ✅ |
| Phase 4 | PyQtDarkTheme 主题切换 + qtawesome icon refresh | ✅ |
| Phase 5 | .bat + PyInstaller spec + tests + E2E 注入 | ✅ |
| Phase 5+ | 「花と嵐」第 4 套主题 + 8 view 内联样式清理 | ✅ |

### 5.2 v2.1 重构 Phase（2026-04-24 决策，待执行）

| Phase | 内容 | 出口标准 |
|---|---|---|
| R1 | 删 `views/{ai,events,history,sync,overview,doctor,guard}.py` 7 文件 + `conclusion_panel.py`；`main_window.py` 拆掉 ConclusionPanel + PollingService wire | 启动后窗口只剩 1 tab（任务），无 traceback；headless smoke 仍过 |
| R2 | 新增 `views/status.py`（合并 overview/doctor/guard 字段渲染）+ 一键修复按钮（QThreadPool 跑 `maintain.py --fix`） | V4 + V12 通过 |
| R3 | 新增 `views/changelog.py` + `widgets/doc_sidebar.py` + `widgets/debug_dock.py` | V11 + V3 + V13 通过 |
| R4 | 实机肉眼验 V1~V5 + V7~V13；补 V4 字段对照清单（机器可读 YAML/JSON）；headless smoke 加"启动→切 3 tab→切 4 主题"；PyInstaller 重打 .exe | 全 V 项绿 + .exe 可启动 |

## 6. 文件影响清单

### 6.1 v2.0 已落地文件（保留 / 删除 / 重写）

| 文件 | v2.1 操作 |
|---|---|
| `control_panel_pyside/__init__.py` | 保留 |
| `control_panel_pyside/__main__.py` | 保留 |
| `control_panel_pyside/main_window.py` | **重写**（拆 ConclusionPanel + 改 3 tab + 加 doc_sidebar + 加 debug_dock） |
| `control_panel_pyside/theme.py` | 保留 |
| `control_panel_pyside/polling.py` | 保留代码（不再被 main_window wire），单元测试保留 |
| `control_panel_pyside/cli_invoke.py` | 保留 |
| `control_panel_pyside/conclusion_panel.py` | **删除** |
| `control_panel_pyside/views/_base.py` | 保留 |
| `control_panel_pyside/views/overview.py` | **删除**（字段挪到 status.py） |
| `control_panel_pyside/views/doctor.py` | **删除**（同上） |
| `control_panel_pyside/views/sync.py` | **删除** |
| `control_panel_pyside/views/guard.py` | **删除**（字段挪到 status.py） |
| `control_panel_pyside/views/ai.py` | **删除** |
| `control_panel_pyside/views/events.py` | **删除** |
| `control_panel_pyside/views/history.py` | **删除** |
| `control_panel_pyside/views/tasks.py` | 保留（点击行为简化为仅打开目录） |
| `control_panel_pyside.bat` | 保留 |
| `control_panel_pyside.spec` | 重打 .exe 时刷新 hiddenimports |
| `control_panel_pyside/requirements.txt` | 保留（依赖未变） |

### 6.2 v2.1 新增文件

- `control_panel_pyside/views/status.py`（合并 overview/doctor/guard）
- `control_panel_pyside/views/changelog.py`
- `control_panel_pyside/widgets/__init__.py`
- `control_panel_pyside/widgets/doc_sidebar.py`
- `control_panel_pyside/widgets/debug_dock.py`

### 6.3 model 层 / panel_api / maintain.py

**零改动**——v2.1 范围收窄是 view 层独立重构。

## 7. 进度

### v2.0（已完成）

- 2026-04-24 · Phase 0 Spike 通过：PySide6 6.11.0 + pyqtdarktheme-fork 2.3.6 + qtawesome 1.4.2，5/5 验证通过，冷启 1.63s
- 2026-04-24 · Phase 1 完成：包结构 + 8 张空 _BasePage 子类 + theme.py（持久化）+ cli_invoke.py（QThreadPool）+ polling.py（半行容错）+ conclusion_panel.py 骨架 + main_window.py（菜单 + dock + dispatch）
- 2026-04-24 · Phase 2 完成：8 张页签全部填实
  - overview / doctor / sync / guard / ai / events / history（v1 等价）
  - tasks（v2 新增，TaskCard QFrame 子类，3 列 QGridLayout，点卡片 → conclusion_panel.show_task）
- 2026-04-24 · Phase 3 完成：PollingService 三通道（events 2s / audit 5s / outcomes 2s）+ ConclusionPanel set_decision/set_cards/show_task + 5 个已存在的 summarize_* 接入完成（status/doctor/sync_preview/log/event；不含 outcomes/recent_events，model 层零改动）
- 2026-04-24 · Phase 4 完成：View → 主题菜单（Auto/Dark/Light）+ 持久化 ~/.claude/control_panel_pyside.json + ThemeManager.theme_changed → MainWindow._refresh_all_icons + 各 page.on_theme_changed 重建 qtawesome 图标
- 2026-04-24 · Phase 5 完成：control_panel_pyside.bat 启动入口 + control_panel_pyside.spec PyInstaller 配置 + tests/test_polling.py 5 项断言全过 + E2E 注入事件验证 polling 闭环
- 2026-04-24 · Phase 5+ 完成：「花と嵐」第 4 套主题加入 + 8 view 内联 setStyleSheet 清理

### v2.1 收窄（待执行）

- 2026-04-24 · 决策：用户实机使用反馈"主控台复杂了"。8 tab → 3 tab + 1 侧栏 + 1 折叠区，决策见本文档 §1 / 设计 §1 / 需求 §4.1。下一步进入 Phase R1~R4。

## 8. 验收状态（v2.1 修订）

| # | 验收项 | v2.0 状态 | v2.1 状态 | 备注 |
|---|---|---|---|---|
| V1 | 启动后窗口可显示 | ✅ | 待 R4 重验 | 拆 ConclusionPanel 后需重测 |
| V2 | **3 页签**滚动 | n/a | 待 R1~R3 实现 | 原 8 页签 V2 ✅ 作废 |
| V3 | **关键文档侧栏**点击 | n/a | 待 R3 实现 | 原 V3「右侧结论面板滚动」作废 |
| V4 | **状态页**字段与 v1 总览/守护/修复合并等价 | n/a | 待 R2 实现 + R4 字段对照 | 原 V4「7 页签等价」作废 |
| V5 | 鼠标滚轮 + PgUp/PgDown | ✅ | 沿用（Qt 内建不受影响） | 待实机肉眼验 |
| ~~V6~~ | ~~panel_api 联通~~ | ✅ | **删除** | 事件页删后无渲染目标 |
| V7 | 主题切换 4 套 | ✅ | 沿用 | 待实机肉眼验 |
| V8 | 任务页徽章染色 | ✅ | 沿用（仅卡片点击行为简化） | 待实机肉眼验 |
| V9 | 点任务卡片：**仅**弹目录 | ✅（含右侧长简介，本期删除） | 待 R1 简化点击行为 | — |
| V10 | 主题切换 tab 图标反色 | ✅ | 沿用 | 待实机肉眼验 |
| **V11** | 变更页 CHANGELOG 倒序展示 | n/a | 待 R3 实现 | — |
| **V12** | 一键修复按钮异步 + 状态反馈 | n/a | 待 R2 实现 | — |
| **V13** | 调试输出区默认折叠 | n/a | 待 R3 实现 | — |

**剩余工作**：v2.1 R1~R4 全部待执行；R4 完成后用户开 .bat 跑实机验收一遍即可。
