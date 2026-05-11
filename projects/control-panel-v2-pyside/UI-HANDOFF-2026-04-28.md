# UI 重构交接包 · control-panel-v2-pyside

> 创建：2026-04-28
> 用途：把当前控制面板的 UI 视觉/布局问题交接给独立 AI 处理
> 上游：本会话已完成 A1+A2+A2.5 的数据/逻辑层修复，**剩下纯 UI 美学/布局问题**

---

## 0. 一句话任务

PySide6 桌面控制面板**视觉与布局重构**。用户原话：「目前最主要问题还是 UI 不好看，设计的不好，导致理解难」。逻辑层已干净，只需要改 QSS（theme）+ 重排卡片布局 + 视觉分级。

---

## 1. 项目是什么

`global-memory` 是用户的个人 AI harness（C++ 引擎开发者高翔自用）。控制面板 = 每日打开看一眼系统状况的**桌面 dashboard**，**不是工作流工具**。

- 技术栈：PySide6 + qtawesome + pyqtdarktheme-fork
- 当前版本：v1.3（5 tab：状态 / 健康 / 变更 / 任务 / 诊断）
- 启动：`~/.claude/global-memory/harness/control_panel_pyside.bat`

---

## 2. 已确定的设计原则（不可改，是约束）

| ID | 决策 | 含义 |
|---|---|---|
| **Q5** | 面板使命 = 每日体检报告 + 把握度 surface + 输出闭环可见化 | 5 秒看一眼判断系统好坏 |
| **Q6** | 状态机砍到 4 态 | detected / fixing / fixed / archived |
| **Q7** | 面板**无任何动作按钮**（除「一键修复」+「刷新」） | 用户是观察者；所有状态变更走 CLI |
| - | 不开 HTTP / 不做 GUI 自动化测试 | 桌面单机工具 |
| - | 不引入超白名单第三方 | 仅 PySide6 / qtawesome / pyqtdarktheme-fork / PyInstaller |

**用户角色**：观察者，不是管理者。面板的工作是**告诉他下一步要做什么，他打开终端跑命令**。

---

## 3. 当前截图问题（来自 2026-04-28-14:39 实机验收）

参考截图：`C:/Users/XINDONG/Pictures/Snipaste_2026-04-28_14-39-02.png`

可见的视觉/布局问题（**已经诊断过，逻辑修了；剩下的都是审美问题**）：

| # | 问题 | 类别 |
|---|---|---|
| V1 | 主区所有卡片**同一种黄色边框 + 黄底**，无视觉权重层次 | 视觉风格 |
| V2 | 「一键修复」primary 按钮显示成**灰色边框**，看着像 disabled | QSS bug（primary 样式没生效） |
| V3 | 「当前结论」卡占主区 50% 高度但只放 2 行字，**Git/Daemon/Doctor 卡被挤出屏外**需滚动 | 布局浪费 |
| V4 | 右侧「关键文档」侧栏的 6 个卡片样式与主区**完全一样**，分不出主辅 | 视觉层次 |
| V5 | 调试输出框默认占 1/3 屏（reveal 逻辑已修，但首次启动初始高度可能还要调） | 布局 |
| V6 | 字号几乎全一样，没有 hero 字 vs body 字 vs caption 的层次 | 排印 |
| V7 | "状态" tab 标题栏占 14px padding+10px，重复显示 title + subtitle，浪费一行 | 信息密度 |

---

## 4. 已经修完的部分（不要重复）

### 数据/逻辑层（A1）
- `~/.claude/global-memory/harness/overview_verdict.py` 新建
  - `build_overview_verdict(status_json, doctor_summary, health_signals) -> dict`
  - 4 子系统聚合：Git / Daemon / Doctor / Health，severity max 合并
  - **D1 修复**：函数签名根本不接 timeline，从 API 形状切断 token saver 劫持
- `~/.claude/global-memory/harness/test_overview_verdict.py` 4 测试全过

### View 层重构（A2）
- `views/status.py` 重写：删 timeline 卡 + 5 按钮 + 4 个 helper
- `views/diagnostics.py` 新建：原 timeline + 5 按钮全搬到诊断 tab
- `main_window.py`：TAB_SPEC 加诊断 tab

