# global-memory 维护工具手册

这份文档给人类维护者看，用来回答三个问题：

1. 当前这套 harness engineering 体系有哪些工具。
2. 自动同步、健康检查、任务收尾到底由谁触发。
3. 出问题时先看哪里、跑什么命令。

如果你只是想知道主控面板每个按钮怎么用，先读 [CONTROL_PANEL.md](CONTROL_PANEL.md)。

它不替代脚本源码中的细节注释；脚本行为以代码为准。

## 快速判断：我现在该用哪个工具

| 你想做什么 | 首选入口 | 说明 |
|---|---|---|
| 打开人类主控台 | `harness\control_panel.bat` | Tkinter 桌面 GUI，无额外依赖。 |
| 看面板按钮怎么用 | [CONTROL_PANEL.md](CONTROL_PANEL.md) | 面向第一次使用者的短说明。 |
| 快速看当前状态 | `python harness\maintain.py status --json` | 只读快照：Git、文件分组、daemon、最近日志。 |
| 做一次只读总检查 | `python harness\maintain.py doctor` | 主控体检入口，默认不写文件、不提交、不推送。 |
| 让 GUI/AI 读取体检结果 | `python harness\maintain.py doctor --json` | 机器可读报告。 |
| 做安全本地修复 | `python harness\maintain.py fix` | 只做索引/统计/路径类本地修复，不提交。 |
| 同步前预览 checkpoint | `python harness\maintain.py sync --preview --json` | 只读预览，不 safe-fix、不 stage、不提交、不推送。 |
| checkpoint 提交并推送 | `python harness\maintain.py sync --source manual` | 唯一推荐的手动同步入口。 |
| 生成维护报告 | `python harness\maintain.py report --markdown` | 输出当前能力边界、问题和下一步建议。 |
| 看能力边界是否清晰 | `python harness\scripts\check_capability_manifest.py --json` | 校验 `capability_manifest.json` 中 core/optional/experimental/legacy/deprecated 状态、脚本路径和全脚本能力归属。 |
| 看客户端支持边界是否清晰 | `python harness\scripts\check_client_manifest.py --json` | 校验 `client_manifest.json` 中稳定/实验/计划客户端、入口路径、完整生命周期接入、read-only Context Brief 接入边界和外部 claim policy。 |
| 非 hook 客户端获取 Context Brief | `python harness\scripts\client_context.py --client generic_cli --task unknown --query "test" --json` | 通用 CLI 接入契约，默认只读不写日志。 |
| 看 G1-G9 治理门禁是否通过 | `python harness\scripts\gate_check.py --json` | 只读输出 gate verdict；默认无 `--json` 仍写 GATE-REPORT。 |
| 看 AI 生成代码是否满足质量门 | `python harness\scripts\quality_gate.py verify --json` | 按当前 git diff 自动分 Tier，检查验证说明、测试证据和 AI review 证据；长期 dirty 仓库用 `--path` 限定本轮范围。 |
| 看脚本能力是否被总览吸收 | `python harness\scripts\scan_orphan_scripts.py --strict --json` | 对账 `harness/` 实际脚本和 `docs/scripts-registry.md`。 |
| 看 hook manifest/文档/模板/运行时是否漂移 | `python harness\scripts\check_hook_alignment.py --strict --json` | 校验 `hook_manifest.json` schema/path，并对账 `bootstrap.py`、`~/.claude/settings.json` 和 `docs/scripts-registry.md`。 |
| 做一次 OSS checkpoint 收束 | `python harness\maintain.py release-checkpoint --json` | 聚合外部源码安全、release verdict、issue ledger、gap table、owner decisions 和 manifest 摘要；默认只读，适合形成当前剩余缺口表。`--strict --json` 会在 blocked/warning checkpoint 下返回非零但仍输出同一 JSON 契约。 |
| 看当前离外部可接入/开源 profile 还差什么 | `python harness\maintain.py release-check --profile oss --json` | 聚合能力注册、自动目录 freshness、hook 对齐、路径配置、硬编码路径、输出契约、smoke 等 blocker/warning；legacy health 需显式 opt-in。 |
| 看私有仓库成熟度审计是否阻塞 | `python harness\maintain.py release-check --profile private-audit --json` | 保留 license/publish scope/source export 为 warning 和证据；适合 owner 已选择不公开发布时继续治理质量问题。 |
| 看当前剩余缺口表 | `python harness\maintain.py release-gaps` | 从当前 release-check 派生 owner/code/docs/publish-scope 缺口表；owner 行带记录命令，非 owner 行保留判断所需的紧凑证据。 |
| 看 owner 决策队列 | `python harness\maintain.py release-decisions --json` | 显示 `license_policy`、`publish_scope_boundary` 等 owner 决策记录状态，并区分 `record_ready` 和 `gate_ready`。 |
| 验证 owner 决策记录 | `python harness\maintain.py release-record-decision --dry-run --decision <id> --selected-option <option> --decided-by <owner> --decided-at YYYY-MM-DD --json` | 只验证将要写入的 owner state；`--write` 才会修改 `harness/release_owner_decisions.json`，且不会提交。 |
| 看自循环/优化证据链 | `python harness\scripts\self_loop_report.py --json` | 汇总 `.meta` 证据链、fallback 候选、已应用优化和完成门禁；JSON 输出进入 output-contract。 |
| 看仓库记忆索引、YAML、统计、Git 状态是否健康 | `python harness\maintain.py doctor` | 唯一权威健康入口。 |
| 验证本机 `~/.claude` junction 和 hooks | `python bootstrap.py check` | 确认 active runtime 确实指向本仓库。 |
| 重新部署 agents/scripts/skills/settings hooks | `python bootstrap.py install` | 会写 `~/.claude/settings.json` 并重建 junction。 |
| 看全套 harness 检查项 | `python harness\verify_all.py --checks` | 只列检查项，不执行全部检查。 |
| 正式任务收尾 | `python harness\task_complete.py <project_dir> --fix` | 跑规范、基础设施、索引、统计、进度文档检查。 |
| 排查 Prompt/Agent/Skill 配置一致性 | `python harness\verify_prompt_system.py --report` | 检查 CLAUDE.md 与 Agent 配置重复、漂移、缺失。 |

