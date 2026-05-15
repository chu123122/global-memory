# 记忆变更审计日志

> 每次修改 global-memory 中的任何文件时，必须在此追加一条记录。
> 这是审计追踪的唯一来源——不记录就等于没改过。

---

### [2026-05-15] [REFACTOR] harness/ 目录重组
- **来源项目**：harness 1.0.0 收敛重构
- **变更内容**：10 个 verify/smoke 脚本 → harness/verify/；7 个报告脚本 → harness/reporting/；3 个 md2html → harness/md2html/；2 个测试 → harness/tests/；更新 manifest 路径、GUI import、smoke_test MANIFEST
- **原因/案例**：harness/ 根目录 50+ 文件平铺，按四层架构（Rules/Skills/Subagent/Scripts+Utilities）重组

### [2026-05-15] [DELETE] 废弃文件清理
- **来源项目**：harness 1.0.0 收敛重构
- **变更内容**：删除 control_panel.py（旧 Tkinter）、control_panel_model.py、test、spike 目录、memory_cleanup.sh；归档 STATUS_SNAPSHOT.md → archives/、FIXLIST.md → archives/
- **原因/案例**：PySide 版替代 Tkinter；memory_gc.py 完全覆盖 cleanup.sh；快照为历史定点文档

### [2026-05-15] [UPDATE] .gitignore + git rm --cached *.pyc
- **来源项目**：harness 1.0.0 收敛重构
- **变更内容**：清除所有已跟踪 __pycache__/*.pyc 文件（15 个），.gitignore 加 **/.diff/ 规则
- **原因/案例**：pyc 历史产物污染 Git 历史，.diff/ 为 hook 生成目录不应入库

### [2026-05-15] [UPDATE] harness/scripts/work_context_pack.py
- **来源项目**：/work skill 审查重构
- **变更内容**：cwd 在 watched_paths 但无 task 匹配时，输出 INFO 级别 + "no task claims this path, proceed"（原：WARNING + "no active task" 推用户建文档）
- **原因/案例**：Perforce 工程路径在 watched_paths 内但 task_paths 无片段匹配，context pack 误判为新任务

### [2026-05-15] [UPDATE] skills/work/v1/scripts/check_doc_sync.py
- **来源项目**：/work skill 审查重构
- **变更内容**：非 git 项目输出 doc age（天数）+ 超 3 天 warning，替代原 "无法检测" 后直接跳过
- **原因/案例**：Perforce 项目下 git-based sync check 全跳过，输出无实质信息

### [2026-05-15] [UPDATE] skills/work/v1/SKILL.md
- **来源项目**：/work skill 审查重构
- **变更内容**：
  - Step 1: 新增任务分级（轻量/完整），替代原 all-or-nothing 文档流程
  - Step 2: 完整等级用模板，轻量等级自由格式
  - Step 2.5: 关键决策立即落地，普通结论批量落地（原：每条单独 Edit）
  - Step 3: 删除旧路由（Opus禁止Edit/Sonnet写代码/Haiku收尾），改为按耦合度分派（对齐 CLAUDE.md）
- **原因/案例**：审查文档 work-skill-review.md 逐条验证 9 个问题全部实锤

### [2026-05-15] [UPDATE] skills/work/v1/templates/需求分析_模板.md, 设计文档_模板.md
- **来源项目**：/work skill 审查重构
- **变更内容**：中文标题替代英文（Requirements→需求分析, Design→设计文档），删除 `（Why）` 式注释标题，删除 HTML 占位注释，精简章节
- **原因/案例**：模板与 HUMAN_DOC_STYLE.md 直接矛盾（风格规则禁止的写法出现在模板中）

### [2026-05-15] [UPDATE] skills/work/v1/templates/workflow.md
- **来源项目**：/work skill 审查重构
- **变更内容**：标注仅完整等级使用，字段可按需精简，不强制全填
- **原因/案例**：原模板对所有场景强制完整结构，bug 修复/继续任务也要过全套格式

### [2026-05-15] [UPDATE] harness/hooks/doc_gate.py
- **来源项目**：/work skill 审查重构
- **变更内容**：registry sanity check 失败从 deny-all 改为 warn（stderr）+ 继续 per-task 检查
- **原因/案例**：无关 task 配置漂移（如 ue-mcp-integration 死条目）导致 watched_paths 下所有编辑被全局阻断

### [2026-05-15] [UPDATE] ~/.claude/projects/project_registry.json
- **来源项目**：/work skill 审查重构
- **变更内容**：删除 ue-mcp-integration 死条目，为 puerts-ai-prototype 补 task_paths 空数组
- **原因/案例**：配置漂移触发 sanity_check_task_paths 失败，全局阻断编辑

---

### [2026-05-14 14:10] [UPDATE] harness/md2html.py
- **来源项目**：claude harness
- **变更内容**：补 `pre`/`code` CSS 样式——暗色背景、border、padding、monospace 字体
- **原因/案例**：真实文档代码块无背景色区分，与卡片背景混在一起不可读

### [2026-05-14 14:00] [CREATE] harness/md2html.py, md2html_classifier.py, md2html_components.py
- **来源项目**：claude harness 自身
- **变更内容**：新建 md2html v4 三文件架构——规则分类器(11 regex + Haiku 兜底) → 12 种组件渲染器 → 暗色终端风格 HTML 组装。将 需求分析.md / 设计文档.md 转换为 dashboard 风格 HTML（metric cards / priority cards / phase cards / scope grids / risk 对比 / timeline / flow diagram 等）
- **原因/案例**：之前 v1-v3 输出 "跟看 MD 一样"，用户多次反馈不满意。用 open-design 生成参考 HTML 后提炼视觉规范，改为语义分类 + 组件化渲染
- **关联**：skills/work/v1/SKILL.md 同步更新，Implement 步骤自动调用 md2html

### [2026-05-14 14:00] [UPDATE] skills/work/v1/SKILL.md
- **来源项目**：claude harness 自身
- **变更内容**：Implement Step 4 添加 HTML 转换调用（md2html.py 需求分析.md + 设计文档.md）
- **原因/案例**：配合 md2html v4，写完 SPEC/HANDOFF 后自动生成 HTML 预览

### [2026-05-14 14:00] [UPDATE] .gitignore
- **来源项目**：claude harness 自身
- **变更内容**：排除 harness/reference-*.html、.workbuddy/、__pycache__/
- **原因/案例**：reference HTML 仅本地视觉参考（~70KB），不纳入版本管理

---

### [2026-05-13 14:30] [CREATE] tasks/bepinex-generic-multiplayer-framework.md
- **来源项目**：Krokosha666/cas-unk-krokosha-multiplayer-coop 架构分析
- **变更内容**：新建 `tasks/` 类型目录，写入 BepInEx + Harmony + Mono 反射通用联机 Mod 框架构想
- **原因/案例**：分析现有联机 mod 后讨论演化方向，记录三阶段路线 + 可行性边界

### [2026-05-13 14:30] [UPDATE] MEMORY.md
- **来源项目**：global-memory
- **变更内容**：添加 `tasks/` 目录索引入口
- **原因/案例**：新增任务文档类型

---

> **以下为 2026-04-29 ~ 2026-05-12 回填记录**（从 git log 提取有意义 commit，排除 auto-sync 噪音）

### [2026-05-12 17:31] [FIX] statusline MODEL_MAP lookup 修复
- `harness/hooks/statusline.py`：lookup key 从 display_name 改为 model id（修复永远 miss 的 bug）、MAP 移到模块级、补 claude-opus-4-6

### [2026-05-12 17:26] [ADD] statusline model 名称映射
- `harness/hooks/statusline.py`：新增 MODEL_MAP 支持 DeepSeek + Claude 短名显示

### [2026-05-12 17:21] [FIX] maintain.py sync 流程顺序修复
- `harness/maintain.py`：git pull 先跑在干净树上，safe_fix 更新统计后再 commit

### [2026-05-11 19:02] [ADD] CLAUDE.md symlink 自动建立 + 非 Claude 模型兼容
- `agents/CLAUDE.md` + `bootstrap.py`：自动 symlink CLAUDE.md；DeepSeek 等非 Claude 模型跳过 model 参数

### [2026-05-11 18:44] [FIX] statusline Windows 路径 sanitize
- `harness/hooks/statusline.py`：`:` 替换为 `-`，匹配 `C--Users-XINDONG` 目录名

### [2026-05-11 18:40] [FIX] bootstrap 注册 StatusLine 和 SubagentStop hook
- `bootstrap.py`：补注册两个新 hook

### [2026-05-11 18:33] [ADD] token 路由优化 — hooks + statusline
- 新增 `harness/hooks/statusline.py`（消息计数 + 模型名 + 项目 + git 分支）
- 新增 `harness/hooks/subagent_stop_logger.py`（subagent 耗时计算）
- `diff_backup.py` / `diff_show.py` stderr 反馈改进

