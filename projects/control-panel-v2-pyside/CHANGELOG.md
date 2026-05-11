# CHANGELOG · control-panel-v2-pyside

> 任务级时间线。全局 `~/.claude/global-memory/CHANGELOG.md` 同步记录跨项目影响项；
> 本文件聚焦本任务内部演进（设计→实现→验收），细到每次源码 mtime 变更。

## [2026-04-27 14:11] R4-a PyInstaller 重打 .exe

- 新建 `~/.claude/global-memory/harness/control_panel_pyside_launch.py` 顶层 wrapper
- 改 `control_panel_pyside.spec`：入口指向 launcher；hiddenimports 显式登记 v2.1 全部子包/widgets（保险）
- 第一次打包成功但 .exe 启动报 `ImportError: attempted relative import with no known parent package` —— 根因：onefile 模式下 `__main__.py` 被当顶级模块加载，包上下文丢失，相对 import 失败
- 加 launcher 走绝对 import 重打，第二次成功：`dist/control_panel_pyside.exe` 52 MB
- 冷启验证（PowerShell Start-Process Hidden）：进程存活 6.88s 无 stderr 无崩
- 唯一 warning（无害）：`Ignoring AppKit.framework/AppKit imported from darkdetect/_mac_detect.py` —— Mac-only ctypes，Windows 跳过

## [2026-04-27] HANDOFF 追平实际进度

- 发现 HANDOFF.md 仍写 "v2.1 R1~R4 待执行"，但源码 mtime（2026-04-24 20:41~20:44）证明 R1~R3.5 已落地。
- 行动：
  - 改 HANDOFF.md 顶部速读 + 阶段标记 → "R1~R3.5 已完成；R4 验收待补 PyInstaller 重打 + 实机肉眼验"
  - "已完成"段补 R1 / R2 / R3 / R3.5 / R4 部分 5 节，每节列出 mtime 与具体改动
  - "下一步"段重写为 R4-a（PyInstaller 重打）+ R4-b（V1~V13 实机肉眼验，列重点项）
  - 新建本 CHANGELOG.md（之前任务目录无）
- 触发：用户提"中控面板那个 GUI 目前如何了"→ 对照源码后发现文档与代码脱节
- 责任：v2.1 R1~R3.5 完成时未当场更新本任务的 HANDOFF/CHANGELOG，违反"记忆写入后立即更新 CHANGELOG"铁律（原代码 mtime 20:44，全局 CHANGELOG 21:10，但任务级文档未跟）

## [2026-04-24 20:41~20:44] v2.1 R1~R3.5 实现完成

源码改动（按 mtime 顺序）：

| 时刻 | 文件 | 动作 |
|---|---|---|
| 20:41:31 | `views/status.py` | R2 新建：GitCard / DaemonCard / DoctorCard + 一键修复按钮（异步 spinner，完成后强制 status 再拉一次） |
| 20:42:15 | `widgets/__init__.py` | R3 新建包 |
| 20:42:26 | `widgets/doc_sidebar.py` | R3 新建：220px 固定宽侧栏 + 6 文档跳转（MEMORY/CHANGELOG/conventions/MAINTENANCE/FIXLIST/CONTROL_PANEL），不存在的灰显 |
| 20:42:41 | `widgets/debug_dock.py` | R3 新建：QToolButton 折叠/展开（28px↔220px），QPlainTextEdit 上限 500 块 |
| 20:43:35 | `main_window.py` | R1+R3.5 重写：3 tab + QSplitter（主区+DocSidebar）+ 底部 DebugDock；删 ConclusionPanel + PollingService wire；保留主题切换+CommandRunner+open_path |
| 20:43:45 | `views/tasks.py` | R3.5 简化：左/右键都 open_path（结论面板已删，长简介看文件本身） |
| 20:44:14 | `views/changelog.py` | R3 新建：正则 `^### \[ts\]` 切条目、QListWidget+QTextBrowser、`_finalize` 闭包修早 return body 字段缺失 bug |

R1 删除（同时段，未单独留 mtime）：
- `views/{ai,events,history,sync,overview,doctor,guard}.py` × 7
- `conclusion_panel.py`

R4 部分验收（同日，全局 CHANGELOG 21:10 条记录）：
- headless smoke：startup 0.07s（v2.0 0.43s）；3 tab + 4 主题切换无 traceback
- polling 5/5 单元测试沿用通过
- **未做**：PyInstaller 重打 .exe；V1~V13 实机肉眼验

## [2026-04-24 20:30] v2.1 范围收窄决策

用户实机使用 v2.0 反馈"主控台复杂了，是为减复杂度引入的"→ 决策 8 tab → 3 tab：
- 删 AI/事件/历史/同步 4 tab；总览/守护/修复 合并到状态页（含一键修复按钮）
- 右侧 ConclusionPanel 整体下线
- 不再依赖 harness-governance-v1 Phase 4-B
- 新增：变更页（读 CHANGELOG.md 倒序 20 条）+ 关键文档常驻侧栏 + 折叠调试区
- 不做：新电脑部署按钮（独立 bootstrap.bat，本任务不实现）

同步更新 4 文档：`需求分析.md / 设计文档.md / SPEC.md / HANDOFF.md`。

## [2026-04-24] v2.0 一次性 Phase 0~5+ 完成

- Phase 0 Spike：PySide6 6.11.0 + pyqtdarktheme-fork 2.3.6 + qtawesome 1.4.2，5/5 全过
- Phase 1~5：包 `~/.claude/global-memory/harness/control_panel_pyside/` 落地（10 view + main_window + theme + cli_invoke + polling + conclusion_panel + tests）
- Phase 5+ 主题：「花と嵐（日式文学）」第 4 套主题，调色与博客 redesign-astro 同源（暖白底 #faf8f5 / 克制赤 #c47b6b / 灰青 #7b9bb5 / 灰绿 #8baa7d），衬线字体栈，状态栏右下角"春の花びらが風に散る"耳语

详情：HANDOFF.md "已完成" 段、全局 CHANGELOG 2026-04-24 19:55 / 18:50 / Phase 0~5+ 各条。