## 部署与运行入口

### `harness/control_panel.py`

职责：给人类看的桌面主控台。日常建议双击：

```powershell
harness\control_panel.bat
```

GUI 提供：

| 页签 | 能力 |
|---|---|
| 总览 | 快速状态、完整 doctor 明细、维护报告入口。 |
| 修复 | 运行安全本地修复；高风险部署操作会二次确认。 |
| 同步 | 查看变更分组、生成只读 checkpoint 预览、一键同步。 |
| 守护进程 | 查看/启动/停止自动同步守护进程，查看 `auto_sync.log` 尾部。 |
| AI 执行 | 通过 `ai_runner.py` 调用 Claude CLI 做只读诊断/计划；V1 不允许自动执行。 |
| 外部事件 | 自动显示 AI/脚本通过 `panel_api.py` 写入的本地事件。 |
| 历史 | 查看 checkpoint 与语义提交、维护日志、维护报告。 |

GUI 不直接拼底层脚本，统一调用 `maintain.py` 和 `ai_runner.py`。

实时性边界：

| 能力 | 当前实现 |
|---|---|
| 快速状态 | 面板打开后每 10 秒静默刷新一次。 |
| 外部事件 | 每 2 秒读取 `~/.claude/logs/control_panel_events.jsonl`。 |
| HTTP/WebSocket API | V1 暂不提供，避免引入常驻服务和端口管理。 |

外部事件 API 示例：

```powershell
python harness\panel_api.py notify --source ai --level info --title "分析完成" --message "建议先生成同步预览。"
```

### `harness/maintain.py`

职责：当前 harness 治理层的主控 CLI。

常用命令：

```powershell
python harness\maintain.py doctor
python harness\maintain.py doctor --json
python harness\maintain.py status --json
python harness\maintain.py fix
python harness\maintain.py sync --preview --json
python harness\maintain.py sync --source manual
python harness\maintain.py daemon status
python harness\maintain.py log --limit 40
python harness\maintain.py report --markdown
python harness\maintain.py release-checkpoint --json
python harness\maintain.py release-checkpoint --strict --json
python harness\maintain.py release-gaps
python harness\maintain.py release-decisions --json
python harness\maintain.py release-decisions --template --json
python harness\maintain.py release-record-decision --dry-run --decision license_policy --selected-option no_public_license --decided-by <owner> --decided-at YYYY-MM-DD --json
python harness\maintain.py release-check --profile oss --json
python harness\maintain.py release-check --profile private-audit --json
```

