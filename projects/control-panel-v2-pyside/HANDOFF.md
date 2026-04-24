# HANDOFF · control-panel-v2-pyside

> 文档类型: HANDOFF（跨对话交接）
> 创建: 2026-04-24
> 当前阶段: implementation / 待 Phase 0 开工

## 30 秒速读

把 v1 Tkinter 重写为 PySide6，仅换 view 层；新增任务总览页。6 大决策已定（PySide6 / 纯代码 widget / PyQtDarkTheme / 按页签拆模块 / lambda+@Slot 混合 / QTimer 轮询），白名单第三方已开放，PyInstaller 打包入正轨。任务实际目录在 `D:/global-memory/projects/control-panel-v2-pyside/`，`D:/ClaudeTasks/active/` 下是 junction。

## 已确定决策

| 决策点 | 选定 | 出处 |
|---|---|---|
| GUI 库 | PySide6（vs Tkinter/CustomTkinter/Web/PyQt6） | 需求 §3 |
| 第三方边界 | 放宽白名单：PyQtDarkTheme / qtawesome / PyInstaller | 需求 §4.2 |
| UI 描述方式 | 纯 Python widget 树（不用 Qt Designer .ui） | 设计 §7.1 |
| 代码组织 | 按页签拆模块（`views/*.py` + `_BasePage` 基类） | 设计 §7.1 |
| 主题 | PyQtDarkTheme + 局部 QSS 微调 | 设计 §7.3 |
| 图标 | qtawesome（字体图标，主题切换需 refresh） | 设计 §7.4 |
| 信号槽 | 混合（同文件 lambda + 跨文件 @Slot） | 设计 §7.2 |
| JSONL 轮询 | QTimer，按通道分频（jsonl 2s / audit 5s / git 10s+QThread） | 设计 §3.1 |
| 任务总览数据源 | `harness_status.py --tasks --json`（不重复造） | 设计 §7.7 |
| 包管理 | requirements.txt + .bat 兜底 pip install | 设计 §8.1 |
| 打包 | PyInstaller --onefile（启动 3-5s 接受） | 设计 §8.2 |

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
  - spike 路径: `D:/global-memory/harness/control_panel_pyside_spike/`（可丢）
- ✅ Phase 1-5 一次性完成（2026-04-24）
  - 包：`D:/global-memory/harness/control_panel_pyside/`（10 个 view + main_window + theme + cli_invoke + polling + conclusion_panel + tests）
  - 启动入口：`D:/global-memory/harness/control_panel_pyside.bat`（pip install + python -m）
  - 打包配置：`D:/global-memory/harness/control_panel_pyside.spec`（PyInstaller onefile）
  - polling 单元测试 5/5 通过：`python -m control_panel_pyside.tests.test_polling`
  - 全链路 headless 烟测：startup 0.43s，8 tab + 2 主题切换无崩
  - E2E：panel_api notify 注入事件 → PollingService offset 0→326 → EventsPage 收到

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