### 文案/数据格式（A2.5）
- 副标题术语化：`"Git / Daemon / 最近修复一屏速览"` → `"看头条结论 + 下一步即可"`
- 卡内容人话化：
  - `"dirty=True / ahead=0 / behind=0 / 变更 41"` → `"未提交 41 个文件"`
  - `"running=True / processes=1"` → `"运行中（1 个进程）"`
  - `"PASS 6 / WARN 0 / ERROR 0"` → `"6 项全过 · 上次：04-28 14:35"`
- 结论卡 headline 修重复：原 `"注意：Git 41 个未提交变更 · Git 41 个未提交变更 · Daemon ..."` → `"⚠ 41 个未提交变更"`
- "下一步"给具体 CLI：原 `"从终端跑 git/同步流程"` → `"终端跑：python -m harness.maintain sync"`
- main_window 失败 reveal=False：让 page 自管（避免 health runner 合法 returncode=1 把调试区误展开）

---

## 5. 剩下要做（你的任务范围）

### 5.1 必须做
- **QSS 重写**（`theme.py` 加上对应 qss 资源）：
  - 卡片样式分 3 级：结论 hero / 子系统 body / 侧栏弱化
  - primary 按钮真正出彩色高亮（当前在花と嵐主题下完全没生效）
  - 整体配色降低饱和度，避免黄色一锅炖
- **主区布局重排**（`views/status.py:_build_content`）：
  - 结论卡：1 行 hero（≥18pt）+ 1 行 next_action（≤12pt 等宽）
  - Git/Daemon/Doctor/Health 4 张子系统卡 → **横向 4 格小卡**（不是纵向 4 张大卡）
  - Doctor 详情（6 个 check label）改成可展开/收起，默认收起
- **侧栏弱化**（`widgets/doc_sidebar.py`）：
  - 6 个卡片 → 纯 list-item（无边框、缩字号到 12pt、灰色 hover）
  - 或：默认隐藏 + 菜单切换显示，进一步把视觉权重让给主区
- **视觉层次**：
  - 字号 3 级：hero(20pt) / body(13pt) / caption(11pt)
  - 颜色语义：success(绿) / warning(琥珀) / error(红) / info(灰)，不是全黄色

### 5.2 推荐做
- 5 tab → 4 tab：诊断进侧栏抽屉（参考 §6 文档），让主区视线动线更短
- 默认窗口尺寸调整：1180×760 偏宽，主区显示不了 4 卡

### 5.3 不要碰
- model 层（`overview_verdict.py`、`control_panel_model.py`）已收口，逻辑完成
- detector / health runner（`harness/health/`）
- IA 总目标（5 tab 暂保留；4 tab 收敛是后续 B 阶段一起做）
- 不引入超白名单第三方
- 不改任何 view 的业务逻辑（refresh / handle_result 等不动）
- 不改 maintain.py / panel_api.py

---

## 6. 关键文件路径

```
~/.claude/global-memory/harness/
├── overview_verdict.py            # 已完成，不动
├── test_overview_verdict.py       # 已完成，不动
├── control_panel_pyside.bat       # 启动入口
├── control_panel_pyside_launch.py # 启动壳
└── control_panel_pyside/
    ├── __main__.py
    ├── main_window.py             # 5 tab 装配；可调侧栏宽/调试区初始高
    ├── theme.py                   # ⭐ QSS 主入口，本任务核心
    ├── cli_invoke.py              # 不动
    ├── polling.py                 # 不动
    ├── widgets/
    │   ├── doc_sidebar.py         # ⭐ 侧栏弱化目标
    │   ├── debug_dock.py          # 已修 reveal 逻辑；可调初始高
    ├── views/
    │   ├── _base.py               # 标题栏可重排
    │   ├── components.py          # ⭐ section_card 等共用组件
    │   ├── status.py              # ⭐ 主区布局重排目标
    │   ├── health.py              # 视觉同步改
    │   ├── diagnostics.py         # 视觉同步改
    │   ├── changelog.py
    │   ├── tasks.py
    │   └── __init__.py
    └── tests/
        └── test_polling.py        # 不影响
```

---

## 7. 文档参考

| 文件 | 关键章节 | 用途 |
|---|---|---|
| `D:/ClaudeTasks/active/control-panel-v2-pyside/需求分析.md` | §1 面板使命 / §1.2 不解决的问题 / §4.2 第三方白名单 | 边界与原则 |
| `~/.claude/global-memory/projects/control-panel-v2-pyside/UX-REVIEW-2026-04-28.md` | D5（视觉层次）/ D6（侧栏挤压）/ D7（闪烁）/ Proposed Layout 章节 | 旧 UX 审计，部分已落实，部分仍可参考 |
| `D:/ClaudeTasks/active/feedback-loop-v1/设计文档.md` | §7「问题闭环」tab 布局示意 | 后续 B 阶段会替换健康 tab，视觉风格要兼容 |