边界：

| 子命令 | 是否改 tracked 文件 | 是否 commit/push |
|---|---:|---:|
| `status` | 否 | 否 |
| `doctor` | 否 | 否 |
| `release-checkpoint` | 否 | 否 |
| `release-gaps` | 否 | 否 |
| `release-decisions` | 否 | 否 |
| `release-record-decision --dry-run` | 否 | 否 |
| `release-record-decision --write` | 是，仅 `harness/release_owner_decisions.json` | 否 |
| `release-check` | 否 | 否 |
| `fix` | 可能 | 否 |
| `sync --preview` | 否 | 否 |
| `sync` | 可能先跑安全修复 | 是 |
| `daemon status` | 否 | 否 |
| `daemon start/stop` | 启停进程 | 否 |
| `log` | 否 | 否 |
| `report` | 默认只打印；`--save` 写 `~/.claude/logs` | 否 |

### 能力吸收与 `.meta` 自循环

这套仓库现在不只是记忆文件集合，还包含 hook、gate、health、retrieve 实验、自循环证据链和任务生命周期工具。新增能力必须先被系统“吸收”，否则会出现脚本存在但总览/doctor/维护入口不知道它的情况。

能力吸收的当前 source of truth：

| 文件 | 用途 |
|---|---|
| `docs/getting-started.md` | 外部最小安装、验证、接入路径。 |
| `docs/scripts-registry.md` | harness 脚本清单，记录触发方和失败动作。 |
| `docs/capabilities.md` | 18 个能力域的外部用户说明；每节用 `capability:<id>` 绑定 manifest。 |
| `docs/license-decision.md` | 许可证未决 blocker 的决策说明；不替项目所有者选择 license。 |
| `docs/publish-scope.md` | 外部发布范围和个人数据边界；不把 active 私人仓库误当干净源码包。 |
| `docs/capability-map-and-oss-gap.md` | 能力地图和开源倒逼缺口。 |
| `docs/meta-evidence-pipeline.md` | `.meta` 自循环证据链说明。 |
| `harness/capability_manifest.json` | core/optional/experimental/legacy/deprecated 能力边界，并强制所有 harness 脚本有能力归属。 |
| `harness/client_manifest.json` | Claude Code / generic CLI / 计划中客户端的支持边界，区分 full lifecycle、Context Brief only 和外部 claim policy。 |
| `harness/config.py` | repo、Claude home、task、log、cache roots 的共享路径解析。 |
| `harness/hook_manifest.json` | Claude Code hook 链的机器可读 source of truth。 |
| `harness/maintenance_manifest.json` | 主控/GUI/AI 可发现的维护命令分组。 |

常用检查：

```powershell
python harness\scripts\scan_orphan_scripts.py --strict --json
python harness\scripts\check_capability_manifest.py --json
python harness\scripts\check_client_manifest.py --json
python harness\generate_catalog.py --check --json
python harness\scripts\gate_check.py --json
python harness\scripts\quality_gate.py verify --json
python harness\scripts\check_hook_alignment.py --strict --json
python harness\maintain.py release-checkpoint --json
python harness\maintain.py release-checkpoint --strict --json
python harness\maintain.py release-gaps
python harness\maintain.py release-decisions --json
python harness\maintain.py release-decisions --template --json
python harness\maintain.py release-check --profile oss --json  # includes maintenance_manifest and catalog_freshness
python harness\maintain.py release-check --profile private-audit --json
python harness\scripts\self_loop_report.py --json
python harness\scripts\meta_optimize.py --json
```

`.meta/` 是实验性证据链，不是默认自动优化器。它的链路是：

```text
health/retrieve logs
  -> proposal
  -> simulation/evaluation
  -> trial
  -> candidate admission
  -> optimization ledger
  -> self_loop_report / maintain report
```

约束：