### [2026-05-11 17:00] [REFACTOR] harness hook 自动发现 + TOPIC_DIRS 去重
- `harness/_lib.py` / `harness_status.py` / `post_task_hook.py` / `verify_memory.py`：扫 hooks/*.py 自动发现；TOPIC_DIRS 单一来源

### [2026-05-11 16:57] [ADD] learn skill + control-panel agents
- 新增 `skills/learn/`、`agents/control-panel-ui-implementer.md`、`agents/control-panel-ux-designer.md`

### [2026-05-11 16:57] [ADD] control-panel-v2 设计文档 + harness governance review
- `projects/control-panel-v2-pyside/`：HANDOFF、CHANGELOG、UI/UX 设计文档、验证 checklist

### [2026-05-11 16:57] [UPDATE] knowledge + feedback + changelog + retrospectives
- UE internals 知识更新；4 条新 feedback；删除 android_apk_build.md；health fix loop 复盘

### [2026-05-11 16:57] [ADD] harness 核心更新 + data-list 一致性检查
- `harness/hooks/` 新增 issue_tracker / overview_verdict / timeline_summary
- `fix_hardcoded_paths.py` 增 data list 一致性检查

### [2026-05-11 16:57] [ADD] control-panel issue loop tab + diagnostics view
- 新增 `views/issue_loop.py`（3 桶布局）、`views/diagnostics.py`
- 主题/组件/状态更新；launcher 脚本

### [2026-05-11 16:45] [FIX] bootstrap skill 列表自动发现
- `bootstrap.py`：扫 REPO/skills/ 的 v1/SKILL.md 目录替代硬编码列表

---

### [2026-04-29 00:xx] [ADD] feedback-loop-v1 D3+D4+D5：「问题闭环」tab 替换健康 tab + stop-hook 自动 ETL
- **来源项目**：feedback-loop-v1（Phase B 第 3-5 天合做）
- **变更内容**：
  - **D3** 新建 `harness/control_panel_pyside/views/issue_loop.py`（~310 行）：
    · `IssueLoopPage(_BasePage)` page_id="issue_loop"，3 桶布局（待你处理 / 自动处理中 / 已处理）
    · 数据源：`issue_tracker._last_record_by_id` + `_last_event_by_id` 直接读 issues.jsonl
    · 视觉：复用 subsystem-cell QSS 体系；severity 双重编码（颜色 + unicode 字符）
    · 每张卡：title + headline + fix_hint + **建议 CLI**（detected/reopened 给 archive 命令；archived 给 reopen 命令）
    · diff 复用 widget（不 deleteLater 重建，无闪烁）
    · Q7 锁：纯只读，无任何动作按钮
  - **D4** `main_window.py` TAB_SPEC 替换：HealthPage → IssueLoopPage（5 tab：状态 / **问题闭环** / 变更 / 任务 / 诊断）
  - **D4** `views/diagnostics.py` 加「跑健康检测」按钮兜底：原 health page 删了，9 项原始 signal 入口移这里，结果 dump 到调试区
  - **D5** `harness/post_task_hook.py` 在 health runner 块后追加 issue_tracker --extract --json 块：每次 stop-hook 自动跑 ETL，输出新增事件按 event 分组（detected/reopened/fixed）
- **验收命中**：V6 ✓（3 桶纯只读，offscreen 实跑 5 active + 1 archived 渲染 OK）/ V7 ✓（HealthPage 已从 TAB_SPEC 删除）/ V8 ✓（post_task_hook 主流程含 ETL 调用）
- **e2e 验证**：4 主题切换无 traceback / 4 issue_tracker 单测 PASS / smoke 26 PASS 0 FAIL
- **Phase B 完成**：feedback-loop-v1 V1 V8 验收全过；用户实机验收后可结项

### [2026-04-28 23:xx] [UPDATE] feedback-loop-v1 D2：4 态转移 + CLI subcmds + 沉淀建议
- **来源项目**：feedback-loop-v1（Phase B 第 2 天）
- **变更内容**：
  - `harness/issue_tracker.py` 增 4 态闭环：
    · ETL 自动 fixed（detector 重跑后 issue_id 不再出现 → append `event: fixed`，V4）
    · ETL 自动 reopened（已 fixed/archived 的 issue_id 又被 health 报告 → append `event: reopened`，state 回 detected）
    · `archive_issue(id, note)` / `reopen_issue(id, note)`：用户 CLI 触发的 transition，actor=user
    · `_make_event(base, event)` helper：从已有 issue 派生新 event，继承 source/severity/title/evidence
  - CLI 重构成 mutually exclusive 互斥组：`--extract` / `--archive ID` / `--reopen ID` / `--list-open`，共享 `--note`
  - V5 沉淀建议：archive 输出 `fixes/{check_id}_{YYYY-MM-DD}.md`（仅 CLI 提示，不写文件）
  - 错误处理：`IssueNotFoundError` / `IssueStateError`（exit code 2）
  - `harness/test_issue_tracker.py` 加 2 单测（auto_fixed_when_disappears + archive_outputs_learning_target）
- **验收命中**：V3 ✓（archive CLI 触发 + 持久化）/ V4 ✓（自动 fixed 单测）/ V5 ✓（实跑 fixes/invocation_freq_2026-04-28.md）
- **实跑**：archive 了 health.invocation_freq.5bd0f44b 一条，open 数 6 → 5
- **下一步**：D3（issue_loop.py UI 骨架，3 桶 + 卡片）

### [2026-04-28 23:xx] [ADD] feedback-loop-v1 D1：issue_tracker.py + test_issue_tracker.py
- **来源项目**：feedback-loop-v1（Phase B 第 1 天）
- **触发**：Phase A（control-panel UI 重构）完成后进入 Phase B 主体——把 health Signal 升级为有状态 Issue 闭环
- **变更内容**：
  - 新建 `harness/issue_tracker.py`（~330 行）：`Issue` dataclass（每行 = 1 次状态变迁，append-only）+ `compute_issue_id(source, check_id, evidence)` 稳定 ID 算法（含 `_strip_volatile()` 去时间戳/N/M 计数/纯数字）+ `extract_from_health()` ETL 主流程（读 health_checks.jsonl 末尾，对 non-ok signal 派生 detected event；用 issues.jsonl 已存在 id 去重）+ CLI `--extract / --json / --dry-run`
  - 新建 `harness/test_issue_tracker.py`（~150 行）：2 单测（id 稳定性 + ETL 提取 5+ check + 第 2 次跑 0 新增 V2 去重）
  - 运行时新增 `~/.claude/logs/issues.jsonl`（首次实跑写入 6 条 detected）
- **验收命中**：V1 ✓（实跑 6 个不同 check 的 issue）/ V2 ✓（连续跑 2 次第 2 次新增 0）
- **关键设计**：
  - source = ETL 来源类型（"health"），不含 check_id，避免 issue_id 双拼
  - issue_id = `{source}.{check_id}.{sha256(canonical)[:8]}`，canonical = evidence 前 3 条去噪音
  - dataclass 用 `field(default_factory=list)` 不会触发 spec_from_file_location 元数据陷阱
- **下一步**：D2（4 态转移 + --archive/--reopen + 沉淀目标建议）
- **文档**：SPEC.md + HANDOFF.md 已写到 `D:/ClaudeTasks/active/feedback-loop-v1/`，Status 转 implementation

### [2026-04-28 22:xx] [REFACTOR] control-panel-v1.3 UI 视觉与布局重构（A1+A2+A2.5+Day1+Day2+Day3）
- **来源项目**：control-panel-v2-pyside / feedback-loop-v1
- **触发**：用户实机验收反馈"目前最主要问题还是 UI 不好看，设计的不好，导致理解难"
- **变更范围**（按阶段，**当场补 changelog 弥补 Day1-3 没及时记**）：
  - **A1**：新建 `harness/overview_verdict.py` + `test_overview_verdict.py`（4 单测）。`build_overview_verdict()` 收口结论卡数据源到 4 真实健康源（Git/Daemon/Doctor/Health）；**函数签名根本不接 timeline → 从 API 形状切断 token saver 子问题对首屏结论卡的劫持（D1 修复）**
  - **A2**：新建 `views/diagnostics.py`，把状态页 `_update_timeline_card` + 5 开发者按钮整段搬走；状态页瘦身回"5 秒看一眼"
  - **A2.5**：4 硬伤——headline 重复 / 调试区 health runner 合法 returncode=1 误展开 / 术语换人话（dirty/ahead/behind/PASS/WARN → 未提交/未推送/远端新提交/通过）/「下一步」给具体可复制 CLI
  - **Day 1（QSS）**：theme.py 修 primary 按钮 `:hover` 选择器特异性问题（QSS 后写覆盖根因）；加 `verdict-hero` / `subsystem-cell` / `doc-sidebar-list` 三级卡片体系；hanaarashi primary 改 accent_aka 红 + Shippori Mincho 衬线 + radius 2px
  - **Day 2（components+status）**：`components.py` 加 `verdict_hero_card()` / `subsystem_cell()` helper；`status.py:_build_content` 重排（hero 卡 + 4 子系统横排 + Doctor 6 项折叠默认收起）
  - **Day 3（其他子页面统一）**：`doc_sidebar.py` 6 按钮 → QListWidget（220→180）；`_base.py` 删 page header（V7 修，subtitle 移 tab tooltip）；`health.py` emoji `🔴🟡🔵🟢` → unicode `✕⚠●` + diff 复用 widget 修闪烁；`tasks.py` 删重复 title；`changelog.py` 不暴露绝对路径；`diagnostics.py` 主按钮提升 primary
- **设计文档**：
  - `D:/ClaudeTasks/active/control-panel-v2-pyside/UI-HANDOFF-2026-04-28.md`（交接包）
  - `D:/ClaudeTasks/active/control-panel-v2-pyside/UI-DESIGN-2026-04-28.md`（ux-designer subagent 方案 B：报纸头条）
- **配合任务**：feedback-loop-v1 V1.3 前置（A=control-panel UX，B=issue_tracker 接入）
- **验证**：4 主题切换无 traceback / smoke 27 PASS 0 FAIL / overview_verdict 4 单测全过
- **教训**：Day 1-3 三天没及时追加 CHANGELOG，违反 CLAUDE.md 铁律"修改 global-memory/ 下任何文件后，**当场**追加 CHANGELOG 记录"。本次一并补齐——下次按文件批改完即记，不攒到对话结束

### [2026-04-28 19:xx] [UPDATE] feedback/feedback_learning_path.md（追加"自学清单模式"）
- **来源项目**：学习模式（XDAdaptivePerformance 学习地图第 2 节后）
- **触发**：第 2 节讲完后用户说"我想直接看源码，要不直接给我点源码推荐我自己看去吧"——连逐节带学都嫌慢
- **变更内容**：feedback 升级为两段式——一段"贴源码线"（讲课时引真代码），一段"自学清单模式"（不讲课了给清单+自检题让用户自学，AI 退到答疑）；定义清单格式标准（路径+行号+看点+自检题）+ 4 种回访接口（贴行号问/测自检/收 knowledge/跳节）
- **触发词**：用户说"给我点源码推荐我自己看"/"直接给清单"/"我自己看" → 切自学模式
- **应用**：所有 /learn 子模式后续教学风格

### [2026-04-28 12:55] [ADD] feedback/feedback_ai_summary_drift.md
- **来源项目**：XDAdaptivePerformance 重构 / Confluence 全树读取 + 红队验证
- **触发**：用户担心 agent 搬迁文档时引入错误（"我基本都不会看，只有 AI 看"），要求建立验证机制
- **变更内容**：建立"AI 摘要文档不可作为 ground truth"协议，覆盖 6 类错误模式（数字反推 / 范畴坍缩 / 总数无源 / 出处张冠李戴 / 拼写漂移 / 未标内部矛盾），强制 L3 业务文档落地前必须重新 fetch 原页 byte-equal 抄录
- **跨项目复用**：本规则不限于 Confluence，所有 AI 跨源摘要场景适用（多文件代码 review / 多 PR 对比 / 多 issue 归类等）
- **配套案例**：`D:/ClaudeTasks/active/xd-adaptive-performance-refactor/_archive/confluence-snapshot-2026-04-28/VERIFICATION-RED-TEAM.md`（5 条抽样、3 条 PARTIAL 实证）

### [2026-04-28 18:xx] [ADD] knowledge/knowledge_ue_internals.md（追加 Module 系统/LoadingPhase 章节）
- **来源项目**：学习模式（XDAdaptivePerformance 学习地图第 1 节）
- **触发**：Q2 答错——LoadingPhase 改 EarliestPossible，用户答"其他游戏依赖它的可能报空"，方向反了（这是太晚的现象）
- **变更内容**：追加 IMPLEMENT_MODULE 真实作用 / LoadingPhase 双向口诀（"太早→我依赖的没就绪；太晚→我的客户已过期"）/ ShutdownModule vs 析构清理边界 / 学习地图入口
- **盲区记录**：LoadingPhase 双向理解错位，已用口诀+表格固化
- **应用范围**：UE 插件开发 / 面试题库

### [2026-04-28 18:xx] [ADD] feedback/feedback_learning_path.md
- **来源项目**：学习模式（/learn）
- **触发**：std::atomic 内存序第 1 节从 store buffer / x86 vs ARM 起讲，用户当场纠正"我们不是应该先围绕引擎源码学习吗，优先关注和当前插件更加相连的部分"
- **变更内容**：新建 feedback_learning_path.md，规则=学习模式必须以项目真代码为线，通用基础就地补最小集，不超出代码 30 行语境
- **应用范围**：所有 /learn 子模式；学习地图 §二（时序图，代码线）和 §五（推荐顺序，知识线）必须融合执行
- **残余风险**：无；下次再起新课时按本 feedback 起点

### [2026-04-28 11:22] [FIX] diff_show hook 避免 Windows 快速闪终端
- **来源项目**：global-memory hooks
- **问题现象**：Claude Code 使用中偶尔连续弹出快速打开/关闭的终端窗口。
- **定位结论**：`~/.claude/settings.json` 中 `PostToolUse Write|Edit` 会触发 `harness/hooks/diff_show.py`；该脚本原来用 `subprocess.Popen('start "" code --diff ...', shell=True)`，在 Windows 上会拉起临时 `cmd` 窗口。AI 连续编辑文件时就会连续闪窗。
- **变更内容**：
  - 改 `harness/hooks/diff_show.py`：新增 `launch_code_diff_hidden()`，Windows 下用 `cmd /d /c code --diff ...` + `CREATE_NO_WINDOW` + stdio DEVNULL 启动 VS Code diff
  - 保留原有 debounce 与 VS Code diff 功能，不改 hook matcher
- **验证**：`python -m compileall harness/hooks/diff_show.py`；伪造 hook input 跑 no-backup 分支 exit=0；`python bootstrap.py check` 全绿
- **残余风险**：所有 hook 命令仍由 Claude Code 通过 `python ...` 调起；如果仍有闪窗，下一步应把高频只写日志类 hook 改成专用隐藏 runner，而不是继续怀疑业务脚本逻辑。

### [2026-04-28] [ADD] /learn skill 学习模式入口（与 /work 对称）
- **来源项目**：claude-system-cleanup（Agent 触发体验改进）
- **变更内容**：
  - 新增 `~/.claude/skills/learn/SKILL.md`（112 行）
  - 触发：用户察觉 learning-agent 没 slash command 入口（只有 work 有 `/work`），靠 Claude 自觉触发"学习模式"判定，今天对话中 Claude 漏判定就翻车
  - 行为：`/learn` → Read `~/.claude/agents/learning-agent.md` 切行为模式 → 读 MEMORY.md + interview_weakness_tracker.md 核对进度 → 按 8 个子模式（C++/UE/渲染/系统设计/面试/算法/简历/个人项目）分流
  - 与 work skill 互斥（同对话不混用，切换 = 新对话）
  - 与 cpp-tutor 关系：cpp-tutor 是话题级 skill，learn 是模式级总入口
- **设计原则**：DRY，不重复 learning-agent.md 内容；skill 只做"激活 + 进度核对 + 子模式分流"
- **生效验证**：写入后 Claude Code 已自动发现并注册到 skill 列表（无需重启）
- **位置纠正**：初版误放 `~/.claude/skills/learn/SKILL.md`（C: 真目录），违反项目约定（所有 skill 真源在 `D:/global-memory/skills/<name>/v1/`，C: 是 junction）。已 mv 到 D: + mklink /J 重建 junction。skill-auditor 重跑 PASS（108 行 ~781 tokens）
- **同步 feedback**：新增 `feedback/feedback_skill_deployment_layout.md` 记录该约定，避免下次踩

### [2026-04-28] [ADD] feedback_no_speculative_semantics_in_comments 不实证就不写"语义"注释
- **来源项目**：xd-adaptive-performance-refactor (4 Monitor 日志梳理审查)
- **变更内容**：
  - 新增 `feedback/feedback_no_speculative_semantics_in_comments.md`
  - 触发：在 `MediaTekPerfMetricsMonitor.cpp:185` 凭印象写注释 "-6=service unavailable on device"，design-reviewer subagent 翻 SDK header 实证发现真实是 -6=UNINITIALIZED, -7=SERVICE_NA
  - 教训：注释里出现"语义/含义/对应/=" 等"语义声明"词时，必须 grep/Read 一手 SDK header 实证，凭印象写就是误导后续诊断
- **同类前科**：之前批 v3 文档"想当然"也是同类错（"我以为/我记得"陷阱）
- **执行规则**：
  - 写注释前自检：句子里有没有 `=` `表示` `对应` `语义` `意思是` `含义` 等词
  - 找不到实证时必须加 `⚠️ 推断` 标记，不能直接写
  - 高风险场景必查：vendor SDK 错误码 / 第三方 API 单位 / 跨平台行为 / 线程模型
- **实证修复**：MediaTekPerfMetricsMonitor.cpp:185 注释已改为完整 EResult enum + SDK header 路径

### [2026-04-27 15:07] [UPDATE] control-panel-v2-pyside 工具闭环与可维护入口
- **来源项目**：control-panel-v2-pyside / token-cost-governance
- **变更内容**：
  - 改 `harness/_lib.py`：新增 `record_tool_invocation()`，写 `~/.claude/logs/harness_tool_invocations.jsonl`
  - 改 `work_context_pack.py` / `audit_skill.py` / `check_prepare.py` / `session_report.py` / `outcomes_reader.py`：脚本启动时记录自运行证据
  - 改 `harness/timeline_summary.py`：区分 `AI tool_audit 直接调用` 与 `脚本自记录调用`，避免把面板/CLI 验证误判为 AI 工作流采用
  - 改状态页：增加"跑 /work pack"、"跑 Skill audit"、"记录 outcome"三个轻入口；顶部结论卡显示下一步
  - 改变更页：新增项目/类型筛选；保留最近 20 条显示，但内部解析 100 条供筛选
  - 新增 `harness/smoke_control_panel_exe.py`：打包 exe 递归启动回归测试，进程数 >2 即 FAIL
- **实测结论**：`work_context_pack.py` / `audit_skill.py` 现在有脚本自运行证据；但 AI 直接调用证据仍为 0，需下一次真实 `/work` / `skill-auditor` 使用后再验证

### [2026-04-27 14:55] [UPDATE] control-panel-v2-pyside 提升状态/变更页可读性
- **来源项目**：control-panel-v2-pyside
- **变更内容**：
  - 改 `harness/control_panel_pyside/views/status.py`：AI 时间线卡片从长文本改为"结论优先 + 表格证据"；明确显示 `/work` 上下文打包、Skill 审计、`/check`、会话报告、outcome ledger 的近 7 天/总计/最近调用和含义
  - 改 `harness/control_panel_pyside/views/changelog.py`：变更页从上下分割改为左右主从阅读；列表两行显示，详情套阅读样式
  - 改 `harness/control_panel_pyside/theme.py`：补 `timeline-reader` 样式，避免时间线证据挤成低可读文本块
- **结论澄清**：此前只是把调用证据接入面板；`work_context_pack.py` / `audit_skill.py` 仍无真实直接调用证据，调用习惯本身尚未解决

### [2026-04-27 14:51] [FIX] control-panel-v2-pyside frozen 命令递归 + 重打 exe
- **来源项目**：control-panel-v2-pyside
- **变更内容**：
  - 改 `harness/control_panel_pyside/main_window.py`：frozen/PyInstaller 环境下 `HARNESS_DIR` 从 `dist` 上一级解析，不再落到 onefile 临时目录
  - 改 `py_cmd` / `py_cmd_repo`：frozen 环境下优先使用 `GLOBAL_MEMORY_PYTHON` / `PYTHON` / 系统 `python` / `py -3` 跑 harness 脚本，不再用 `sys.executable`
  - 重新打包 `harness/dist/control_panel_pyside.exe`
- **根因**：打包后 `sys.executable` 指向 `control_panel_pyside.exe`；状态页自动刷新执行脚本时实际变成"控制面板 exe + maintain.py"，导致 exe 自我递归启动
- **验证**：重打后 6 秒启动 smoke 中进程数稳定为 2（PyInstaller onefile 父/子进程），不再爆发式递归；smoke 后已清理残留进程

### [2026-04-27 14:43] [UPDATE] control-panel-v2-pyside 接入 AI 时间线证据卡
- **来源项目**：control-panel-v2-pyside / token-cost-governance
- **变更内容**：
  - 新增 `harness/timeline_summary.py`：只读汇总 `tool_audit.jsonl` + `task_outcomes.jsonl`，输出最近会话、关键脚本直接调用证据、最近 outcome
  - 改 `harness/control_panel_pyside/views/status.py`：在状态页新增"AI 时间线 / 工具接入证据"卡片；保留 3 tab 结构，不恢复 AI/事件/历史/账本旧页
  - 新增 `harness/tests/test_timeline_summary.py`：覆盖空日志、正常会话、工具调用计数、outcome 读取
- **边界**：只统计 audit 日志里的直接调用；不把 smoke/doctor 间接跑过的脚本算成真实工作流使用；完整会话只输出到 DebugDock
- **触发**：用户追问 `token-cost-governance`、`session_report.py` 是否真实接入默认入口，要求接入控制面板

### [2026-04-27 14:11] [UPDATE] control-panel-v2-pyside R4-a PyInstaller 重打 .exe
- **来源项目**：control-panel-v2-pyside
- **变更内容**：
  - 新建 `harness/control_panel_pyside_launch.py`：顶层 wrapper，绝对 import `control_panel_pyside.__main__:main`
  - 改 `harness/control_panel_pyside.spec`：Analysis 入口换成 launcher；hiddenimports 显式列 v2.1 全部子包/widgets
  - 重打产物 `harness/dist/control_panel_pyside.exe` 52 MB（onefile）
- **根因+修复**：第一次直接打 `__main__.py`，启动报 `ImportError: attempted relative import with no known parent package`（onefile 模式入口被当顶级模块加载，相对 import 失败）→ 加 launcher wrapper 绕开
- **验证**：PowerShell Start-Process Hidden 启动 .exe，进程存活 6.88s，stderr 空，无崩
- **下一步**：R4-b 用户实机肉眼验 V1~V13（双击 .exe 或 .bat 启动）

### [2026-04-27 14:07] [UPDATE] control-panel-v2-pyside HANDOFF 追平实际进度 + 新建任务级 CHANGELOG
- **来源项目**：control-panel-v2-pyside
- **变更内容**：
  - 改 `projects/control-panel-v2-pyside/HANDOFF.md`：顶部速读 + 阶段标记从"R1~R4 待执行"→"R1~R3.5 已完成；R4 待补 PyInstaller 重打 + V1~V13 实机验"；"已完成"段补 R1/R2/R3/R3.5/R4 部分 5 节；"下一步"段重写为 R4-a + R4-b（含重点验收项）
  - 新建 `projects/control-panel-v2-pyside/CHANGELOG.md`：补回 4-24 当日 R1~R3.5 的源码 mtime 时间线 + 4-27 本次追平动作
- **根因**：v2.1 R1~R3.5 完成时（4-24 20:44）只补了全局 CHANGELOG（21:10），任务级 HANDOFF/CHANGELOG 未跟，违反"记忆/任务文档当场更新"铁律
- **触发**：用户提"中控面板那个 GUI 目前如何了"→ 对照 ~/.claude/global-memory/harness/control_panel_pyside/ 源码后发现文档与代码脱节
- **下一步**：用户决策 R4 收尾时机（PyInstaller 重打 + 实机肉眼验 V1~V13）

### [2026-04-24 21:10] [UPDATE] control-panel-v2-pyside v2.1 实现完成（R1~R4）
- **来源项目**：control-panel-v2-pyside
- **变更内容**：
  - R1 删除：`views/{ai,events,history,sync,overview,doctor,guard}.py` × 7 + `conclusion_panel.py`
  - R2 新增：`views/status.py`（合并 v2.0 总览/守护/修复字段：Git 卡 + Daemon 卡 + 最近修复卡 + 一键修复按钮，异步 spinner + 自动刷状态）
  - R3 新增：`views/changelog.py`（读 CHANGELOG.md 倒序前 20 条，QListWidget + QTextBrowser 详情，[打开完整 CHANGELOG] 按钮）+ `widgets/doc_sidebar.py`（6 项常驻文档跳转：MEMORY/CHANGELOG/conventions/MAINTENANCE/FIXLIST/CONTROL_PANEL）+ `widgets/debug_dock.py`（默认折叠的调试输出区，QToolButton 切换 28px↔220px）
  - R3.5 重写 `main_window.py`：3 tab + QSplitter 主区+侧栏 + 底部 DebugDock；删 ConclusionPanel + PollingService wire；保留主题切换 + 命令运行器 + 文件打开
  - 简化 `views/tasks.py`：左/右键都打开任务目录（原右侧长简介渲染删除）
  - 修：`views/changelog.py::_parse_entries` body 字段在早 return 路径未设置 → 改用 `_finalize` 闭包统一 finalize
- **验证**：headless smoke startup=0.07s（v2.0 是 0.43s），3 tab + 4 主题切换无 traceback；polling 5/5 单元测试沿用通过
- **触发**：本对话用户决策"主控台复杂了"→ 8 tab → 3 tab。详见同日 20:30 CHANGELOG 项 + 任务文档 4 份已同步收窄

### [2026-04-24 20:30] [UPDATE] control-panel-v2-pyside v2.1 范围收窄
- **来源项目**：control-panel-v2-pyside（用户实机使用 v2.0 反馈"主控台复杂了"）
- **决策**：8 tab → 3 tab（状态/变更/任务）+ 1 常驻文档侧栏 + 1 折叠调试区
- **删除**：AI/事件/历史/同步 4 个 tab；总览/守护/修复 合并到状态页（含一键修复按钮）；右侧 ConclusionPanel 整体下线；不再依赖 harness-governance-v1 Phase 4-B 任何接口
- **新增**：变更页读 `~/.claude/global-memory/CHANGELOG.md` 倒序 20 条；关键文档常驻侧栏（点击=默认编辑器打开）；调试输出区默认折叠
- **不做**：新电脑部署按钮（独立 bootstrap.bat，本任务不实现）
- **更新文件**：`projects/control-panel-v2-pyside/{需求分析.md, 设计文档.md, SPEC.md, HANDOFF.md}` 4 文档同步收窄
- **触发**：用户原话"我引入它是为减少复杂度，不是增加"。原 8 tab 等于把"打开哪个工具"换成"点哪个 tab"，认知成本未降
- **下一步**：实施 v2.1 Phase R1~R4（详见 SPEC §5.2 / 设计 §4.2）

### [2026-04-24 19:55] [CREATE] Qt/PySide6 样式系统盲区 + 视觉美学偏好
- **来源项目**：control-panel-v2-pyside（PySide6 重写 + 「花と嵐」主题定制）
- **变更内容**：
  - 新增 `knowledge/knowledge_qt_pyside_styling.md`：8 条 PySide6 QSS / palette / qtawesome / QThreadPool 实战盲区
  - 新增 `feedback/feedback_visual_aesthetic.md`：「花と嵐」日式文学性极简定位 + 三件铁律 + 调色板速查
- **触发**：本次任务踩了 setStyleSheet 内联覆盖 app QSS、qdarktheme replace 行为、qtawesome 图标不自动反色、QTextEdit.setMarkdown 等多个 Qt 知识点；且全套调色源于个人博客 redesign-astro 调性，应作为后续个人工具的视觉基线

### [2026-04-24 18:50] [UPDATE] token-cost-governance 首批 token saver 实现
- **来源项目**：token-cost-governance
- **变更内容**：新增 `harness/audit_skill.py`、`harness/work_context_pack.py`、`harness/check_prepare.py`;`maintenance_manifest.json` 增加 `token_savers`;`/work`、`/check`、`skill-auditor` 入口改为优先调用脚本短摘要。
- **配套修复**：`harness_status.py` 默认不再写 `STATUS_SNAPSHOT.md`,仅 `--write-snapshot` 显式落盘;清理 `smoke_test_hooks.py` / `verify_doc_drift.py` 中旧绝对路径硬编码。
- **流程状态**：`projects/token-cost-governance/` 已补 `SPEC.md` / `HANDOFF.md`,两份人类文档 Status 切到 `implementation`。

### [2026-04-24 18:35] [CREATE] token-cost-governance 独立任务文档
- **来源项目**：Token 降耗脚本化讨论
- **变更内容**：新建 `projects/token-cost-governance/需求分析.md` 和 `projects/token-cost-governance/设计文档.md`;同时把 Token 成本治理内容从 `harness-governance-v1` 拆出,避免不同治理目标混在同一任务里。
- **方案摘要**：首批 P0 脚本为 `work_context_pack.py`、`audit_skill.py`、`check_prepare.py`,分别接管 `/work` 上下文打包、Skill 结构审计、`/check` 前置扫描;`review_preflight.py` / `bug_pack.py` / `memory_add.py` 延后。
- **原则**：默认只读、短摘要 ≤120 行、详细结果只走 `--json`/`--verbose`,避免脚本输出反向制造 token 噪音。

### [2026-04-24 18:30] [APPEND] feedback_output_format.md 加"vendor SDK 集成问题先核对 SDK 标准用法"子规则
- **来源项目**：XDAdaptivePerformance QAPE 排查 — 用户给出 qape_sagc_wrapper SDK 资料后真相浮出
- **变更内容**：原 feedback「机制层推断必列候选」之前加 sub-rule #4 — vendor SDK 集成问题排查必须**先**核对 SDK 标准用法 vs plugin 实际用法，再深挖系统层
- **触发原因**：QAPE 排查走 4 轮脑补（manifest → SELinux → MIUI → 描述符），全错。真因是 plugin **没调 SDK 注册入口 `qcom_ega_load(GameID)`** + **hardcode `mGameID = 200001` 参考值**。看 SDK readme + grep plugin 5 分钟就能定位，前 4 轮全跳过这步
- **常见 vendor SDK 集成漏洞**（写进规则）：
  - Hardcode 默认 ID/license 没改成业务真实值
  - 缺 `register/load/init` 注册流程
  - 自己写 wrapper 绕过 SDK 标准 client 类
  - 没拿 vendor 申请的合规白名单
- **应用步骤**：vendor SDK 问题先做 4 步检查（找资料 → grep 调用 → 对比 wrapper → 才深挖系统层）

### [2026-04-24 18:00] [APPEND] feedback_output_format.md 加"机制层推断必须列候选集合"子规则
- **来源项目**：XDAdaptivePerformance MIUI QAPE 排查（用户挑战"vintf manifest 移除你怎么判断的"）
- **变更内容**：原 feedback 文件「事实 vs 推断分层」段后加 sub-rule #3 — 现象推断 vs 机制推断分层。机制推断必须列候选集合 + 给可证伪验证方法 + 不锁定单一假设
- **触发原因**：脑补"MIUI 把 vendor service 从 vintf manifest 移除"被用户挑战，实测后真因是 **SELinux 拒 untrusted_app find vendor service**（avc denied 直证），跟 manifest 完全无关
- **核心模板**：
  ```
  ✅ 事实层（log/cmd 直证）
  🟡 强推断（现象层 — 跨设备一致性 → 系列性问题）
  ❌ 弱推断（机制层 — 列候选集合 + 验证命令，不锁定）
  ```
- **常见易脑补的机制类别**：vintf manifest / SELinux policy / Binder permission / AppsFilter / dlopen 失败 / 参数命名错配 / NDK API level / ABI 错配
- **更新日志同步**：04-24 条目

### [2026-04-24 17:30] [APPEND] fixes_android_apk_build.md 加问题 12 — NDK API 30+ symbol 静态调用导致老设备 dlopen 失败
- **来源项目**：XDAdaptivePerformance Mi 10 (Android 10 / API 29) 实测 — app 启动即闪退
- **变更内容**：`fixes/fixes_android_apk_build.md` 新增「问题 12」 + frontmatter summary 改 11→12 + updated 改 04-24
- **核心**：plugin C++ 直接静态调 NDK API 30+ symbol（如 `AThermal_acquireManager`）即使有运行时 `if (ApiLevel >= 30)` 守护也无效，因为 SO 在 link 阶段强引用 → linker 在 if 之前就检查 symbol → unsatisfied → SO load 失败
- **2 种修法**：weak symbol（推荐 ~5 行）/ dlsym 动态解析（更显式）
- **通用规则**：plugin C++ 凡引用 NDK API ≥ 30 symbol 必须 dlsym/weak 兜底
- **效果预期**：下次撞类似"老 Android 装不上 / `<clinit>` 崩 / UnsatisfiedLinkError"，立刻去看 plugin 是否静态调了 API 30+ symbol

### [2026-04-24 16:30] [APPEND] feedback_work_skill_doc_only_tasks.md 加 /work 触发场景规则
- **来源项目**：XDAdaptivePerformance 长会话末尾用户提问 "轻量 work 是不是该设计 / 压缩后要不要 /work"
- **变更内容**：原 feedback 文件追加新一段「`/work` skill 触发场景规则」，明确：
  - ✅ 应该跑：新会话 / 切项目 / 跨天回来 / **上下文压缩后**
  - ❌ 不该跑：同会话内继续推进 / 微小修补 / 紧接 follow-up
  - 判定一句话：「我现在还需要重新加载全局上下文吗？」在 → 跳，不在 → 跑
  - 不做：不设计"轻量 /work"（over-engineering）/ 不每回合自动跑
- **关键洞察**："效果稳定"的真因是 CLAUDE.md 铁律不是 /work 本身。/work 只是**激活**铁律到上下文，激活后同会话一直生效
- **触发原因**：用户实测今天长会话后半段没跑 /work 质量没掉，识别到重复 /work 是 token 浪费 + 主动问压缩后要不要重跑
- **Frontmatter 同步**：description 改成涵盖触发场景 + 原 task_complete 跳过规则两件事

### [2026-04-24 17:00] [APPEND] feedback_collaboration_meta.md 加 §4 多 Phase 终态架构原则
- **来源项目**:harness-governance-v1 DESIGN 评审
- **变更内容**:`feedback/feedback_collaboration_meta.md` 新增 §4 — 多 Phase 任务必须先建终态架构再渐进式落地详细设计;DESIGN §1 必须包含"终态愿景/数据流/信任边界/横切原则/可观测性/演进路径"6 项;未启动 Phase 不能用"待启动"占位,至少要给"角色+方向+接口+依赖"4 字段
- **触发原因**:用户原话"我希望的是一个大体的规划下先准备好,然后具体情况具体分析,再展开详细的规划。其他的方案可以先不落地,但你得有一个大体的方向"——前轮 DESIGN §1 只画了 Phase 执行依赖图,§3 用"待启动"塞过去
- **章节顺序**:§4 在 §3 之前(后插但逻辑上是更高层规则,做项目时先看)

### [2026-04-24 15:30] [NEW] feedback_collaboration_meta.md 创建
- **来源项目**：harness-governance-v1 讨论阶段
- **变更内容**：新增 `feedback/feedback_collaboration_meta.md`，收纳两条协作元偏好：
  1. **优先级评估必须含"反馈价值"维度**：优先级规则不破，但允许基于"对下游不可逆助力"明确升级低优先级项（如 Phase 4 评估账本因"时间不可逆"应升 P0）。可拆分大 Phase 为"骨架(P0) + 完整版(原 P)"。
  2. **AI 应主动记忆 + 主动回复"已记忆"**：用户给反馈/纠正/元偏好时，当场写 memory 并明确告知用户已落地，不等用户追问。附自检清单。
- **MEMORY.md 同步**：feedback 表新增一行
- **触发原因**：harness-governance-v1 Phase 排序讨论中，用户指出 Phase 4 应基于"反馈价值"提优先级，并要求 AI 后续主动记忆并回复

### [2026-04-24 11:45] [UPDATE] 单仓库合并后 hook/skill/harness 路径修复
- **来源项目**：memory-system-merge 收尾修复
- **变更内容**：修复 `bootstrap.py` / `harness/_lib.py` / `post_task_hook.py` / `auto_sync_daemon.py` / `verify_all.py` / `verify_docs.py` / `verify_memory.py` / `fix_hardcoded_paths.py` 等脚本的旧 `skills-repo` 路径假设，统一以 `global-memory` 单仓库为 active 源。
- **运行配置**：重渲染 `~/.claude/settings.json` hooks，新增 `~/.claude/skills/diff` junction，并重启 `auto_sync_daemon.py`，解决 Stop hook 路径解析错误和 `/diff` skill 未暴露问题。
- **配套修复**：补齐 `feedback_diff_workflow.md` frontmatter，补 4 个 feedback 文件 YAML 字段，补充“每模块改完拉一次编译”的 quick check，更新 README/agents/templates 的当前路径说明，`diff_show.py` 改为读取按 task 隔离的 `.diff/now/` 备份。
- **验证**：`bootstrap.py check`、`check_health.py`、`post_task_hook.py --pre-commit`、`fix_hardcoded_paths.py`、`verify_docs.py` 均通过；`verify_all.py` 0 ERROR。

### [2026-04-24] [APPEND] knowledge_ue_internals.md 加心动 XD 引擎源码精读路线
- **来源项目**：心动多线程资源加载插件预研，源码阅读起步
- **变更内容**：`knowledge/knowledge_ue_internals.md` 末尾新增「心动 XD 引擎源码精读路线」一节 + 更新日志加 2026-04-24 条目
- **配套深度文档**：新建 `D:/docs/engine-source-reading-roadmap.md`（与 `engine-panorama-report.md` 同级，存完整路线图与 Topic 表）
- **Topic 1 已定位**：`FParticleLockFreeMemoryPool`，9 个真实 `#if` 落点，核心实现在 `ParticleMemoryPool.cpp`（616 行），关键 Alloc/Free/PrebuiltBlockSizes 行号已记
- **关键教训**：panorama 的"289 处""84 处"统计**包含 PCH/Intermediate**，不等于真实源码使用次数。`XD_OPT_PARTICLE_INSTANCE_MULTI_THREAD_FILL_DATA` 全 Source 真实零命中可证。**下次定位前必须 grep `Engine/Source/Runtime/` 并排除构建产物**
- **定位规则**：所有 XD 自定义开关在 C# 配置（`Programs/UnrealBuildTool/Configuration/XDBuildConfiguration/`）而非 C++ 头；C# 配置里大多附 Wiki 链接（作者亲笔设计文档）

### [2026-04-23 18:30] [APPEND] feedback_output_format.md 加"修法不奏效时先质疑假设本身"条款
- **来源项目**：XDAdaptivePerformance MAGT verify -8 排查终态复盘
- **变更内容**：`feedback/feedback_output_format.md` 在「事实 vs 推断分层」之后新增条款 — 当假设 A 的修法不奏效时，先质疑假设 A 本身（特别是有限集场景如"用哪个 keystore"，直接列全集逐个试），不要立刻发明新假设
- **触发原因**：今天 MAGT verify -8 真因是 `torchlight.keystore` 不是 `xdaperf.keystore`。从第一次用 xdaperf re-sign 仍 -8 时就该回头质疑 keystore 选错，但我连续跳了 4 个新理论（class 缺失 / AppsFilter / Not Support MAGT / ROM 不支持），绕了 4 小时
- **效果预期**：下次撞类似"改了 X 问题仍在"，先把"X 是不是错的"列为新分支跟其他理论平等对待

### [2026-04-23 17:30] [APPEND] fixes_android_apk_build.md 加问题 11 — Android 11+ AppsFilter 拦 bindService 跨 app
- **来源项目**：XDAdaptivePerformance MAGT 接通 — 真根因终于找到
- **变更内容**：`fixes/fixes_android_apk_build.md` 新增「问题 11」 + 顶部 frontmatter summary 改 10→11 + updated 改 04-23
- **核心**：targetSdk≥30 后跨 app `bindService` 必须在 manifest 加 `<queries>`，否则 AppsFilter 拦截返回 `not found`（容易被误判为"class 缺失"）
- **关键诊断信号**（容易漏看）：`I/AppsFilter: ... <calling_pkg> -> <target_pkg> BLOCKED`
- **UE 项目 UPL 注入修法**：plugin 自己的 UPL 加 `<queries><package name="..."/></queries>`，落点选 plugin UPL 不选项目公共 UPL
- **3 步验证**：APK manifest grep / logcat AppsFilter / dumpsys activity services
- **写下教训**：`dumpsys package <pkg> | grep <Service>` 返回空 ≠ class 不存在；先看 AppsFilter log 再下结论

### [2026-04-23 16:35] [APPEND] feedback_output_format.md 加"事实 vs 推断分层"条款
- **来源项目**：XDAdaptivePerformance MAGT verify -8 排查
- **变更内容**：`feedback/feedback_output_format.md` 在「回答风格」末尾加一条：debug/排查任务必须分开「直接观测的事实（log 直证）」和「推断（基于时间戳/架构脑补）」
- **触发原因**：今天写 HANDOFF TD-15 时把 `bind 失败 → verify=-8` 当成单根因，用户挑战"AppLicenseHubService bind 这个日志在哪里"才发现 PID 1386 vs 984 的因果**没有 stacktrace 直证**，只是时间戳接近+架构联想
- **应用方式**：诊断报告分 3 段 — 事实 / 推断 / 缺口（可证伪步骤）。也写下"我跳过的几个错路径"避免下次再跳

### [2026-04-22 19:20] [APPEND] fixes_android_apk_build.md 加 7 类新坑（问题 4-10）
- **来源项目**：XDAdaptivePerformance Phase 1c 子线程化跨平台验证
- **变更内容**：`fixes/fixes_android_apk_build.md` 在原 3 类问题后追加 7 类新坑：
  - 问题 4：UE Editor 锁住编译输出 dll → LNK1104
  - 问题 5：单 OBB > 4 GiB 触发 stage 失败 + hybrid 拼装绕开方案
  - 问题 6：`adb install -r` 同 versionCode 覆盖装可能让 OBB 被 scoped storage 清（app uid 翻新）
  - 问题 7：Git Bash 下 `cmd //c "X.bat"` 不弹 console 进交互模式 → PowerShell 替代
  - 问题 8：`adb shell cp` 14.7 GB 慢/不稳 → 改用 mv 或直接 push 到目标
  - 问题 9：PSO Precompile + GMS 噪音淹 logcat → `-G 16M` + stream 模式 + 找最后一次 [T0] 起切分
  - 问题 10：MTK MAGT init `-8` (License Check Failed) — APK 签名 cert hash ≠ license 注册的，用 `xdaperf.keystore` (Lingyao Gan 持有) re-sign 而非 `torchlight.keystore`
- frontmatter `summary` 同步更新（10 类问题摘要）；`updated` → 2026-04-22；`source` 加 "Phase 1c 子线程化跨平台验证"
- **原因/案例**：今天跑 K60 + MT6899 真机验证 Phase 1c 子线程化时连撞 7 类坑，全部含具体修复方案。沉淀到 fixes 避免下次回头再踩
- **影响范围**：所有 UE 4 + Android 打包 / 装机 / OBB / MTK MAGT 鉴权场景

### [2026-04-22] [ADD] cpp-weak-token-async-lifetime.md 异步 lifetime 模式深度文档（博客草稿）
- **来源项目**：XDAdaptivePerformance Phase 1c 子线程化（用户提议把这个发现写成文档）
- **变更内容**：
  1. 新增 `knowledge/docs/cpp-weak-token-async-lifetime.md`（约 280 行，12 节）：问题起源 / 三类方案对比（裸 this / 手写 atomic flag / weak token）/ control block 本质 / 为什么需要 token 不直接 weak this / init-capture 语法 / Reset() 时机价值 / 跨语言对照 / UE 内部使用例 / 必须用 vs 可省 / 与 XD 插件的关联 / 4 类踩坑 / 30 秒面试讲法
  2. `knowledge/docs/INDEX.md` "C++ 语言与底层" 分组追加该文档链接
  3. `knowledge/knowledge_cpp_multithreading.md` 新增 "模式与文档" 段，索引该 doc + 一句话核心
- **原因/案例**：XD Phase 1c 实战中用户对 weak token 模式 + init-capture 语法的提问触发深度讲解。用户表示 "之前打算写一篇文档简单聊一下这个发现"，要求落地为文档。该模式跨语言通用（iOS [weak self] / Java WeakReference / Rust Weak<T>），值得作为博客草稿沉淀
- **影响范围**：C++ 多线程 / UE 异步编程 / 面试话术（已附 30 秒讲法）

### [2026-04-21 18:00] [ADD] feedback_diff_workflow + Edit/Write 后自动弹 VS Code diff 弹窗的全局 hook
- **来源项目**：XDAdaptivePerformance 重构（工作流改进副产物）
- **变更内容**：
  1. 新增 `feedback/feedback_diff_workflow.md`：B 协议规则 + 白名单目录定义 + 扩展/禁用方法 + "未来 AI 不要困惑" 现象解释
  2. 新增 `~/.claude/skills-repo/_bootstrap/scripts/hooks/diff_backup.py` (PreToolUse Write|Edit hook)：白名单内文件编辑前备份到 `D:\ClaudeTasks\.diff_backup\<name>.<sha1[:8]>.bak`
  3. 新增 `~/.claude/skills-repo/_bootstrap/scripts/hooks/diff_show.py` (PostToolUse Write|Edit hook)：编辑后异步 `start "" code --diff <bak> <file>` 弹 VS Code 三栏视图，5s 内同文件不重弹（debounce 状态记 `_lastshow.json`）
  4. `~/.claude/settings.json` 注册 hook：PreToolUse Write|Edit 数组追加 diff_backup；新增 PostToolUse Write|Edit 条目调 diff_show
- **白名单**（脚本顶部 WHITELIST 常量，两文件需同步）：
  - `D:\ClaudeTasks\active`（所有任务文档）
  - `C:\Perforce\tl_gaoxinag_01\frontend\trunk\Editor\UE_game\Plugins\XDAdaptivePerformance`（XD 插件源码）
- **原因/案例**：XD 重构期用户反馈 — AI 改完文件后 chat 贴 diff 描述表，用户扫一眼就过、把控感差。要求"修改完自动弹 diff 页面"，全脚本化避免每次 AI 跑命令的 token 消耗。三个决策点：白名单范围 OK / 5s 内不重弹 / 全局加白名单（不是项目级）
- **影响范围**：所有项目的 Edit/Write 行为，但仅白名单目录触发；其他目录无感
- **未来 AI 注意**：看到 VS Code 自动弹 diff 窗口或 `D:\ClaudeTasks\.diff_backup\` 下一堆 .bak 不是 bug，是这套 hook。详见 `feedback/feedback_diff_workflow.md`

### [2026-04-21 14:02] [UPDATE] README / MEMORY 元数据对齐 + 补 3 个 frontmatter
- **来源项目**：通用（记忆仓库整治）
- **变更内容**：
  1. `README.md` 改为当前实现口径：更新目录数量、健康检查入口为 `check_health.py`，并说明自动维护由部署侧 `Stop hook -> post_task_hook.py --auto-fix` 驱动
  2. `knowledge/knowledge_windows_dev_env.md`、`fixes/fixes_android_apk_build.md`、`decisions/decision_work_mode_workflow.md` 补齐 frontmatter（name/description/type/source/updated）
  3. `MEMORY.md` 中上述 3 个条目的描述改为可读版本，避免继续显示英文占位描述
  4. 部署侧 `post_task_hook.py` 的索引检查改为只读取 `MEMORY.md` 的 `AUTO-INDEX` 区块，不再把项目文档 / 系统索引误判成 topic 死链，减少无意义 `auto-fix` 提交
- **原因/案例**：README 仍引用历史脚本名 `verify_memory.py` / `auto_sync_daemon.py`，且健康检查持续报 3 个 YAML warning，导致入口说明和元数据都与现状不一致
- **影响范围**：所有项目（全局记忆入口 + 元数据质量）

### [2026-04-20 18:30] [APPEND] knowledge_cpp_pitfalls 加链接性/extern + TUniquePtr<前置声明>析构坑
- **来源项目**：心动 XDAdaptivePerformance 重构（学习副产物）
- **变更内容**：`knowledge/knowledge_cpp_pitfalls.md` 追加两大节：
  1. **链接性 vs 作用域 vs 存储期**：三维度区分表 + extern 工作机制（声明 vs 定义 + 链接器流程）+ external/internal/no linkage 表 + UE Unity Build 引发的 C4211 坑（static 定义 + extern 声明在同 TU 内冲突）+ header/cpp 标准模式
  2. **TUniquePtr<前置声明类> 析构 C4150**：PIMPL 必踩。原因（隐式 dtor 展开需完整类型）+ 修法（.h 显式声明 ctor/dtor，.cpp `= default`）+ 适用范围（unique_ptr/shared_ptr 都中招，TWeakObjectPtr 例外）
- **原因/案例**：CSV 采样逻辑抽 FCSVSamplerService 时连踩两坑：(1) Service.cpp `extern T CVar;` + Module.cpp `static T CVar(...)` 在 Unity Build 拼成同 TU 后 C4211 (2) Module.h 用 `class FCSVSamplerService;` forward decl + `TUniquePtr<FCSVSamplerService>` 成员，编译器为 Module 生成隐式 dtor 时报 C4150。两个都是面试高频 + 实战必遇
- **影响范围**：所有 C++/UE 项目

### [2026-04-20 17:00] [APPEND] 知识库追加 UE 智能指针 / 命名前缀 / Public-Private 语义 + C++ const 位置规则
- **来源项目**：心动 XDAdaptivePerformance 重构（学习副产物）
- **变更内容**：
  1. `knowledge/knowledge_ue_internals.md` 追加：TUniquePtr/TSharedPtr/MakeShared/MakeUnique/UE_NONCOPYABLE、FAutoConsoleCommand RAII 自注册、UE 类型命名前缀完整表（U/A/F/I/E/T/S/b）、Public/Private 目录的真正语义（不是 .h/.cpp 分开）
  2. `knowledge/knowledge_cpp_pitfalls.md` 追加：const 位置规则（const T / T const / T* const / const T* const 四态）+ 成员函数后置 const 的语义和约束
  3. 两文件 `updated` frontmatter 同步更新
- **原因/案例**：用户在重构期间问的 4 个 UE/C++ 概念问题（MakeUnique 是啥、F 前缀含义、UE_NONCOPYABLE 干嘛、const 位置区别），明确要求"记进 memory 后面回顾"。属于知识盲区落库
- **影响范围**：知识库（C++/UE 学习方向）

### [2026-04-20 15:30] [FIX/PUSH] post_task_hook 同步 skills-repo + 暴露 push 错误 + 手动追推
- **来源项目**：claude-system-cleanup
- **变更内容**：
  1. `post_task_hook.py` `git_sync_repo` 改返回 `(ok, msg)`，push 失败把 stderr tail 暴露出来；不再 `capture_output=True` 裸吞错
  2. `main()` 同步循环改为 `[MEMORY_DIR, SKILLS_DIR]` 双仓推送，失败计入 `result.errors`（pre-commit 模式会阻止 commit）
  3. 加 `skills-repo/.gitignore` 忽略 `__pycache__`，`git rm --cached` 清掉历史 pyc
  4. 手动 `git pull --rebase` global-memory（17 个 auto-fix commit 落后 1 远端 commit `f8a5af9`，远端只加新文件 → 干净 rebase）→ push 成功
  5. 手动 commit + push skills-repo（marker 模式 sync_index、update_stats 边界修、A 独有 hooks/session_report/smoke_test/stage_lib 全量 cp）
- **原因/案例**：上一轮检查发现 global-memory ahead 17 commits 没人推、skills-repo 7 个文件未提交。根因 `post_task_hook.git_sync_repo` 用 `capture_output=True` 静默吞 push 错误（远端有新 commit 一直 reject 但 hook 报 ✅）
- **影响范围**：全局基础设施（自动同步链路 + 两个核心仓库实际推送）
- **验证**：global-memory `9185328` / skills-repo `d779aaa` 均 push 成功；下次 Stop hook 触发若再失败会在 result.errors 里直接报出来

### [2026-04-20 14:50] [FIX] update_stats.py 修边界 + sync_index 加自愈 + 新 feedback
- **来源项目**：claude-system-cleanup（D:/ClaudeTasks/active/claude-system-cleanup/）
- **变更内容**：
  1. `update_stats.py` 正则边界加入 `\n<!-- AUTO-INDEX:END`，不再吞 marker（这是导致 marker 累积 bug 的根因）
  2. `sync_index.py` legacy-migrate 路径增加 strip 孤儿 marker 的防御逻辑（即使别处出问题也能自愈）
  3. 新建 `feedback/feedback_infra_ops_windows.md`：3 条铁律（PowerShell 建 junction / 删 hook 引用目录原子化 / marker-aware 工具链）
- **原因/案例**：上一条 CHANGELOG 后发现 MEMORY.md 累积了 7 个 AUTO_BEGIN marker，0 个 END。根因是 update_stats 的正则贪心吞 END，sync_index 误入 legacy-migrate 反复加 BEGIN
- **影响范围**：全局基础设施（记忆维护脚本工具链一致性）
- **验证**：BEGIN=1, END=1；3 个自定义区块仍在；A/B 通过 junction 自动一致

### [2026-04-20 14:20] [FIX/REFACTOR] sync_index.py 改 marker 模式 + 批次 3 收尾
- **来源项目**：claude-system-cleanup（D:/ClaudeTasks/active/claude-system-cleanup/）
- **变更内容**：
  1. `skills-repo/_bootstrap/scripts/sync_index.py` 重写为 `<!-- AUTO-INDEX:BEGIN/END -->` marker 模式：只重建 markers 之间，区块外的 📌/🏗️/📜 自定义章节不再被覆写；首次运行带 legacy-migrate
  2. MEMORY.md 恢复 📜 复盘记录区块；自动区用 markers 包裹
  3. A/B scripts 双轨合并：9 个分化 .py 全部保留 B（auto-fix 维护版本）；A 独有 session_report.py + smoke_test.py + 整个 hooks/ 目录 cp 入 `skills-repo/_bootstrap/scripts/`；A 整目录备份到 `~/.claude/_backups/scripts_20260420/`
  4. `~/.claude/scripts` 改为 directory junction → `~/.claude/skills-repo/_bootstrap/scripts`（PowerShell `New-Item -ItemType Junction` 建立，git bash `cmd //c mklink` 报"无效语法"踩坑）
  5. 用户在过程中改 settings.json 把 6 处 hook 路径直指 `skills-repo/...`（删 A 后 hook 链路断裂导致工具被 PreToolUse 阻塞，需手动解锁）
- **原因/案例**：HANDOFF.md「新发现 P0」要求修 sync_index 否则 MEM-11 持续被破坏；批次 3 是 SPEC 收尾批次
- **影响范围**：全局基础设施（脚本路径、hook 行为、记忆索引算法）
- **验证**：MEM-11 PASS；verify_all = 10 PASS / 4 WARNING / 0 ERROR

### [2026-04-20 13:30] [REWRITE] MEMORY.md + NEW knowledge/docs/INDEX.md
- **来源项目**：claude-system-cleanup（D:/ClaudeTasks/active/claude-system-cleanup/）
- **变更内容**：
  1. 重建 MEMORY.md：补全 30+ 漂移文件的索引；新增「📌 系统规则与索引」「🏗️ 项目文档」「📜 复盘记录」三个区块
  2. 新建 knowledge/docs/INDEX.md：30 篇深度文档分 6 组索引（MEMORY.md 不再一一列出）
  3. 改 verify_memory.py MEM-11：递归白名单制（黑名单 = 系统/运维文件 + 子目录），docs/ 走 INDEX.md 校验；A/B 两套同步
- **原因/案例**：REVIEW-2026-04-20-1220.md 发现 MEMORY.md 索引声称 49/50 实际 64+，30+ 文件未索引；MEM-11 检测漏 docs/test-reports/retrospectives/ 等子目录
- **影响范围**：影响所有项目（全局记忆入口 + 全局健康检查脚本）
- **遗留**：linter/hook 在持续改 MEMORY.md（删 retro 区块、回退统计），见 HANDOFF.md「新发现 P0」

### [2026-04-20 13:30] [MIGRATE] skills/work → skills-repo/work/v1/ + junction
- **来源项目**：claude-system-cleanup
- **变更内容**：
  1. `skills-repo/work/v1/` 新建（完整复制部署位 SKILL.md + scripts/ + templates/）
  2. 备份 `skills/work/` 到 `~/.claude/_backups/skills_work_20260420/`
  3. `skills/work/` 改 directory junction → `skills-repo/work/v1/`
- **原因/案例**：work skill 仅在部署位存在、repo 无源 → 重部署会丢失
- **影响范围**：影响所有项目（/work skill 来源）


## 格式规范

```markdown
### [YYYY-MM-DD HH:MM] [操作类型] [文件路径]
- **来源项目**：[项目名 / 通用]
- **变更内容**：[一句话描述改了什么]
- **原因/案例**：[为什么改，来自什么具体场景]
- **影响范围**：[只影响本项目 / 影响所有项目]
```

操作类型：`CREATE` | `UPDATE` | `DELETE` | `PROMOTE`(从项目级提升为全局规范)

---

## 变更记录

### 2026-04-13 12:00 CREATE knowledge/docs/*.md (6 个文档)
- **来源项目**：通用
- **变更内容**：批量生成 6 个深度知识文档（UE 引擎/C++ 多线程/Prompt 体系/面试追问链/项目话术/Code Review）
- **原因/案例**：离职前最大化利用 token 生成可离线使用的知识资产
- **影响范围**：所有项目


### 2026-04-13 13:00 CREATE knowledge/docs/async-resource-loading-preresearch.md
- **来源项目**：心动引擎中台（预研）
- **变更内容**：多线程资源加载预研文档（692 行，3 方案对比）
- **原因/案例**：入职心动前的技术准备
- **影响范围**：心动项目


### 2026-04-13 13:30 CREATE knowledge/docs/interview-cheatsheet.md
- **来源项目**：通用
- **变更内容**：面试速查卡（118 行，UE 10 模块 + C++ 多线程一句话速记）
- **原因/案例**：从深度文档中提炼的口语化版本
- **影响范围**：所有项目


### 2026-04-13 14:00 CREATE projects/xindong-engine/dev-map.md + task-board.md
- **来源项目**：心动引擎中台
- **变更内容**：项目导航模板和任务板
- **原因/案例**：为入职后的项目上下文做准备
- **影响范围**：心动项目


### 2026-04-13 15:00 UPDATE MEMORY.md
- **来源项目**：通用
- **变更内容**：顶部新增"🔥 当前活跃项目"区块
- **原因/案例**：新 AI 对话不知道当前在做什么项目，需要一个入口锚点
- **影响范围**：所有项目


### 2026-04-13 16:53 CREATE CHANGELOG.md
- **来源项目**：通用
- **变更内容**：记忆变更审计日志，追溯所有历史变更
- **原因/案例**：跑了两个项目后发现无法追踪"谁改了什么记忆、为什么改"
- **影响范围**：所有项目


### 2026-04-13 16:53 CREATE decisions/conventions.md
- **来源项目**：帧同步 v2 + 博客重设计（PROMOTE）
- **变更内容**：12 条跨项目规范，8 条标注 🔒 硬检查
- **原因/案例**：帧同步项目中总结的好实践（SPEC 先行、HANDOFF 必备、namespace 必须有等），需要同步给其他项目
- **影响范围**：所有项目


### 2026-04-13 16:53 UPDATE MEMORY.md
- **来源项目**：通用
- **变更内容**：索引新增 Decisions 和审计区块（conventions.md + CHANGELOG.md）
- **原因/案例**：verify_conventions.py 检查出 MEM-03 WARNING（索引不同步）
- **影响范围**：所有项目


### 2026-04-13 17:05 CREATE scripts/verify_memory.py
- **来源项目**：通用
- **变更内容**：记忆仓库健康检查脚本（13 项自动检查），替代人工/AI 审查
- **原因/案例**：跑了两个项目后记忆格式不一致（docs/ 无 YAML、conventions.md 无 YAML），需要自动化检测
- **影响范围**：所有项目


### 2026-04-13 17:06 UPDATE decisions/conventions.md
- **来源项目**：通用
- **变更内容**：添加 YAML 头部（name/description/type/created/updated/source）
- **原因/案例**：verify_memory.py MEM-03 ERROR 检测到 decisions/ 下文件缺少 YAML 头
- **影响范围**：所有项目


### 2026-04-13 17:22 CREATE scripts/maintain_memory.py
- **来源项目**：通用
- **变更内容**：记忆仓库自动维护脚本（sync-index/update-stats/init-project/close-project/changelog）
- **原因/案例**：verify 系列脚本只检测不修复，需要一个自动修复/维护的脚本
- **影响范围**：所有项目


### 2026-04-13 17:33 UPDATE scripts/*
- **来源项目**：通用
- **变更内容**：拆 maintain_memory.py 为 6 个单一职责脚本(_lib/sync_index/update_stats/init_project/close_project/append_changelog) + 新增 update_readme.py，所有脚本加留档到 ~/.claude/logs/
- **原因/案例**：职责单一原则+错误最小化+运行留档
- **影响范围**：所有项目


### 2026-04-13 18:56 CREATE knowledge/docs/4个搜索文档
- **来源项目**：通用
- **变更内容**：心动情报+面试趋势+UE5异步加载+Harness 2026最新实践
- **原因/案例**：离职前最大化利用token收集外部情报
- **影响范围**：所有项目


### 2026-04-13 19:07 CREATE knowledge/docs/game-physics-reference.md + game-networking-reference.md
- **来源项目**：通用
- **变更内容**：物理模拟(PBD/XPBD/赛车) + 网络同步(帧同步/RUDP/GGPO)技术参考
- **原因/案例**：面试准备 + 帧同步项目技术验证
- **影响范围**：所有项目


### 2026-04-13 19:10 UPDATE knowledge/docs/game-physics-reference.md + game-networking-reference.md
- **来源项目**：通用
- **变更内容**：补充GDC物理演讲/GGST回滚/永劫无间混合同步/Gaffer On Games/网易雷火/事件流同步
- **原因/案例**：用户要求补充更多行业文献和具体游戏方案
- **影响范围**：所有项目


### 2026-04-13 19:18 UPDATE knowledge/docs/game-*-reference.md
- **来源项目**：通用
- **变更内容**：补充GGPO深度架构/GGST/永劫无间/Gaffer7篇/Fix Your Timestep/雷火三部曲/事件流/Catto12场GDC/CCD/Sequential Impulses/Dynamic BVH
- **原因/案例**：用户要求补充更多行业文献
- **影响范围**：所有项目


### 2026-04-13 19:27 UPDATE _bootstrap/CLAUDE.md + agents/*.md
- **来源项目**：通用（双 Agent 审查）
- **变更内容**：修复 15 个审查问题（3🔴+6🟡+6🟢）：工作背景改动态引用、MEMORY_UPDATE格式补齐、个人项目限定为学习、启动协议去重、Skill触发对照表、转交判断、苏格拉底豁免、审查例外、讨论模式、对外沟通约束、CHANGELOG格式内联、代码审查子模式、fixes门槛扩展、compact规则明确、简历场景
- **原因/案例**：5维度审查发现工作背景即将过时(V4)、记忆写入不可预测(U1)、Agent边界模糊(M1)等关键问题
- **影响范围**：所有项目


### 2026-04-13 19:55 UPDATE 系统架构深度优化（6 项）
- **来源项目**：通用（架构审查）
- **变更内容**：
  1. Skill 下沉：workspace-init/multi-search-engine/memory-manager/doc-generator → _archived/
  2. 记忆写入一致性：MEMORY_UPDATE 增加 update/conflict 操作 + 去重/矛盾检测
  3. 深度文档标注为快照，Topic 为准
  4. CHANGELOG 归档：新增 changelog_archive.py 周归档脚本
  5. L2 记忆 A+B 方案：Topic YAML 加 summary + generate_project_context.py 关键词预判注入
  6. MEMORY.md 索引改为 summary 摘要格式 + references 区块
- **原因/案例**：架构审查发现 Skill 膨胀、L2 按需读取不可靠、记忆写入重复/矛盾、CHANGELOG 膨胀、docs 和 Topic 分叉
- **影响范围**：所有项目


### 2026-04-13 21:00 CREATE knowledge/docs/resource-links.md + ue-source-deep-dive.md + cpp-memory-model-lockfree.md
- **来源项目**：通用（WorkBuddy 资料整理）
- **变更内容**：
  1. `resource-links.md` — 48 篇高质量技术文章链接索引（9 大类，每类标 ★）
  2. `ue-source-deep-dive.md` — UE5 八大模块源码级参考（反射/GC/Subsystem/Delegate/TaskGraph/Timer/异步加载/FTimerManager），基于多篇文章交叉验证整合
  3. `cpp-memory-model-lockfree.md` — C++ 内存模型与无锁编程深度参考（6 种 memory_order/Happens-Before/CAS/无锁栈/自旋读写锁+完整代码+性能对比）
- **原因/案例**：用户搜集大量高质量 UE 源码分析和 C++ 深度资料，抓取核心文章后做批判性整合
- **影响范围**：所有项目


### 2026-04-13 21:15 CREATE 4 个战略/方法论文档
- **来源项目**：通用（WorkBuddy 深度分析）
- **变更内容**：career-strategy-2027.md + ai-impact-game-dev.md + learning-methodology.md + onboarding-plan.md
- **原因/案例**：利用深度分析做职业规划/AI 冲击/学习方法/生活优化
- **影响范围**：所有项目


### 2026-04-13 21:22 CREATE knowledge/docs/gdc-must-watch.md
- **来源项目**：通用（WorkBuddy 整理）
- **变更内容**：GDC 必看演讲清单（28 演讲 × 7 方向）
- **影响范围**：所有项目


### 2026-04-14 02:30 CREATE FIXLIST.md（CLI 迁移审计）
- **来源项目**：系统级
- **变更内容**：CLI 适配问题清单（5P0+11P1+4P2），Sonnet 4.6 全量测试 T01-T38 生成
- **影响范围**：所有项目


### 2026-04-14 04:20 CREATE test-reports/ 9 组报告 + final-summary + smoke
- **来源项目**：通用（系统验证）
- **变更内容**：T01-T38 全量测试报告 + 夜间冒烟测试 + 博客音乐播放器复盘
- **影响范围**：通用


### 2026-04-14 09:16 UPDATE MEMORY.md + CHANGELOG.md（merge 冲突解决）
- **来源项目**：通用（WorkBuddy 同步）
- **变更内容**：解决 CLI 端和 WorkBuddy 端的 3 处 git merge 冲突，合并两边内容
- **影响范围**：所有项目


### 2026-04-14 09:35 CREATE interview/resume-versions.md + UPDATE question_bank + system_design
- **来源项目**：通用（Study/ 目录文件清理整合）
- **变更内容**：
  1. `interview/resume-versions.md` — 简历定稿版（引擎版+客户端版+面试钩子策略）
  2. `interview/interview_question_bank.md` — 大规模更新：心动二面完整记录+米哈游 140 题+算法/OS/场景设计
  3. `knowledge/knowledge_system_design.md` — 万能 5 步框架+A 攻击 B 标准答案+项目对应表+练习清单
- **原因/案例**：用户清理 D:/TestContent/Study/ 12 个文件，提取有价值内容沉淀
- **影响范围**：面试全方位


### 2026-04-14 09:45 UPDATE feedback_code_style.md + feedback_output_format.md
- **来源项目**：通用（T01-T38 评估后批量修复）
- **变更内容**：两个 feedback 文件从空壳激活——预填已知偏好（C++ 红线/UE 规范/回答风格/方案对比规则）
- **原因/案例**：T16 暴露 feedback 系统完全空壳，从未有真实纠正记录
- **影响范围**：所有项目


### 2026-04-14 09:54 CREATE agents/guardian-agent.md + UPDATE CLAUDE.md + FIXLIST.md
- **来源项目**：通用（WorkBuddy 系统修复）
- **变更内容**：
  1. 新建 `guardian-agent.md` — 规范守卫 Agent（5 大类检查清单 + 脚本辅助 + PASS/CONDITIONAL/FAIL 判定）
  2. CLAUDE.md 新增「交付前门禁」铁律 — 交付前必须派生 guardian-agent，FAIL 阻断交付
  3. FIXLIST.md 更新已修复进度（13 项已修复）
- **原因/案例**：系统分析发现"脚本全有但没串联"，guardian-agent 是结构性解法
- **影响范围**：所有项目


### 2026-04-14 09:57 UPDATE test-reports/ 合并 + MEMORY.md 索引 + conventions FILE-01
- **来源项目**：通用（系统修复 FIX-02/21/23）
- **变更内容**：
  1. test-reports/ 9 个 group 文件合并为 `all-tests-detail-2026-04-14.md`，文件数 49→41
  2. MEMORY.md 索引更新（test-reports 区块 + 文件计数修正）
  3. conventions.md 新增 FILE-01 静态资源文件名 ASCII 化规范
- **原因/案例**：文件数接近上限 49/50 需清理；博客复盘发现文件名问题需规范化
- **影响范围**：所有项目


### 2026-04-16 14:00 CREATE fixes/fixes_android_apk_build.md + UPDATE task-board.md + MEMORY.md
- **来源项目**：心动引擎中台（火炬之光 Android 打包）
- **变更内容**：
  1. 新建 `fixes/fixes_android_apk_build.md` — Git Bash 环境下 UE4 Android 打包的三个兼容性修复
  2. 更新 `projects/xindong-engine/task-board.md` — 新增 Android APK 打包需求专项记录（进度、卡点、修复记录、关键文件位置）
  3. 更新 MEMORY.md 索引（Fixes 区块新增条目）
- **原因/案例**：首次在本机跑完 Android 打包全流程，沉淀 Git Bash + UE bat 工具链兼容性经验（NoDefaultCurrentDirectoryInExePath / subst / MSYS_NO_PATHCONV）。当前卡在 ShaderCodeLibrary 初始化失败（Global Shader 缺失）
- **影响范围**：心动项目 + 通用 Git Bash 经验



### 2026-04-17 12:15 CREATE decisions/decision_work_mode_workflow.md + skills/work/ 全套 + 改 work-agent.md
- **来源项目**：通用（harness 升级）
- **变更内容**：
  1. 新建 `skills/work/SKILL.md` + `scripts/{load_context,check_doc_status,check_doc_sync}.py` + `templates/workflow.md` — 工作模式统一入口
  2. 新建 `decisions/decision_work_mode_workflow.md` — 架构决策记录（三层文档防线 + 为什么不用 hook/subagent）
  3. 修改 `agents/work-agent.md` — 顶部加「流程入口」章节指向 `/work`，保留所有现有子模式
  4. 修改 `MEMORY.md` Decisions 区块加索引
- **原因/案例**：work-agent 之前是「人格描述」靠自觉走启动协议，会漏文档校验和收尾同步。spec_gate.py 是 PreToolUse 被动拦截，触发时已经在写代码了。统一为 `/work` skill 显式入口 + 三层文档防线（入口主动校验 / spec_gate 兜底 / 收尾追踪）
- **影响范围**：所有项目（替代 work-agent 的隐式启动协议）



### 2026-04-22 UPDATE projects/xindong-engine/task-board.md（Android APK 移入已完成）
- **来源项目**：心动引擎中台
- **变更内容**：
  1. Android APK 打包从「进行中/闪退」迁到「已完成」（2026-04-21 红米 K60 真机跑通）
  2. 当前进行中加入 XDAdaptivePerformance 重构（Phase 1c），关联 baseline-logs 位置
  3. 专项记录中标注 ShaderCodeLibrary 闪退已解决，但**修复手段未沉淀**，标待补
- **原因/案例**：用户告知"手机包已经打成功过了，红米跑通"。task-board 状态严重过期需对齐
- **遗留**：等用户回忆 ShaderCodeLibrary 实际修复路径（是否补 .uproject 插件启用、是否走全量 Cook、还是别的方案），补 `fixes/fixes_shader_code_library_missing.md`

### 2026-04-22 CREATE fixes/fixes_shader_code_library_missing.md
- **来源项目**：心动引擎中台
- **变更内容**：
  1. 新建 `fixes/fixes_shader_code_library_missing.md` — 修复手段：去掉 minimal cook 走全量 cook
  2. 更新 task-board.md 已完成行 + 专项记录闪退段，加 fix 文档链接
- **原因/案例**：用户回忆确认 ShaderCodeLibrary 闪退最终修法（红米 K60 验证通过）。沉淀关键经验：minimal cook 不能用于打可分发 APK，Global Shader 必须全量 cook
- **关联**：项目里另有「插件未启用 → Cook 失败」根因链（fixes_android_apk_build.md / CLI memory fixes_android_build.md），fix 文档里已交叉引用并给出区分方法


### 2026-04-22 ARCHIVE D:/ClaudeTasks/active/memory-system-merge → archived/
- **来源项目**：claude harness 自身
- **变更内容**：
  1. global-memory + skills-repo 单仓合并执行完成（Phase A 备份 / B 杀 daemon / C bootstrap install / D check 全绿）
  2. `~/.claude/{agents,scripts}` 现以 junction 指向 `D:/global-memory/{agents,harness}`；`~/.claude/skills/` 为普通目录含合并后的 skill junction
  3. `settings.json` 8 个 hook 全部改写为 `D:/global-memory/harness/hooks/*.py` 路径
  4. `auto_sync_daemon` 装 Windows Startup（`Startup/auto_sync_startup.vbs`）实现开机自启，弥补此前**无任何自启机制**的盲区（switch.sh "自动重启" 文档误导已确认）
  5. 修复 `~/.claude/CLAUDE.md` 中 `skills-repo/check/v1/SKILL.md` 残留路径 → `skills/check/SKILL.md`
  6. 任务 `memory-system-merge` 三份文档 Status 从 `implementation` 改为 `archived`，从 `project_registry.json` 的 `active_tasks` / `task_paths` 移除，目录从 `active/` 移到 `archived/`（源目录残留空壳，被 Defender/索引器锁住，重启后清）
- **原因/案例**：用户判定合并方案落地、所有 5 项 D 阶段验证通过。归档以释放 active_tasks 槽位
- **影响范围**：所有依赖 `~/.claude/skills`、`~/.claude/scripts`、`~/.claude/agents` 的 skill / hook / 脚本路径——全部通过 junction 透明寻址，外部无需改动
- **遗留**：①`active/memory-system-merge` 空目录待手动 `rmdir`（Windows 文件锁缓存）②`registry.templates_dir` 仍指向 `D:/skills-repo/_bootstrap/templates`，若后续清理 `D:/skills-repo` 需同步改 ③`claude-system-cleanup` 任务存在但未登记 `active_tasks`，按需补