---

## 8. 推荐工作方式

1. **先实机看**：跑 `control_panel_pyside.bat`，5 tab 都点一遍截图
2. **读 theme.py**：理解现有配色 palette、4 个主题（auto / dark / light / hanaarashi）
3. **出 mockup**：给用户 2-3 套不同风格让他选（可参考 [superdesign](https://github.com/superdesigndev/superdesign) / [awesome-design-md](https://github.com/VoltAgent/awesome-design-md)）
4. **选定后实施**：
   - QSS 重写（theme.py 加 qss 资源）
   - components.py 加新版 section_card
   - status.py / diagnostics.py / health.py 改用新组件
   - doc_sidebar.py 弱化
5. **验**：
   - 4 主题切换无 traceback
   - `python -B harness/smoke_test.py` 全 PASS
   - `python -B harness/test_overview_verdict.py` 4/4 PASS
   - 实机截图与改前对比

---

## 9. 验收标准（用户视角，不是 pixel-perfect）

| # | 验收项 |
|---|---|
| U1 | 启动后 **5 秒内**能看清「现在系统好不好 / 下一步做什么」（无需思考） |
| U2 | 主区视觉层次清晰：结论 hero 字最显眼，Git/Daemon/Doctor/Health 4 卡平等且较小 |
| U3 | 「一键修复」primary 按钮**有真正高亮色**，不再像 disabled |
| U4 | 关键文档侧栏**视觉权重明显低于**主区 |
| U5 | 调试输出区默认折叠到底部一行，不抢视觉 |
| U6 | 4 主题切换全部生效且不报错 |
| U7 | 字号有 hero / body / caption 至少 3 级 |
| U8 | 颜色不再"全黄色一锅炖"，severity 用语义色（绿/琥珀/红/灰）区分 |

---

## 10. 当前完整 build_overview_verdict 输出示例（你不需要改这个，但 view 要按此渲染）

```python
# 输入：dirty 41 + daemon running 1 process + doctor 未跑 + health 未跑
{
  "severity": "warning",                                          # ok | info | warning | error
  "headline": "⚠ 41 个未提交变更",                                  # 主区 hero 显示
  "reason": "Git 41 个未提交变更 · Daemon 运行中（1 进程）· Doctor 未运行 · Health 未运行",  # view 不用拼这个
  "next_action": "终端跑：python -m harness.maintain sync",         # 主区第二行（建议等宽字体）
  "primary_button": None,                                         # Q7：永远 None
  "subsystems": [
    {"name": "Git",    "severity": "warning", "summary": "41 个未提交变更"},
    {"name": "Daemon", "severity": "ok",      "summary": "运行中（1 进程）"},
    {"name": "Doctor", "severity": "info",    "summary": "未运行"},
    {"name": "Health", "severity": "info",    "summary": "未运行"}
  ],
  "last_checked": "2026-04-28T06:42:11+00:00",
  "debug": {"input_has_status": True, "input_has_doctor": False, "input_signal_count": 0}
}
```

view 渲染映射：
- `headline` → 结论卡上行 hero 字
- `next_action` → 结论卡下行（建议等宽，因为含 CLI）
- `subsystems` → 4 张子系统小卡，每张显示 `name`（卡标题）+ `summary`（卡内容）+ severity 颜色边
- `reason` 是给 debug / 序列化用的，view 不直接显示（reason 信息已在 4 卡里）

---

## 11. 当前用户硬约束（不要试图说服他改）

- 用户**不要**面板里加任何"管理 issue 状态"的按钮（Q7 已锁）
- 用户**不要**自动 commit / push（手动 CLI）
- 用户接受花と嵐主题为默认审美方向（日式文学风），但当前实现没体现出风味
- 个人单机工具，**不考虑**多用户/团队/合规

---

## 12. 完成后交回什么

- 改动的代码文件（views/ + theme.py + widgets/）
- 改前/改后截图对比（5 tab 各 1 张）
- 1 段简短说明：选了哪种风格、为什么、跟之前对比的关键变化
- smoke + 单测均通过的证据

不需要写设计文档——本文件就是上下文。