| 规则 | 原因 |
|---|---|
| `.meta` 默认只读，不自动改默认行为。 | 防止优化脚本绕过人工判断。 |
| task-context fallback 优先 task-scoped opt-in。 | 避免全局召回噪声扩大。 |
| 已应用优化必须写入 `.meta/optimizations/optimizations.jsonl` 并包含 rollback。 | 保留审计和回滚路径。 |
| 新增脚本必须更新 `docs/scripts-registry.md`。 | 防止能力存在但系统总览不可见。 |
| 新增能力域必须更新 `harness/capability_manifest.json` 和 `docs/capabilities.md`；新增脚本必须被某个能力域吸收或显式 exemption。 | 防止 core、optional、experimental 和 legacy 边界混在一起，也防止“registry 有脚本但能力地图没有”。 |
| 新增或调整维护入口必须更新 `harness/maintenance_manifest.json`。 | 防止主控/GUI/AI 清单指向不存在脚本，或关键入口参数退回旧形态。 |
| 新增客户端接入或调整外部入口叙事必须更新 `harness/client_manifest.json`。 | 防止把 read-only Context Brief 契约或 Claude Code 深度集成误报成通用多客户端完整闭环，也防止 README/docs 越界宣称。 |
| 新增 release-facing 脚本的 repo/task/log/cache 默认路径应优先复用 `harness/config.py`。 | 防止 `Path.home()/.claude` 和本机路径 fallback 在脚本里重新分叉。 |
| 新增或调整 hook 必须先改 `harness/hook_manifest.json`，再跑 `check_hook_alignment.py --strict --json`。 | 防止 hook 文件缺失、路径越界、failure_action 非法，以及文档/模板/runtime 分裂。 |

### `bootstrap.py`

职责：把仓库部署到 Claude Code 运行位置。

常用命令：

```powershell
python bootstrap.py check
python bootstrap.py install
```

它负责：

| 项 | 行为 |
|---|---|
| Skill junction | `~/.claude/skills/<skill>` 指向 `skills/<skill>/v1`。 |
| Agent junction | `~/.claude/agents` 指向 `agents/`。 |
| Script junction | `~/.claude/scripts` 指向 `harness/`。 |
| Hook settings | 渲染 `~/.claude/settings.json` 的 `hooks` 字段。 |

当前部署的 Skill 清单在 `bootstrap.py` 的 `SKILLS` 常量里维护。

## 自动维护链路

### 对话结束链路：Stop hook

部署后，`~/.claude/settings.json` 中的 `Stop` hook 会调用：

```powershell
python ~/.claude/scripts/post_task_hook.py --auto-fix
```

因为 `~/.claude/scripts` 是 junction，所以实际脚本来自：

```text
harness/post_task_hook.py
```

它会做：

| 步骤 | 行为 |
|---|---|
| 索引检查 | 检查 `MEMORY.md` 的 `AUTO-INDEX` 是否和 topic 文件一致。 |
| CHANGELOG 检查 | 今天有 Git 变更但无 CHANGELOG 记录时给警告。 |
| 自动修复 | `--auto-fix` 下调用 `sync_index.py` 和 `update_stats.py`。 |
| Git 同步 | 委托 `maintain.py sync --source stop-hook` 生成 `checkpoint:` 提交并推送。 |

### 后台链路：自动同步守护进程

入口：

```powershell
python harness\auto_sync_daemon.py
pythonw harness\auto_sync_daemon.py
python harness\auto_sync_daemon.py --once
```

它监听 active 仓库文件修改，最后一次变更后空闲 5 分钟触发 `maintain.py sync --source daemon`。

日志写到：

```text
~/.claude/auto_sync.log
```

如果要开机自启，当前仓库提供 `harness/auto_sync_startup.vbs`，可放到 Windows `shell:startup`。

## 健康检查与验证矩阵

| 脚本 | 用途 | 什么时候跑 |
|---|---|---|
| `harness/maintain.py` | 主控 CLI，统一 doctor/fix/sync/daemon/log。 | 日常首选。 |
| `harness/control_panel.py` | Tkinter GUI 主控台。 | 人类查看/操作首选。 |
| `harness/panel_api.py` | 本地事件 API，写入 GUI 可轮询的 JSONL。 | AI/脚本想把状态显示到面板时。 |
| `harness/ai_runner.py` | Claude CLI/Codex/API adapter 层；V1 禁用 execute。 | GUI 或 CLI 需要 AI 诊断/计划时。 |
| `maintain.py doctor` | 记忆仓库日常健康检查（唯一权威入口）。 | 平时最常用。 |
| `harness/verify_all.py` | Harness 总验证，一键检查基础设施并和基线对比。 | 改 Agent/Skill/harness 后。 |
| `harness/verify_docs.py` | 文档一致性检查。 | 改 `/work` 文档流程或任务文档后。 |
| `harness/verify_prompt_system.py` | 检查 `CLAUDE.md`、Agent 配置、Skill 引用一致性。 | 改 prompt/agent/skill 规则后。 |
| `harness/verify_conventions.py` | 跨项目规范硬检查。 | 正式项目交付前。 |
| `harness/task_complete.py` | 收尾总入口，组合规范、基础设施、索引、统计、进度文档检查。 | 正式任务完成前。 |