1. **任务路径**：实际目录在 `D:/global-memory/projects/control-panel-v2-pyside/`，`D:/ClaudeTasks/active/` 下是 junction（mklink /J）。所有读写以实际目录为准；junction 删除不影响真实文件。**长期根治需要 harness-governance-v1 修脚本支持 task_paths 回退**。
2. **外部依赖**：账本页（结论面板内）需等 harness-governance-v1 Phase 4-B reader 就绪后接入，不阻塞 Phase 0-2。任务总览页用的 `harness_status.py --tasks --json` 已就绪（Phase 2-A.1）。
3. **JSONL 半行风险**：`panel_api.append_event()` 是裸 append（无锁），polling.py 必须按设计 §3.2 的容错伪代码实现。
4. **qtawesome icon 不会自动随主题反色**，主题切换信号必须连 `_refresh_all_icons`，否则 V10 落空。
5. **REVIEW 5 项 🟢 低风险未处理**（PyQtDarkTheme 维护回退 / PySide6 vs PyQt6 理由 / Nuitka 对比 / V4 字段对照清单 / V1-V7 验收命令补全），implement 期间可顺手补。
6. **v1 §3.2 引用**：v2 文档曾错误引用 v1 §3.2，已修正为准确章节，未来不要回写到 §3.2。
7. **qdarktheme 包改名（设计文档不回改，以本条为准）**：设计 §7.3/§8.1 写的是 `PyQtDarkTheme`，但 PyPI 上 `PyQtDarkTheme` / `pyqtdarktheme` 都停在 0.1.7（仅有 `load_stylesheet`，无 `setup_theme`）。Phase 0 spike 实证须用 fork 包 `pyqtdarktheme-fork` 2.3.6（活跃维护，含 `setup_theme`）。**requirements.txt 写 `pyqtdarktheme-fork>=2.3`**，业务代码 `import qdarktheme` 命名空间不变。备选回退：原包 0.1.7 + `load_stylesheet('dark')` 也已实证可在 Py3.12 跑通（无 distutils 问题），但需多 ~30 行手写主题切换。
8. **qdarktheme 不暴露主题切换信号（设计文档不回改，以本条为准）**：设计 §7.4 假设的"qdarktheme theme-changed 信号"不存在。spike 已验证替代方案：在主窗口定义自定义 `Signal(str)`，调用 `setup_theme()` 后手动 `emit`，订阅方重建 qtawesome 图标。Phase 1 `_BasePage` / 主窗口需照此搭骨架（spike 代码 `__main__.py:23,76-86` 是范本）。

## 下一步

**剩余工作：实机肉眼验收**（用户 1 次开窗能完成）：
1. `D:/global-memory/harness/control_panel_pyside.bat` 双击启动
2. 8 个 tab 各点一遍：
   - **V2**: 每页中央内容鼠标滚轮可滚（特别是事件页 / 任务页）
   - **V5**: 同时验 PgUp / PgDown
   - **V8**: 任务页看 active + archived 卡片是否齐，stage 徽章颜色（discussion=蓝/implementation=绿/unknown=灰）
   - **V9**: 点一个 active 卡片 + 一个 archived 卡片，确认弹文件管理器 + 右侧长简介渲染
   - **V7**: View → 主题 → Light / Dark 切换，UI 立即变色
   - **V10**: 切完主题后 8 个 tab 图标颜色对比度正常（不会黑底黑图标）
3. **V4 字段对照**：和 v1 主控台肉眼对比 7 张同名页，确认无字段缺失

**WSLg 验证**（设计 §7.6）：可选，等真有 Linux 使用场景再做。

**PyInstaller 打包**（V1 真实分发）：
```bat
cd D:/global-memory/harness
pyinstaller control_panel_pyside.spec
:: 产物在 dist/control_panel_pyside.exe
```
预计 80-150MB，3-5s 冷启（设计 §8.2）。

**已知未做**（按 SPEC §4 不做清单）：
- 不删 v1 Tkinter（兼容期共存）
- 不接 HTTP API
- 不写 GUI 自动化测试（model summarize_* pytest 留待需要时补）
- 账本页（结论面板内）等 harness-governance-v1 Phase 4-B reader 就绪后接入

## 相关文件

- 任务文档: `D:/global-memory/projects/control-panel-v2-pyside/`
  - 需求分析.md / 设计文档.md / SPEC.md / HANDOFF.md / REVIEW-2026-04-24-1814.md
- 实现位置: `D:/global-memory/harness/control_panel_pyside/`（待 Phase 1 创建）
- 复用代码: `D:/global-memory/harness/control_panel_model.py` / `panel_api.py`
- 上游 v1: `D:/global-memory/projects/control-panel-v1/` + `D:/global-memory/harness/control_panel.py`
- 并行任务: `D:/global-memory/projects/harness-governance-v1/`（账本 reader 提供方）
