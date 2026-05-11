# Day 4 实机验收清单 · control-panel v1.3

> 创建：2026-04-28
> 用法：双击 `D:/global-memory/harness/control_panel_pyside.bat` 启动后，对照 V1-V19 逐项打勾。
> 任何 ✗ → 反馈给 AI，决定是迭代修还是接受

---

## A · 视觉验收（默认主题：花と嵐）

启动后第一屏不要点任何东西，直接看：

| ID | 检查项 | 通过条件 | ✓ / ✗ |
|---|---|---|---|
| **V1** | 5 秒判断 | 启动后**5 秒内**能说出"现在系统是 ok / warning / error"，不需要思考 | |
| **V2** | hero 字明显 | 结论卡 headline 字号**显著大于**子系统卡内文字（22pt vs 11pt） | |
| **V3** | 衬线字 | 结论卡 headline 是**衬线字**（Shippori Mincho 风格，横平竖直有钩），不是默认黑体 | |
| **V4** | severity 颜色双重编码 | headline 前面有圆点字符（`●` / `⚠` / `✕`），且**字符颜色 + 卡左边线颜色一致**（绿/赭/沉赤） | |
| **V5** | 一键修复按钮高亮 | [一键修复] 按钮是**赭红实心色**（不再灰色边框像 disabled）；hover 时变深 | |
| **V6** | 4 子系统横排 | Git / Daemon / Doctor / Health **同行排 4 张小卡**，不再纵向 4 张挤一列 | |
| **V7** | 子系统左边色 | 每张子系统卡左边有 3px 颜色条（ok 灰绿 / warn 赭 / error 沉赤 / info 灰青） | |
| **V8** | Doctor 详情默认收起 | 主区底部"Doctor 6 项详情 ▸"默认折叠；ok 状态展不开看不到；warning/error 状态自动展开 | |
| **V9** | next_action CLI 高亮 | "下一步：终端跑：python -m harness.maintain sync" 中**命令部分有浅红背景小药丸**且等宽字 | |
| **V10** | 调试区折叠 | 启动后**底部只有一行 `▸ 调试输出`**，不再占 1/3 屏；点击才展开 | |
| **V11** | 侧栏弱化 | 右侧"关键文档"区是**纯文字 list**（无边框、无按钮高亮）；hover 时浅米底；视觉权重明显低于主区 | |
| **V12** | tab 头不重复 | 切到任一 tab，**没有"今日状态"等大字标题再重复一次**（tab 名已显示）；hover tab 看 tooltip 有说明 | |

## B · 交互验收

| ID | 检查项 | 通过条件 | ✓ / ✗ |
|---|---|---|---|
| **V13** | 健康页一致字符 | 切到「健康」tab，signal 列表用 `✕⚠●`（不再 emoji `🔴🟡🔵🟢`） | |
| **V14** | 健康页折叠 ok | 健康页默认只显示警告/严重项；底部"已通过的检查（N）▸"折叠；点开能看 ok 列表 | |
| **V15** | 健康刷新无闪烁 | 在健康页静止 60 秒（自动每 30s 刷新一次），**肉眼不察觉重绘闪烁** | |
| **V16** | 一键修复反馈 | 点[一键修复] → 按钮变"修复中..." + spinner 图标；完成后 Doctor 卡 summary 自动更新 | |
| **V17** | 主题切换 | 视图菜单 → 主题，依次切 auto / dark / light / hanaarashi 各一次，**无 traceback、无空白窗口、tab 图标颜色跟着变** | |

## C · 内容/文案验收

| ID | 检查项 | 通过条件 | ✓ / ✗ |
|---|---|---|---|
| **V18** | 不再有"内部 JSON 字段名" | 状态页所有可见文本不应出现 `dirty=True` / `ahead=0` / `behind=0` / `PASS 6` / `WARNING 0` 这些原始字段 | |
| **V19** | 切到任务页 | 看到"进行中 N 个 · 已归档 N 个"；任务卡片点击能打开任务目录 | |

---

## D · 三态截图对比（强烈建议）

跑出 3 张截图保存到 `D:/ClaudeTasks/active/control-panel-v2-pyside/screenshots/`：

| # | 文件名 | 怎么造场景 |
|---|---|---|
| S1 | `day4-ok.png` | 跑 `cd /d/global-memory && git stash` 让工作树干净 + 跑 maintain.py status，期望 hero 显示绿色"一切正常" |
| S2 | `day4-warning.png` | 当前状态（41 个未提交）就是 warning，截屏 |
| S3 | `day4-error.png` | 跑 `python harness/maintain.py daemon stop` 让 daemon 停掉 → 期望升级到 error |

跑完别忘 `git stash pop` 恢复 WIP 文件。

---

## E · 反馈格式

实机看完，按下面格式给 AI 反馈：

```
✓ 通过：V1 V2 V4 V6 V11 V12 V17
✗ 失败：
  - V3：headline 字看着不像衬线，跟周围字体一样
  - V5：[一键修复] 是赭红了，但 hover 变浅米色（应该变深红）
  - V14：折叠按钮点不动
其他观察：
  - 1280×800 默认窗口在我的 1920×1080 屏上偏小，能不能默认 1440？
```

---

## F · 已知 Day 3 之后剩余的设计债（B 阶段处理，本期不做）

- 5 tab → 4 tab：诊断进侧栏抽屉（让主区视线动线更短）
- 健康页 signal 加修复按钮（需先扩 Signal schema 加 `fix_action` 字段）
- 子系统 cell 点击展开详情（需 issue_tracker 上下文）
- whisper 状态栏俳句按 severity 切换文案（`春の花びらが風に散る` / `風雲急を告げる` / `嵐が来る`）

这些在 `feedback-loop-v1/设计文档.md §9 Phase B` 一起做。

---

## G · 验收完成后

| 选项 | 后续 |
|---|---|
| 全 ✓ 或 1-2 个 ✗ 不影响使用 | 进入 **Phase B**：feedback-loop-v1 主体（issue_tracker.py + 「问题闭环」tab 替换健康 tab，~5 天） |
| 多个 ✗ 或新发现严重问题 | 反馈给 AI 迭代 Day 4.5 修复 |
| 完全不能用 | 回退到 v1.2（Day1 之前的 commit），重新评估方案 |