`verify_all.py --checks` 当前注册的检查包括：`CLAUDE.md`、`MEMORY.md`、Skill junction、Skill YAML、Agent 配置、核心脚本、工程模板、记忆健康度、文档一致性、Git 状态、自动同步。

## Hook 体系

`bootstrap.py install` 会把 hook 配置写进 `~/.claude/settings.json`。当前主要 hook 如下：

| Hook | 匹配 | 脚本 | 目的 |
|---|---|---|---|
| `Stop` | 全部 | `harness/post_task_hook.py --auto-fix` | 任务结束后修索引/统计并尝试同步。 |
| `PreToolUse` | `Bash` | `harness/hooks/dangerous_command_blocker.py` | 拦截危险 shell 命令。 |
| `PreToolUse` | `Write|Edit|MultiEdit` | `harness/hooks/memory_file_protector.py` | 保护记忆文件写入规则。 |
| `PreToolUse` | `Write|Edit|MultiEdit` | `harness/hooks/memory_lint_gate.py` | 写记忆文件时校验 frontmatter。 |
| `PreToolUse` | `Write|Edit|MultiEdit` | `harness/hooks/doc_gate.py` | 在任务文档状态不满足时拦截代码编辑。 |
| `PreToolUse` | `Write|Edit|MultiEdit` | `harness/hooks/diff_backup.py` | 编辑前备份 diff。 |
| `PreToolUse` | `Read` | `harness/hooks/read_large_file_guard.py` | 拦截超大文件读取。 |
| `PreToolUse` | `Agent` | `harness/hooks/agent_prompt_gate.py` | 检查 subagent prompt 质量。 |
| `PostToolUse` | 全部 | `harness/hooks/audit_logger.py` | 记录工具调用审计日志。 |
| `PostToolUse` | `Write|Edit` | `harness/hooks/diff_show.py` | 编辑后弹出 VS Code diff 视图。 |
| `SubagentStart` | 全部 | `harness/hooks/subagent_logger.py` | 记录 subagent 启动。 |
| `SubagentStop` | 全部 | `harness/hooks/subagent_stop_logger.py` | 记录 subagent 停止。 |
| `UserPromptSubmit` | 全部 | `harness/hooks/changelog_inject.py` | 注入 CHANGELOG hint。 |
| `UserPromptSubmit` | 全部 | `harness/hooks/sync_inject.py` | 注入 multi-agent 锁状态。 |
| `UserPromptSubmit` | 全部 | `harness/hooks/route_check.py` | 注入路由提示。 |
| `UserPromptSubmit` | 全部 | `harness/hooks/retrieve_inject.py` | 注入 Context Brief。 |
| `statusLine` | 全部 | `harness/hooks/statusline.py` | 渲染终端状态行。 |

Hook 共享辅助库在 `harness/hooks/_hook_lib.py` 和 `harness/hooks/_task_resolver.py`。

## Agent / Skill / Script 分工

### Agent

| 文件 | 作用 |
|---|---|
| `agents/CLAUDE.md` | 全局约束、启动协议、记忆写入摘要。 |
| `agents/learning-agent.md` | 学习、面试、知识缺口追踪。 |
| `agents/work-agent.md` | 正式生产任务、代码、文档、审查、Bug 定位。 |
| `agents/design-reviewer.md` | 设计文档二次审查，只读。 |
| `agents/guardian-agent.md` | 交付前合规检查，只读。 |

### Skill

| Skill | 作用 |
|---|---|
| `work` | 正式任务入口，管理讨论文档、实现阶段和收尾检查。 |
| `check` | 设计阶段二次 review，输出结构化报告。 |
| `diff` | 交互式查看 edit/write 后积累的 diff。 |
| `bug-locator` | 系统化 Bug 定位流程。 |
| `cpp-tutor` | C++/并发/现代 C++ 学习辅导。 |
| `migrate-executor` | 多文件迁移、重构、回滚验证。 |
| `skill-creator` | 创建或更新 Skill。 |
| `skill-auditor` / `skill-reviewer` / `smoke-test` | Skill 质量、审查、冒烟测试辅助。 |

### Script / Harness

脚本按职责分组理解，不需要逐个背：

| 分组 | 代表脚本 | 作用 |
|---|---|---|
| 部署 | `bootstrap.py`、`deploy_hooks.py`、`deploy_skill_symlinks.*` | 把仓库接到运行时。 |
| 同步 | `auto_sync_daemon.py`、`sync_memory.sh`、`sync_manager.bat` | Git 自动/手动同步。 |
| 记忆维护 | `sync_index.py`、`update_stats.py`、`append_changelog.py`、`changelog_archive.py` | 维护 `MEMORY.md` 和 `CHANGELOG.md`。 |
| 项目流程 | `task_complete.py`、`baseline_compare.py` | 正式任务收尾和流程基线。 |
| 规范验证 | `verify_all.py`、`verify_conventions.py`、`verify_docs.py`、`verify_prompt_system.py` | 检查系统、文档、prompt 和规范漂移。 |
| 上下文生成 | `generate_project_context.py`、`extract_to_memory.py`、`session_report.py` | 拼合项目上下文、提取记忆、生成会话报告。 |
| Hook | `harness/hooks/*.py` | Claude Code tool lifecycle 拦截和审计。 |

## 常见问题与排查

### 我不确定自动同步有没有在跑

先看守护进程：

```powershell
python harness\maintain.py daemon status
```

再看日志：

```text
~/.claude/auto_sync.log
```

如果只想立即同步一次：

```powershell
python harness\maintain.py sync --source manual
```

### `~/.claude` 里的 Skill 或脚本不像是最新的

先检查：

```powershell
python bootstrap.py check
```

如果 junction 或 hooks 不一致，再重新部署：

```powershell
python bootstrap.py install
```

### `MEMORY.md` 索引不对

优先用主控安全修复：

```powershell
python harness\maintain.py fix
```

如果只想重建索引和统计：

```powershell
python harness\sync_index.py
python harness\update_stats.py
```

### README 统计或说明过时

当前 README 不再作为完整工具清单维护，避免频繁漂移。工具细节优先更新本文件。

如果确实需要自动更新 README 统计，可看：

```powershell
python harness\update_readme.py --dry-run
```

### 我想知道这套 harness 当前能力边界

生成维护报告：

```powershell
python harness\maintain.py report --markdown
```

如果要留档到 `~/.claude/logs`：

```powershell
python harness\maintain.py report --markdown --save
```

### AI 面板能不能直接改仓库

V1 不允许。GUI 只显示“只读诊断”和“计划生成”；命令行直接传 `--mode execute` 也会被 `ai_runner.py` 明确拒绝。

### 修改 Agent / Skill / Prompt 后担心规则冲突

跑：

```powershell
python harness\verify_prompt_system.py --report
python harness\verify_all.py
```

如果只想看总检查项：

```powershell
python harness\verify_all.py --checks
```

### 正式任务收尾时该跑什么

在项目目录明确时：

```powershell
python harness\task_complete.py <project_dir> --fix
```

这会组合运行规范检查、基础设施检查、索引同步、统计更新和项目进度文档检查。

## 维护约定

| 规则 | 原因 |
|---|---|
| README 只写总览，不展开完整脚本表。 | 保持人类入口轻量，避免再次变成大杂烩。 |
| 工具说明集中写在 `MAINTENANCE.md`。 | 维护者要找命令时有单一入口。 |
| 脚本行为以源码 docstring 为准。 | 文档可能落后，代码是事实来源。 |
| 改 hook、Agent、Skill 后跑 `bootstrap.py check` 和 `verify_prompt_system.py`。 | 防止运行入口和配置说明漂移。 |
| 改记忆 topic 后按 `memory-rules.md` 判断是否更新 CHANGELOG。 | 保留审计链，避免记忆仓库不可追溯。 |
