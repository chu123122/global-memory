# 记忆变更审计日志

> 每次修改 global-memory 中的任何文件时，必须在此追加一条记录。
> 这是审计追踪的唯一来源——不记录就等于没改过。

---

### [2026-06-24] [MAINT] commit-retrieve-shared-runtime-logs
- 提交 retrieve inject 日志迁移到 shared runtime directory 的配置、脚本、health checks 和回归测试。

### [2026-06-24] [EXP] commit-gm-mcp-semantic-source
- 提交 gm_mcp search/catalog 与 semantic source handling 更新，包括 sources 配置、语义语料处理和对应测试。

### [2026-06-24] [EXP] commit-collab-orchestration-stack
- 提交 experimental collaboration orchestration stack：collab 核心模块、CLI、示例、测试与 review/change-packet 记录。

### [2026-06-24] [MAINT] commit-hooks-obsolete-runtime
- 移除 obsolete runtime hook 条目与对应 hook 脚本，更新 hook/capability manifest、脚本目录和 smoke 验证。

### [2026-06-24] [MIGRATE] commit-skill-flatten-layout
- 提交 Skill 真源扁平化相关源码、同步脚本、catalog/audit 适配与布局文档；保留 skills/<name>/v1 到 skills/<name> 的结构迁移。

### [2026-06-24] [MAINT] ignore local scratch and generated gm_mcp indexes
- 更新 `.gitignore`，忽略 `.tmp/`、`harness/data/gm_catalog.json`、`harness/data/gm_symbols.json`，避免本地 scratch / gm_mcp 生成索引反复进入 dirty tree。

### [2026-06-24] [ARCHIVE] global-memory-pull-architecture 归档
- **来源任务**：D:\ClaudeTasks\archived\global-memory-pull-architecture
- **归档原因**：Phase1-4 complete; gm.search follow-up moved to gm-search-query-issue-analysis
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\global-memory-pull-architecture/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-23] [EXP] gm_mcp structured internal navigation
- 新增 `gm.locate` / `gm.symbol` / `gm.inspect` / `gm.map` / `gm.answer` 工具面和 `harness/gm_mcp/catalog.py`，将内部导航从 `gm.search` fuzzy recall 中拆出。
- 更新 pull-memory tool capability、scripts registry、README、work skill 路由和 gm_mcp 文档；`gm.search` 保留为跨项目/跨会话旧经验召回。
- 修正 README harness 脚本计数为 195；`check_capability_manifest.py --json`、orphan scan、gm_mcp/work 相关测试通过。
### [2026-06-23] [MAINT] clear Claude deployed-extra skill entries
- 清理 `audit_skill.py` 报出的 7 个 Claude runtime `deployed-extra` 入口：`codex-work`、`first-principles-explain`、`hv-analysis`、`khazix-writer`、`note`、`xdap-test-device`、`xdoa-skill`。
- 仅移动 runtime 入口到 `C:\Users\XINDONG\.claude\skills_disabled_20260623\_manual_deployed_extra_cleanup\`，未删除 `.agents\skills` 或 `.codex\skills` 真源。
- 验证后 `deployed_extras=0`，`bootstrap.py check` 仍全绿。
### [2026-06-23] [MAINT] remove migrate-executor skill
- 删除 `D:\global-memory\skills\migrate-executor` 真源，并移除 Claude/Codex runtime 链接；删除前备份到 `C:\Users\XINDONG\.codex\skills_disabled_20260623\_manual_removed_sources\migrate-executor\`。
- 更新 `agents/work-agent.md` 与 `docs/guide/MAINTENANCE.md`，不再把多文件迁移路由到 `migrate-executor`；这类任务回到 `/work` + 现有测试/脚本验证。
- 运行 catalog 刷新后，默认保留 skill 集不再包含 `migrate-executor`。
### [2026-06-23] [MAINT] runtime skill exposure cleanup
- 将 Claude runtime extra skill 入口移至 `C:\Users\XINDONG\.claude\skills_disabled_20260623\`（91 个入口，含 manifest），Codex runtime extra skill 入口移至 `C:\Users\XINDONG\.codex\skills_disabled_20260623\`（85 个入口，含 manifest）；保留系统入口、`codex-work` 与 10 个核心 `D:\global-memory\skills` 链接。
- 精简 `D:\global-memory\skills` 真源：移除 `learning-opportunities`、`collab`、`skill-reviewer`、`smoke-test`、`skill-creator`；删除前备份到 `C:\Users\XINDONG\.codex\skills_disabled_20260623\_global_memory_removed_sources\`。
- 运行 `python -B harness\generate_catalog.py` 刷新 `agents/README.md`、`skills/README.md`、`harness/README.md`；回滚可将 disabled 目录条目移回原 runtime 路径，并从备份或 Git 恢复上述 5 个真源 skill。
### [2026-06-20] [EXP] collab Phase 12 product entry/readiness gate
- 新增 `harness/collab/entry.py` 与 `harness/scripts/collab_entry.py`：提供 runbook、readiness、smoke 入口，生成 plan/blueprint/events/store/router/MCP/readiness artifacts。
- readiness gate 明确 `verdict=not_ready`，`client_manifest_readiness_changed=false`；Codex/Claude E2E、真实 MCP registration、桌面/web UI 未验证时保持 blocker/warning。
- 新增 `harness/tests/test_collab_entry.py`；targeted tests `6 passed`，full collab regression `111 passed`。
- 同步 manifest、capabilities、scripts registry、README/catalog、collab skill；仍不提升 readiness。

### [2026-06-20] [EXP] collab Phase 11 router/report loop
- 新增 `harness/collab/router.py` 与 `harness/scripts/collab_router.py`：event-sourced router snapshot/enqueue/ack/fail/retry/report 操作，显式记录 correlation id、dedupe key、ack/failure/retry/duplicate。
- 扩展 `harness/collab/bridge_host.py` reducer，让 `router_message_*` events replay 到 materialized UI model：router message/failed/duplicate/acked 计数均可见。
- 新增 `harness/tests/test_collab_router.py` 与 `harness/tests/test_collab_router_cli.py`；targeted tests `6 passed`，full collab regression `105 passed`。
- 同步 manifest、capabilities、scripts registry、README/catalog、collab skill；仍不提升 readiness。

### [2026-06-20] [EXP] collab Phase 10 MCP-style bridge beta
- 新增 `harness/collab/mcp_bridge.py` 与 `harness/scripts/collab_mcp_bridge.py`：输出 `create_worker/send_to_worker/worker_status/read_worker/ingest_worker_report` MCP-style schema/probe，并支持对 events JSONL 执行 tool call。
- 扩展 `harness/collab/bridge_host.py` 增加 `create_bridge_worker()`，让 Phase 10 `create_worker` 可追加 worker row 但不启动进程。
- 新增 `harness/tests/test_collab_mcp_bridge.py` 与 `harness/tests/test_collab_mcp_bridge_cli.py`；targeted tests `7 passed`，full collab regression `99 passed`。
- 同步 manifest、capabilities、scripts registry、README/catalog、collab skill；边界保持 `real_mcp_server_verified=false`，不接管主 Codex/Claude CLI，不提升 readiness。

### [2026-06-20] [EXP] collab Phase 9 worker runtime alpha
- 新增 `harness/collab/worker_runtime.py` 与 `harness/scripts/collab_worker_runtime.py`：non-spawning runtime request、显式 `--allow-spawn` command-worker run、stdout/stderr/status 捕获、stable JSON error contract。
- 扩展 `harness/collab/bridge_host.py` 支持 `worker_runtime_result` event，event log replay 后 materialized model 显示 `phase=9`、`real_worker_lifecycle=true`、`runtime_run_count` 和 report pointer。
- 新增 `harness/tests/test_collab_worker_runtime.py` 与 `harness/tests/test_collab_worker_runtime_cli.py`；targeted tests `7 passed`，full collab regression `92 passed`。
- 同步 `harness/capability_manifest.json`、`docs/capabilities.md`、`docs/scripts-registry.md`、README/catalog、`skills/collab/v1/SKILL.md`；manifest/orphan/catalog checks 均 `verdict=ok`，脚本数 `182/182`。
- 边界：当前证明 operator-configured command-worker 非 manual lifecycle；Codex/Claude E2E 未验证，不提升 `harness/client_manifest.json` readiness。

### [2026-06-20] [FIX] collab JSON error contract completion
- 修复 reviewer blocking：`harness/collab/errors.py` 的 `error_payload()` 现在输出完整 additive contract：`ok:false`、`kind`、`error`、`error_code`、`message`、`details:{}`，同时保留旧 `kind/error/error_code` 字段。
- 补强 `harness/tests/test_collab_error_contract_cli.py`，覆盖 `collab_plan/state/replay/dispatch/queue/recover/ui_shell.py --json` 错误输出；成功 JSON payload 不变。

### [2026-06-20] [EXP] collab Phase 5 optional UI shell contract
- 新增 `harness/collab/ui_shell.py` 与 `harness/scripts/collab_ui_shell.py`：从 Phase 4 `plan/state/queue/recover/dispatch/report` artifacts 生成 deterministic UI shell JSON view model 与 Markdown dashboard。
- UI shell contract 明确 `headless=true`、`spawns_process=false`、`readiness=experimental`、只读 mutation policy，并把 XDMaker `CollaborationModeToggle` / `OrcaSplitView` 限定为概念/布局可复用，不复制产品壳、localDb 或进程启动链。
- 新增 `examples/collab/run_ui_shell_flow.py`，串起 minimal flow 后生成 `ui-shell.json` / `ui-shell.md`，证明 UI shell 不绕过 state/queue/recover/error contract。
- 同步 `harness/capability_manifest.json`、`docs/scripts-registry.md`、README 脚本计数与 catalog；能力仍为 experimental，不提升 `harness/client_manifest.json` readiness。

### [2026-06-20] [EXP] collab Phase 4 recovery / queue / errors core
- 新增协同插件稳定错误契约：`harness/collab/errors.py`、现有 collab CLI JSON error 保留 `kind/error` 并新增 `error_code`。
- 新增 host-neutral 多 worker 队列：`harness/collab/queue.py` + `harness/scripts/collab_queue.py`，支持 create/show/lease/requeue/complete/fail、labels、worker concurrency、retry exhaustion；不启动 worker。
- 新增恢复分析：`harness/collab/recover.py` + `harness/scripts/collab_recover.py`，覆盖 stale running、plan/state/queue mismatch、schema/version 不匹配、state/queue 冲突。
- 新增可执行示例 `examples/collab/run_minimal_flow.py` 与 README，串起 plan → state → queue → recover → dispatch dry-run。
- 同步 `harness/capability_manifest.json`、`docs/scripts-registry.md`，并补 collab errors/queue/recover/CLI 测试；能力仍为 experimental，不提升 `harness/client_manifest.json` readiness。

### [2026-06-18] [DOC] 通道契约表 + 结构审查勘误（P0 结构性调整）
- `rules/接入索引.md` 新增 §0.1「投递通道契约」：内容类型→通道（注入 push / 检索 pull / 动作点门 gate）映射表 + 3 条钉死契约（不跨通道重复 / 检索恒为候选供给 / 门只拦确定性违规）+ 两引擎分立声明。防止每次新需求重拍"该上 hook 还是 skill 规范"的元纠结。
- **结构审查结论（design-reviewer 独立）**：地基没病。张力1（两检索入口同后端）**事实错误**（grep 证实 retrieve 字面引擎零向量、gm_search 才是语义引擎），必须纠否则误导"统一两套入口"大重写；张力2（通道无显式模型）唯一真结构性项=补本表；张力3（worker 真空）焊点②即正解；张力4（反馈断）gm_mcp 接朴素聚合；张力5（检索不裁决）已做对写进本表。所有改动=1表+①②+1只读脚本，无引擎/hook 引擎改动。
- 勘误：`design/整合方案-gm_search融入框架.md` §2.3"底层都吃 harness/semantic"、§5"①与 retrieve 同后端"两处事实错误已纠正（retrieve 字面 vs gm_search 语义，① 重叠远小于原判、条件化降为非必需）。
- 落盘：`D:/ClaudeTasks/active/global-memory-pull-architecture/design/结构性调整方案.md`。纯文档零代码；后续 P1（焊点①② + gm_mcp 聚合脚本）待确认。

### [2026-06-18] [FEAT] bootstrap 可迁移性一键安装（B 线）+ knowledge 落盘
- `bootstrap.py install/check` 扩展 5 缺口：前置检测（Windows/Python≥3.12/git/Ollama，缺则报错+winget 引导、不静默装系统件）；pip 装 `requirements.txt`（mcp/PyYAML，numpy optional）；Ollama tags 检测 + bge-m3 缺失自动 pull；`python -m harness.semantic.cli build` 索引重建；Codex（config.toml 幂等写 `[mcp_servers.global-memory]`，sys.executable+REPO 零硬编码，改前备份）+ Claude Code（仅走 `claude mcp get/add -s user`，不手搓 ~/.claude.json）双端 MCP 注册。check 扩依赖/Ollama+模型/索引/双端注册校验。
- **幂等修正**（tester 终验 No-go 点）：`replace_junction` 在已指向正确 source 时跳过；`sync_claude_settings` 仅 hooks/statusLine 两 key，一致则跳过（不堆 settings.json.<ts> 备份），漂移才备份+刷新（保留用户其它字段）。bootstrap 主体本不幂等的老问题连带修。
- 新增 `requirements.txt` + `harness/tests/test_bootstrap_portability.py`（9 测，沙盒+幂等覆盖）。
- 新增 `knowledge/knowledge_gm_search_threshold_gate_unstable_small_corpus.md`：gm_search 实测坐实"阈值-only gate 在小杂库不稳"+ 穷举 golden 方法论（措辞漂移/injection-aware/FP-约束标定）+ 三次"测错战场"反模式。
- 验证：tester 真隔离 install→install→check，第二轮全"已指向/已一致跳过"、备份不堆积、真实 ~/.claude.json+config.toml SHA256 前后一致不污染；34 测绿、quality_gate PASS。
- 目标：干净 Win 机 `git clone && python bootstrap.py install` 一条命令配好整套（harness junctions + gm_search MCP 双端 + Ollama 向量 + 索引），`check` 全绿。Windows→Windows；前置软件检测+引导不静默装系统件。

### [2026-06-18] [TUNE] gm_search abstain 阈值 0.590→0.622（穷举 golden 证伪 0.590）
- 穷举到 74 正/20 负后，0.590 被 JS TypeError、Python ImportError、Docker permission 等通用技术问法击穿（3/20）；升至 `LOW_CONFIDENCE_THRESHOLD=0.622` 达 FP=0。分离裕度仅 0.0029，仍是剃刀边缘，根治待本地 LLM rewrite/query-intent。

### [2026-06-18] [TUNE] gm_search abstain 阈值标定 0.62→0.590
- 基于 golden 21 正 + 10 负与 tester 过拟合压测收口：`LOW_CONFIDENCE_THRESHOLD=0.590`，正例 acceptable 投递 17→19/21、golden 负例 0 击穿、新负例 0/15 击穿；该点是小语料剃刀边缘操作点，稳健解仍待本地 LLM 改写/意图判断。

### [2026-06-18] [FEAT] gm_search deliver-gate 收口（option B）+ 双端注册接入框架
- `gm.search` deliver-gate 收口：主投递只剩 `pointers`（低置信 abstain + 按 path 去重 + require-vector + top-3 cap，默认 `DEFAULT_DELIVERED_UNIQUE_PATHS=3`）；`intent_matches`/`suggested_answer_refs` 降到 `raw`，避免冒充"答案"误导上下文。`debug.deliver_gate` 记 demote/cap 审计字段。
- 定调 **call 可强制、deliver 必过门**，限定跨项目/跨会话/换说法召回（repo 内仍用 grep）。去噪僵局裁决：纯检索侧 cosine 门否决（关 vector_only 会赔掉跨语言/换说法召回，UE RAG 模板带远程 LLM 都没走通）；本地 LLM 查询拆解记升级触发器；AI 自筛采纳（连 UE 团队都退回此路）。
- 注册：Codex `~/.codex/config.toml` + Claude Code user-scope（`claude mcp add -s user global-memory`，`Connected`，所有项目可见）。代码落主工作树 `harness/gm_mcp/`。
- 验证：tester 三轮独立复验，终验 Go——recall 16/16（p15 在 rank3 未被 N=3 截）、abstain 5/5、主字段纯 pointers；17 单测绿、quality_gate PASS、禁区 diff 空。

### [2026-06-18] [ISSUE] 长讨论方案漂移/无序度发散
- 新增 `issues/ISSUE-2026-06-18-long-discussion-plan-drift-entropy.md`：记录长讨论/多次 compact 后任务原始出发点、阶段卡与 HANDOFF 漂移，导致反复 re-litigate 和绕回原点；候选修复包括不可变北极星锚、阶段卡同步门和 Context Brief 注入锚点原文。

### [2026-06-17] [FIX] pull-mode MCP reviewer delta
- 修复 `gm.search` 置信度语义：`rank_score` 与 semantic `confidence` 分离，lexical-only 不再用 RRF/authority score 充当置信度，离题负问顶部 lexical-only 时保持 `low_confidence=true`。
- 修复 `gm.rule` 过强裁决：每条结果新增 `verdict_basis`，弱语境/缺直接 topic alias 时 verdict 降为 `informational`。
- `harness.semantic.engine` 向量缓存增加 optional numpy matrix fast path；无 numpy 时保持纯 Python fallback，不新增硬依赖。

### [2026-06-17] [EXP] pull-mode global-memory MCP tools Phase A
- 新增 `harness/gm_mcp/`：本地 stdio MCP MVP，暴露 `gm.search` / `gm.rule`；日志 JSONL 显式记录 `source`/`mode`/`latency_ms`，默认 `source=natural`，self-test/test 可覆盖。
- `gm.search` 复用 `harness.semantic` + `harness/semantic/fixtures/intent_bank.json`，使用 open acceptance/debug 输出，低置信只标记不过滤；semantic engine 增加 query_vector 复用与进程内只读向量缓存以避免每次重复 embedding/BLOB reload。
- `gm.rule` 使用 `harness/gm_mcp/rules.yaml` 覆盖 R18/R17/R9/记忆写入/R13/工具登记 6 条规则，并校验 `source_path` + `anchor_text` 可 grep。
- 新增 experimental capability `pull_memory_tools`，同步 `docs/scripts-registry.md` / `docs/capabilities.md` / README 脚本计数；自动注入链 `harness_retrieve.py`、hooks、`client_context.py` 未改。

### [2026-06-17] [EXP] curated intent routing Phase 1 测量
- 新增 `harness/semantic/fixtures/intent_bank.json`：小规模人工策展 intent bank，分离 train paraphrases 与 held-out positives，承载 Phase 1 Q2Q 可分性验证。
- 任务私有脚本 `D:\ClaudeTasks\active\global-memory-curated-intent-routing\test\measure_intent_bank.py` 复用 bge-m3 与 SQLite chunk vectors，输出 Q2doc/Q2Q 分布、过拟合幅度和 τ 扫描；未接入生产 retrieve/hook。
- 验证：`python -m harness.semantic.cli build` PASS；`python D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/measure_intent_bank.py ...` PASS；`python -m pytest D:/ClaudeTasks/active/global-memory-curated-intent-routing/test/test_measure_intent_bank.py -q` 3 passed。
### [2026-06-17] [ISSUE] context-brief issue 补现场实例
- `issues/ISSUE-2026-06-16-context-brief-no-usefulness-feedback-loop.md` 追加「## 现场实例（2026-06-17）」：(A) 该轮注入 3 条指针、2 条为 `concept:ui` alias 噪声（aik-refactor-ui，与 loop/agent 无关），`pointer_rate=0` 混淆"噪声 vs 摘要够用"；(B) AI 自主 Read 未注入的 `knowledge_skill_design.md`（探索期过度读），连 injection 账本都不记。两面印证反馈回路缺口。

### [2026-06-17] [DECISION] 多 agent 自动调度采用混合模型
- 新增 `decisions/decision_multi_agent_dispatch.md`：静态角色目录 + AI 从目录挑 + 代码绑定模型并 orca 派生；v1 起手 dev/reviewer/explorer 三角色用骨折 gpt-5.5；护栏(API key 模式/worker 硬上限/计划过人)；实现待走 `/work`。
- 新增 `knowledge/knowledge_loop_engineering_harness_mapping.md`：loop engineering(Cherny 红杉 AI Ascent 2026)映射本 harness 双轴——单 agent 已满配，缺口=多 agent loop。
- 来源：用户分析 loop engineering 推特视频 + 提出"自动划分 agent、按需派生骨折 gpt-5.5"需求；讨论确定混合调度方向。

### [2026-06-16] [ARCHIVE] global-memory-semantic-retrieval-survey 归档
- **来源任务**：D:\ClaudeTasks\archived\global-memory-semantic-retrieval-survey
- **归档原因**：PoC 完成: 本地语义检索召回验证成立(Recall@10=1.0 vs baseline 0), abstain 非 LLM 不可解(两次实测), 小杂语料 ROI 低, 决策暂不部署; 代码+认知归档备查
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\global-memory-semantic-retrieval-survey/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-16] [TRIAGE] issue 与 feedback 批量消化
- `ISSUE-2026-06-03-registry-single-source-autoindex` 改为 `routed`：当前 drift/双登记 partial fix 已完成，完整 single-source SoT 改为后续正式 `/work` 范围。
- `ISSUE-2026-06-03-rules-layer-minor-backlog` 改为 `deferred`：该文件是低优先级 minor backlog 汇总，未来按单条触发另开 task/work。
- `feedback_diff_workflow.md` 改为 `superseded`，因为默认 VS Code diff 自动弹窗 hook 已关闭；`feedback_skill_deployment_layout.md` 保持 active，但更新为 `~/.claude/global-memory` 真源 + runtime junction/sync 的当前部署表述。

### [2026-06-16] [FIX] triage A 批次关闭 feedback 与 doctor warning
- 将 `feedback_archive_feedback_loop.md`、`feedback_harness_maintenance_flow.md` 标记为 `superseded`，追加关闭原因与验证命令；两条均通过 `triage_inbox.py --verify-close ... --json`。
- `agents/CLAUDE.md` 补充最小指令优先级与 Agent 扩展边界说明，清理 `verify_prompt_system.py` 的优先级 warning。
- `harness/scripts/task_experience_index.py` 改用 `config.CLAUDE_TASKS_ROOT`，并运行 `fix_hardcoded_paths.py --fix` 将旧 `D:/global-memory` 文档引用规范到 `~/.claude/global-memory`；补 `test_warning_cleanup.py` 回归。

### [2026-06-16] [FIX] 清理 registry/capability drift 与 prompt verifier blocker
- 删除误落到 `rules/Untitled.md` 的个人秋招顾问临时 prompt；该文件不是 rules 层规范，未作为规则提交。
- 用 `harness/scripts/register_script.py` 补齐脚本登记/能力归属：`readback_audit.py` → `health_diagnostics`，`scripts/check_phase_evidence.py` + `scripts/change_packet.py` → `task_lifecycle`，`scripts/task_experience_index.py` → `memory_repository_maintenance`；`scan_orphan_scripts.py --strict` 与 `check_capability_manifest.py` 均恢复 PASS。
- 更新 README harness 脚本计数 140 → 143；调整 `verify_prompt_system.py` 的 CLAUDE.md 必备锚点为当前“全局铁律”结构，避免要求已迁出到 rules/skills 的旧启动/Agent 大段提示词；`maintain.py doctor --json` 结论恢复 `can_proceed`。

### [2026-06-16] [FEAT] triage close verify 机械门
- 扩展 `harness/scripts/triage_inbox.py`：新增只读 `--verify-close <path>`，输出 `triage_close_verification.v1` JSON，校验 issue/feedback 状态已离开 inbox 且正文有关闭/验证/drop/supersede 证据；PASS=0、FAIL=1。
- 扩展 `harness/tests/test_triage_inbox.py`：覆盖 open issue、closed issue 无证据、closed issue 有验证命令、active feedback、dropped/superseded feedback 有 reason，并确保默认 scan 行为继续通过。
- 更新 `skills/triage/v1/SKILL.md` Step 5 与 `docs/scripts-registry.md`：关闭来源后必须运行 verify-close，PASS 才算 close source 成功；该门只读、不自动修改来源。

### [2026-06-15] [FEAT] script registry 双登记自动化 MVP
- 新增 `harness/scripts/register_script.py`：默认 dry-run，`--apply` 才写回；校验 harness 相对 `.py` 路径、脚本存在性、capability id、触发方和失败动作，一次性更新 registry Markdown 与 capability manifest。
- 新增 `harness/tests/test_register_script.py`：覆盖 dry-run 不写、apply 双登记、重复注册幂等、capability/脚本/越界错误不写，以及 monkeypatch fixture 下复用现有 drift checker 逻辑验证注册后无 unregistered/unassigned。
- 用新命令注册自身：`docs/scripts-registry.md` 增加 `scripts/register_script.py`，`harness/capability_manifest.json` 归入 `release_readiness`；来源 issue 仅标记 partial progress，完整 single-source SoT 仍保留后续。

### [2026-06-15] [FIX] archive commit 复盘强制门
- `harness/scripts/archive_task.py --commit` 在 `cmd_check()` PASS 后、物理移动前执行 retrospective gate：`Phase*.md >= 4` 必须存在并通过 `core/复盘.md` 5 护栏 lint。
- `<4 Phase` 小任务缺复盘时，显式 `--commit --yes` 会写入最小跳过声明“本任务无重大踩点，跳过复盘”，保证归档产物有机器可查留痕；若已有复盘仍需 lint PASS。
- 新增 `harness/tests/test_archive_task.py` 覆盖大任务缺复盘拒绝、大任务复盘 lint fail 拒绝、小任务跳过留痕、`--extract` lint 不回退；关闭 `issues/ISSUE-2026-06-04-archive-commit-skips-retrospective-gate.md`。

### [2026-06-15] [FEAT] 轻量 `/triage` 问题消化 MVP
- 新增 `skills/triage/v1/SKILL.md`：定义 scan inbox -> AI propose -> user choose `{修/task/work/drop}` -> execute/route -> verify -> close source 的轻量问题消化流程。
- 新增 `harness/scripts/triage_inbox.py` 与 `harness/tests/test_triage_inbox.py`：只读扫描 open issue 与 active feedback，输出 `triage_inbox.v1` JSON；覆盖 open/closed issue、active feedback、输出契约和只读行为。
- 更新 `docs/scripts-registry.md` 与 `harness/capability_manifest.json`：登记 `triage_inbox.py` 为 Manual / REPORT，并归入 task lifecycle capability。
- 更新 `bootstrap.py`：安装时把仓库 `skills/*/v1` 同步到 Codex skill root，同时保留 Claude Code skill junction；`/triage` 可由 Claude Code 与 Codex 共同发现使用。
- 方向校准：撤回旧 `archive_task.py --triage/--close` 重型状态机路线；归档候选仅作为后续可选输入源。

### [2026-06-15] [FIX] Work 意图方向校准门
- 修复 `harness/work_context_pack.py --intent`：无显式 `--task` 且命中高置信新 work/task 意图时，即使 cwd/task_resolver 已解析到旧 task，也返回 `intent_guard.action=create_task_or_confirm`，提示新开 task 或显式确认继续。
- 新增/更新 `harness/tests/test_work_skill_tdd_rules.py` 回归：真实 `/triage` -> work 交接串、cwd/task_resolver/session/no-task、显式 `--task`、普通继续、`继续维护当前 task` 中文边界。
- 关闭 `issues/ISSUE-2026-06-15-work-discussion-before-implementation-gap.md`；验证：`pytest harness/tests/test_work_skill_tdd_rules.py -q` 21 passed，真实复现命令 WARNING，显式 `--task` PASS，限定 quality gate PASS。

### [2026-06-15] [FEEDBACK] Archive Feedback Loop 缺口入 feedback 并新开任务
- 新增 `feedback/feedback_archive_feedback_loop.md`：归档复盘抽取候选不能只停在 `_archive/extract_candidates.md`，必须进入 triage -> issue/knowledge/decision/task/drop -> verification -> close。
- 新开任务 `archive-feedback-loop`：设计并实现归档复盘反馈消费闭环；触发案例为 `D:\ClaudeTasks\archived\global-memory-entry-pr-gate\_archive\extract_candidates.md`。

### [2026-06-15] [ARCHIVE] global-memory-entry-pr-gate 归档
- **来源任务**：D:\ClaudeTasks\archived\global-memory-entry-pr-gate
- **归档原因**：完成：接入式 Change Packet 前置门落地，流程缺口保留 issue 后续处理
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\global-memory-entry-pr-gate/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-15] [UPDATE] 关闭 VS Code diff 自动弹窗 hook
- 用户要求关闭“修改文件后弹出 VS Code”的 hook；从 `harness/hook_manifest.json` 移除 `PostToolUse Write|Edit -> hooks/diff_show.py` 注册。
- 保留 `harness/hooks/diff_show.py` 文件和 `diff_backup.py` 备份能力，只停止默认 runtime 自动弹窗。
- 同步 `bootstrap.py` runtime 检查、`docs/hook-chain.md`、`docs/主循环与日志地图.md`、`docs/scripts-registry.md`；后续需通过 `bootstrap.py install` 渲染到 `~/.claude/settings.json`。

### [2026-06-15] [ARCHIVE] work-user-confirmation-after-design-review 归档
- **来源任务**：D:\ClaudeTasks\archived\work-user-confirmation-after-design-review
- **归档原因**：用户确认任务完成并要求归档
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\work-user-confirmation-after-design-review/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-15] [FEAT] Change Packet 前置门实现（task: global-memory-entry-pr-gate Phase 2）
- 新增 `templates/change_packet.md.tmpl`：Change Packet 模板（动机/范围/方案/证据/风险/意图对齐）
- 新增 `harness/scripts/change_packet.py`：`new` 建包 / `validate` 校验 / `status` 列表的确定性 CLI
- 新增 `harness/tests/test_change_packet.py`：29 项单元测试覆盖合法/缺字段/无效值/CLAUDE.md 保护/模板提示语/Scope 范围过滤/证据警告/模板
- 修改 `AGENTS.md`：增加「改动前置门（Change Packet）」节，作为仓库维护入口的前置 intent/scope gate
- 修改 `docs/scripts-registry.md`：注册 `change_packet.py`（Manual / REPORT）
- 修改 `docs/guide/CONTRIBUTING.md`：§3.7 Change Packet CLI 用法
- 新建 `quality/change-packets/` 存储目录，并用 `quality/change-packets/20260615-100000-change-packet-gate.md` dogfood 本次改动
- 新增 Tier 3 质量证据：`quality/verification.md` + `quality/reviews/{correctness,test-quality,risk-security,maintainability}.md`
- 设计约束：Change Packet = 实现前 intent gate；quality_gate.py = 实现后 correctness gate；互补不重叠

### [2026-06-15] [ISSUE] 记录 work 实现前讨论阶段方向校准缺口
- 新增 `issues/ISSUE-2026-06-15-work-discussion-before-implementation-gap.md`：用户纠偏指出旧 task 方向错误，真正目标是 global-memory 接入式入口 prompt + PR-shaped 改动过滤；记录 `/work` 在实现前讨论阶段缺少 intent alignment / 方向校准门，后续需在进入实现或派生 worker 前产出可追溯校准结论。

### [2026-06-10] [DOCS] 收尾 current_task 整改：测试重指强校验 + SKILL.md 措辞 + 重渲染 codex
- `harness/tests/test_work_skill_tdd_rules.py`：两个 `test_work_skill_*` 从只读已瘦身的 SKILL.md 重指到内容现在的家——`rules/执行层.md`（`Red→最小实现→Green`/`后补测试不算 TDD`/`改代码必有测试或替代验证`）+ `docs/task-lifecycle.md`（`无法先写测试`→`替代验证`）；恢复强校验（不再因 SKILL.md 瘦身而变薄），加 `EXEC_LAYER`/`TASK_LIFECYCLE` 常量
- `skills/work/v1/SKILL.md`:62/75：`.current_task` 措辞由「legacy fallback / 多终端会互覆」改为「纯信息位、已无 reader 读取、create_task 仍写」；点明 `.session_tasks/<session_id>` 是 statusline 显示 + brief/pack 解析的唯一来源
- 重渲染 `~/.codex/skills/codex-work/SKILL.md`（SKILL.md 是渲染源；verify_all 的 codex 漂移门已从 drift → up-to-date）
- 全量 **351 passed, 9 skipped**

### [2026-06-10] [FIX] retrieve_inject + work_context_pack 去全局回退（堵第二污染出口 + intent_guard 迁移）
- `harness/hooks/retrieve_inject.py`：`_resolve_task` 删全局 `.current_task` 回退**和** `active_tasks[0]` 盲选（前者换后者只是换个错 task）；只留 session 标记 + cwd→owner（均 per-terminal）；删 `CURRENT_TASK_FILE`/`_read_current_task_file`；无匹配→`unknown`
- `harness/work_context_pack.py`：`resolve_task` 删 `.current_task` 分支 + 删 `read_current_task_file`
- **intent_guard 迁移**（防静默删护栏，需用户知会）：`build_report` 的「新任务意图却复用上个 task 指针」警告从 `reason=="current_task_file"` 改 `=="session_task_file"`——current_task 不再被解析后原分支必成死代码，迁到 session 标记保住护栏语义
- 测试：`test_retrieve_inject_*` / `test_work_context_pack_warns_*` 改用 session 标记复现；`json_query_does_not_clear_session_marker` 删 current_task mock；全量 **351 passed, 9 skipped**
- 实测：本会话 brief task `piano-sheet-skill`（全局串味）→ `unknown`；有标记旧会话正常解析自身 task
- 旁修：2 个 `test_work_skill_*` 预存失败（TDD 细节已从 SKILL.md 搬到 `执行层.md`/`task-lifecycle.md`，测试断言的旧短语全 repo 已无）→ 对齐到 SKILL.md 现存引用行（`改代码走 TDD`/`Red→最小实现→Green`/`改代码必有测试或替代验证`），测试因此变薄
- **未改**：SKILL.md:62/75 仍把 `.current_task` 称「legacy fallback」，现已无任何 reader 读它（纯信息位），措辞过时待清

### [2026-06-10] [FIX] statusline 去全局回退，.current_task 降级为信息位（消多终端 task 串味）
- `harness/hooks/statusline.py`：`resolve_task_name()` 只读 `.session_tasks/<session_id>`，删除对全局 `.current_task` 的回退 + 删 `CURRENT_TASK_FILE` 常量；无 session 标记→显示空（宁空勿错）
- `harness/tests/test_work_skill_tdd_rules.py`：`test_statusline_*` 重写为新契约——terminal-b 无标记不被 terminal-a 注册污染（实测本会话从误显 piano-sheet-skill → 空）
- 根因：session 标记写得稀（仅 create_task 时写），全局文件既被无条件写又当兜底读 → 跨终端最后写赢
- **未动**（同款回退仍在，Context Brief 仍会串味）：`retrieve_inject.py` `_resolve_task` + `work_context_pack.py`；session 标记写勤 + `.session_tasks/` 清僵尸（现 8 个，2 个空）均未做
- 旁现：`test_work_skill_{requires_phase_tdd_loop,has_code_change_test_rule}` 预存失败（SKILL.md 措辞漂移 vs 测试断言），与本改无关

### [2026-06-10] [DOCS] 记忆写入省 token 行为约束（只查重+凭记忆写+lint兜底）
- `feedback/feedback_collaboration_meta.md` 加 §5：写/改 global-memory 禁止预读 conventions/lint/triggers/CHANGELOG 当仪式；正确三步=查重(轻) + 凭记忆写 + lint 兜底
- 用户反馈：记忆写入时为"防格式错"重读 ~500 行规格属无意义 token 消耗，违背确定性铁律 #8
- 关联：`feedback/ai-test-failure-modes-four-defenses.md`（同属"确定性门替代 AI 预防"）+ collaboration_meta §2（主动记忆）

### [2026-06-10] [DOCS] 记录 Tier2 证据门防伪决策（治标已落/治本挂起）
- 新增 `decisions/decision_quality_gate_evidence_antifake.md`：Tier2 `test-quality` 强证据门可被假证据糊弄（Goodhart 递归，`/code-review` 8 findings 确认），黑名单治标已落、事实门治本挂起 + 复审条件
- **审计补记 TODO**：本决策所述 Tier2 门*代码*改动（`quality_gate.py`/`quality_gate.yaml`/tests/`QUALITY_GATE.md`/VERSION→1.5.0）已在 live 但本 CHANGELOG 顶部缺其条目，待 commit 时补记
- 关联：`feedback/ai-test-failure-modes-four-defenses.md`（RED-先行防线的机械化落点）

### [2026-06-07] [DOCS] CLAUDE.md 加语言偏好铁律
- `agents/CLAUDE.md`：头部加「思考用英文，回复用中文」（对齐 `feedback_language_preference` 记忆）

### [2026-06-07] [FIX] skill-creator quick_validate 读 SKILL.md 显式 utf-8
- `skills/skill-creator/v1/scripts/quick_validate.py`：`read_text()` → `read_text(encoding='utf-8')`，避免 Windows cp936 默认编码读 UTF-8 frontmatter 崩/乱码

### [2026-06-07] [FEAT] /work 四契约重排 + done 证据打回门（补提交 codex-work-flow-contract-tightening 遗留）
- work 流程用 SPEC「四契约」(任务/验收/执行/权威) 重排：`skills/work/v1/SKILL.md`「## 四契约」+ `docs/task-lifecycle.md` §2 四契约 Phase 卡 + done 打回规则(验收项↔证据 1:1) + 权威裁决链(人工>可执行证据>设计>代码>自动状态)
- 新增 `harness/scripts/check_phase_evidence.py`（done 前机械校验每验收项有 Green/证据）；`workflow.md` 模板字段↔契约映射；`decision_work_mode_workflow.md` 补 04 更新 note；task_template 路径修正 → skills-repo/_bootstrap
- 附带发现：`fixes/fix_mechanical_check_silence_not_success`（机械检查定位不到目标须显式失败，勿静默跳过）+ `issues/ISSUE-2026-06-04-archive-commit-skips-retrospective-gate`（archive --commit 可绕 5 护栏复盘门）
- `.gitignore` 忽略 `**/work-workspace/`（skill eval sandbox scratch）

### [2026-06-04] [ARCHIVE] harness-3layer-architecture 归档
- **来源任务**：D:\ClaudeTasks\archived\harness-3layer-architecture
- **归档原因**：完成
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\harness-3layer-architecture/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-04] [ARCHIVE] global-memory-stale-cleanup 归档
- **来源任务**：D:\ClaudeTasks\archived\global-memory-stale-cleanup
- **归档原因**：完成：清理 global-memory 陈旧文件 + 退役 legacy 工程流程模板子系统（提交 148156c）
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\global-memory-stale-cleanup/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-04] [ARCHIVE] codex-work-flow-contract-tightening 归档
- **来源任务**：D:\ClaudeTasks\archived\codex-work-flow-contract-tightening
- **归档原因**：四契约重排 work 流程完成：SKILL 四契约骨架+done打回+裁决链、Phase卡模板四契约小节、check_phase_evidence 机械检查、删孤儿旧副本；经验抽 fixes/silence-not-success
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\codex-work-flow-contract-tightening/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-04] [CLEANUP] 退役 legacy 工程流程模板子系统 + 清孤立旧模板

- **背景**：用户发起 global-memory 陈旧文件清理（task `global-memory-stale-cleanup`）。审计发现用户初判的两个例子（`templates/WORKFLOW.md`、`agents/work-agent.md`）中 work-agent.md 实为活 subagent 定义（保留），但确实存在真死重量。
- **删孤立旧模板（0 活依赖，旧 harness 残留）**：`templates/HANDOFF.md`、`HARNESS_REVIEW.md`、`SKILL_LIFECYCLE.md`。`templates/` 现仅余 `doc-templates.md` + 4 个 `memory_*.tmpl`（均活）。
- **退役 legacy 工程流程校验子系统**：`verify_workflow.py` 校验的是 `docs/SPEC.md`+`docs/PROGRESS.md`+`docs/dev-log/phaseN.md` 项目约定——比 task-lifecycle v1/v2 都早的第三套，无任何现役任务命中，唯一调用方是 smoke（只验"能跑不崩"）。协同删除：`templates/WORKFLOW.md`、`templates/SPEC.md`、`templates/workflow.json`、`harness/verify/verify_workflow.py`；移除 `verify_all.check_templates()`(+TEMPLATES_DIR 导入)、`verify_docs.ACTIVE_DOCS` 的 WORKFLOW 行(+TEMPLATES_DIR 导入)、`smoke_test.py` usage 项、`fix_hardcoded_paths.py` ACTIVE_DOCS 镜像列表的 WORKFLOW、`control-panel-ui-implementer.md` 示例命令；清登记 `capability_manifest.json`(×2)、`scripts-registry.md`、`MAINTENANCE.md`(×2)；`generate_catalog.py` 重生成 `harness/README.md`。
- **撤回**：`docs/subsystem-map.md` 初判"被 工具组件总览.md 取代"**错**——它是按 5 大功能子系统组织的功能图 + 上下文控制闭环叙述（`status:active`、有 trigger、治理方案当承重 cluster 跟踪），与按层的工具目录不重叠，保留。
- **删本地数据**：`.workbuddy/`（WorkBuddy 工具 Apr-28 本地 session，已在 .gitignore，本就不该入库）。
- **验证**：verify_all 0 ERROR（10P/4W，4 warning 为预存）、verify_docs 0 ERROR、smoke 0 FAIL（21P/2W/3S）、scan_orphan orphan_listed=0 且 verify_workflow 不在死引用、capability_manifest JSON 有效。`check_capability_manifest` 的 3 unassigned（readback_audit/check_phase_evidence/task_experience_index）为预存技术债，非本次引入。

- **根 declutter（方向3）**：根层 arch-doc 迁入 `docs/{spec,guide,reference}/`——`docs/spec/`(QUALITY_GATE / RULE_ENFORCEMENT_MATRIX / MEMORY-RULES) + `docs/guide/`(MAINTENANCE / CONTROL_PANEL / CONTRIBUTING) + `docs/reference/`(OBSERVATIONS)。全 `git mv` 保历史。
- **改名**：`memory-rules.md`→`MEMORY-RULES.md`（大小写统一）、`notes.md`→`OBSERVATIONS.md`。`AGENTS.md`/`CHANGELOG.md` 改名 **DROP**（审计：Codex 根镜像约定 / MEM-01 硬编码 + 铁律三重绑定，按用户「按审计」拍板）。
- **删废弃件**：`check_health.py`（DEPRECATED，maintain doctor 接替）+ 清运行机件：oss_readiness `check_health()` 函数+调用、`verify_output_contracts` 契约用例、`smoke_test` external 项、`maintenance_manifest` legacy 注册、`status.py` 标签、docs/README 引用。
- **断链修复**：~34 处引用（脚本硬编码 verify_doc_drift/ghost_refs/memory_file_protector/ai_runner/note/doc_sidebar/oss_readiness、manifest、rules×8、agents、root md）。fresh grep 全仓核对（workflow 断链地图漏了 MEMORY.md 深度硬编码 / docs 机器引用 / note.py / ai_runner，靠 grep 补全）。
- **范围收敛（rule-1 push-back，证据强制）**：① `MEMORY.md`/`MEMORY-LEGACY.md` **留根**——被 init/close_project、memory_usage、maintain HARNESS_AUTO_FILES、test_integration 深度硬编码，移则断。② 现有 `docs/*.md`(14) **不折叠进 reference/**——8 个被 check_capability_manifest/check_hook_alignment/oss_readiness/publish_scope_manifest 硬编码 `docs/<name>` 路径，折叠高危零增益（本就在 docs/，非根杂乱）。
- **隐私保全**：CONTROL_PANEL/OBSERVATIONS 迁入 docs/(external prefix) 后，在 `publish_scope_manifest` private_scope 显式登记新路径（classify file 匹配优先于 prefix），保持 private 不外发。
- **回归**：catalog regen（generate_catalog）修我引入的 agents/README stale + 2 个 pre-existing；CONTRIBUTING 补 frontmatter（docs/ 约定）。stash 基线对比确认：**oss blocker 9→7（去 catalog_freshness/output_contracts，零新增）**、doc_drift=基线(7P/1F)、reconcile exit0、smoke 0 fail。无 VERSION bump（doc 层重构）。
- 审计经 `doc-reorg-execute-discovery` workflow（搬迁map/改名审计/断链地图/删除安全→执行计划），主模型受控分批落 + 每批验证。

### [2026-06-04] [DOCS] 架构表述对齐双轴模型（取代旧 flat-4 + Subagent）

- **背景**：用户指认 `harness-3layer-architecture` 任务 `design/` 下 5 张 drawio 为唯一可信架构源，global 是旧版。旧 README/接入索引 §0 的 flat-4「L1 Rules/L2 Skills/L3 Subagent/L4 Scripts 线性链」是 category error。
- **真模型（双轴各 3核心+1旁挂）**：运转轴 HOW = `Rules→Skills→Script` 三层级 + `harness` 旁挂（强制/触发/隔离，CLI无关）；设计轴 WHAT = `执行→沉淀→反馈` 闭环 + `维护` 旁挂。判断(AI残余+人)住执行层不入钉法列。**Subagent = 理应独立的更高层，当前 dormant 已移除**（非 harness 子功能、非伪层）。
- **改**：`README.md` 架构段重写双轴（两 ASCII 轴图）；`rules/接入索引.md §0` 重写为「架构模型(双轴)」+ 内嵌 WHAT×钉法 格子图（取代旧「两套四层消歧」）；`agents/CLAUDE.md` 架构行改双轴（保留「架构」字面，verifier 不破）；`rules/执行层.md` L18「四层」→「设计轴 WHAT 闭环」；`verify_prompt_system.py` 架构正则 `四层|...Subagent...` → `双轴|运转轴|设计轴|架构`（保留 架构 兜底）。
- **未改（防过度修正）**：执行层 routing「派 subagent」= 委派**动作**（harness 按需隔离仍有效），非 dormant 层，保留；docs/subsystem-map.md「五大功能」旧镜像 = 既有未治理项，单独立项；历史快照/归档保原貌。
- 审计经 `global-model-realign-discovery` workflow（4 区扫 + 汇总 worklist）。验证：verify_prompt_system 架构 PASS、reconcile --check exit 0、smoke 25/0、**零新增失败**。
- ⚠️ 既有问题（非本次引入，stash 对比确认）：verify_prompt_system 3 ERROR（CLAUDE.md 缺 安全边界/启动协议/Agent 判定 区块）—— 早先 19铁律 slimming 把这些节移走/重组，verifier 的 required_claude 期望未跟进。登 backlog 单独修。

### [2026-06-04] [DOCS] 两套「四层」消歧 + 清死引用
- **消歧**：仓库存在两套同名「四层架构」——**载体四层**(L1 Rules/L2 Skills/L3 Subagent/L4 Scripts，结构视角，README) vs **生命周期四层**(执行/沉淀/反馈/维护，功能视角，CLAUDE.md+rules/)。AI 接入第一眼最易撞名（Codex 实测确认）
- `rules/接入索引.md` 新增 **§0 两套四层消歧**（前置于 §1）：点明正交非嵌套 + 载体→生命周期交叉映射表 + 三层金字塔(Script→Skill→Agent)历史名归位（=载体三机制的取用次序偏好，非独立架构）
- `README.md` 四层架构段补一句交叉说明，指向接入索引 §0
- **清死引用**：`docs/工具组件总览.md` + `docs/主循环与日志地图.md` 仍列已删脚本 `view_retrieve_log.py`（2026-06-03 清理删除）→ 改为 `analyze_retrieve_log.py`(统计) / `retrieve_calls.pretty.log`(人读)
- 审计经 `four-layer-disambiguation` workflow（4 并行：抽两模型+碰撞扫描+同步审计→合成）。git/版本/接入索引引用均一致；reconcile --check exit 0
- **未改**：subsystem-map.md「五大功能」旧模型与四层不一致——已属既有未治理镜像（治理方案 §1 high + reconcile meta-check 候选），单独治理不在本次；历史快照(ai-system-audit / CHANGELOG_archive / notes.md)保原貌

### [2026-06-04] [FEAT] reconcile.py 扩展 M2/M3/meta-check
- `harness/scripts/reconcile.py`：M1(渲染) 外加 **M3 引用校验**（rules/*.md 跨层 `../`/同目录 .md 指针目标存在）+ **M2 委托** `scan_orphan_scripts.py`（不重写避免造新检查器）+ **meta-check** 启发式（含多处 hooks/scripts 路径但无 RECONCILE 标记 → advisory）
- **M3 首跑抓 5 真断链**：`rules/{执行,沉淀,反馈,维护}层.md` 误写 `../CLAUDE.md`（实际 `../agents/CLAUDE.md`）+ `维护层.md` 的 `MEMORY.md`（应 `../MEMORY.md`）→ 已修。`--check` 现 M1 drift / M3 断链 → 退 2
- meta-check 标出 5 候选未治理镜像（capabilities/capability-map/gate-template/meta-evidence/subsystem-map）供人工裁定
- M4(词表)=既有 G4 已做按需委托；候选 renderer + 更多 cluster 留后续
- 验证：`reconcile --check` → M1 drift=0 / M3 0 missing / M2 unregistered=2 / exit 0

### [2026-06-04] [FIX] 纳管 learning_opportunity_nudge hook + 更正 bootstrap 假设
- **更正**：multisource-audit/治理方案曾称「bootstrap.py 硬编码 hook 第二源」=**假**。实测 `bootstrap.hooks_json()` 已 `load_hook_manifest()` 从 manifest 渲染，statusLine 同样在 manifest。bootstrap 是渲染器非独立源，「杀第二源」不存在。治理方案 §1/§8/§10 已更正
- **修真 drift**：`check_hook_alignment` verdict=drift（`runtime_not_in_bootstrap`：settings 有 `learning_opportunity_nudge`，manifest 无）。补进 `hook_manifest.json`(PostToolUse/Bash) + `capability_manifest.json`(runtime_hook_governance) + `scripts-registry.md` → `reconcile.py --fix` 重渲染 doc hook 表
- 结果：check_hook_alignment **drift→aligned**(0 findings)；check_capability ERROR **3→2**；scan_orphan unregistered **3→2**（剩 readback_audit / task_experience_index 为既有无关项）
- 不重装 settings（已含该 hook，补 manifest 对齐源即可）。演示单源闭环：改 manifest → reconcile --fix → doc 自动同步

### [2026-06-04] [FEAT] reconcile.py — 多数据源统一治理 MVP（M1 manifest→doc 渲染）
- 新增 `harness/scripts/reconcile.py`：扫全仓 `RECONCILE` 标记动态构建 cluster（发现不枚举，§0 地基）→ M1 `hook_table` renderer 从 `hook_manifest.json` 渲染逐 hook 表 → `--check`(漂移退 2)/`--fix`(重写块)/`--json`
- `docs/主循环与日志地图.md`：加首个 `RECONCILE` 块（逐 hook 表，自动渲染）。TDD：占位→Red(drift exit2)→`--fix`→Green(exit0)
- 登记：capability_manifest(runtime_hook_governance) + scripts-registry + README 计数 139→140。验证零新增巡检错误（check_capability ERROR=3 既有 / scan_orphan unregistered=3 既有）
- **首跑抓真 drift**：`hook_manifest.json` 缺 `learning_opportunity_nudge`（settings 有它）→ manifest 与运行时不同步实证。记 `issues/ISSUE-2026-06-03-rules-layer-minor-backlog.md`（修属 manifest/settings 半，触安装链须确认）
- 范围：仅 doc 镜像渲染，**不碰 settings/bootstrap**（杀第二源那半触 hook 安装链，留确认后单独做）。设计/进度见 `docs/多数据源治理方案.md` §9

### [2026-06-04] [FEAT] RULE_ENFORCEMENT_MATRIX v2 全量合并 + smoke 扩展
- `RULE_ENFORCEMENT_MATRIX.md` v2：矩阵 8→17 hooks（补 RULE-015~023：read_large_file_guard / agent_prompt_gate / memory_lint_gate / subagent_stop_logger / learning_opportunity_nudge / changelog_inject / sync_inject / route_check / retrieve_inject）+ 加 `claude_rule_id` 列（RULE-NNN↔R 交叉，多数 hook 无铁律标 —，R14/R18/R19/R3/R8 有映射）+ R1-R19 索引（层规格引用权威）
- `harness/verify/smoke_test_hooks.py`：8→25 case（matrix v2），新增 read_large_file_guard/agent_prompt_gate/memory_lint_gate/subagent_stop_logger/diff_backup/diff_show/4 注入链/learning_opportunity_nudge/doc_gate 的 happy+robust(fail-open) 用例。回填矩阵 RULE-003/006/007 smoke_test_id。post_task_hook(git副作用) + doc_gate deny-path 仍 SKIP（需 fixture）
- **修真 bug**：smoke_test_hooks.py 的 `HARNESS_DIR = __file__.parent`（文件在 harness/verify/ 但 hooks 在 harness/hooks/，parent 算成 verify/hooks 找不到）→ 改 `.parent.parent`。TDD Red 抓到（24 FAIL→修后 25 PASS/0 FAIL）
- 验证：`python harness/verify/smoke_test_hooks.py` → 25 PASS / 0 FAIL

### [2026-06-04] [DOCS] conventions DOC-*/HARNESS-* 对齐 v2 task 结构
- `decisions/conventions.md`：DOC-01~05 + HARNESS-01/02 改写为 v2 结构（core/背景+HANDOFF+复盘 / design/设计文档+进度+Phase卡 / ops/CHANGELOG+坑点 / test/测试），旧 `docs/SPEC.md+TECHNICAL_DESIGN+PROGRESS+dev-log` 套降级为 legacy 兼容说明
- 硬检查描述对齐 `verify_conventions.py` 实际行为（已有 `is_v2_task()` 分支，v2 查上述文件，非 v2 回退旧检查）——**脚本无需改，仅文本同步**
- 四层架构落地（v1.5.0）配套收口；CODE-/GIT-/FILE- 编码规范不动

### [2026-06-03] [FEAT] harness 四层架构落地（Rules 层重构，VERSION 1.4.0→1.5.0）
- **VERSION 1.4.0 → 1.5.0**（架构重构 = minor；hook/脚本运行时行为未变）；README Release Notes 加 v1.5.0 + 目录结构加 `rules/`
- **`agents/CLAUDE.md` 重写**：177→~50 行，19 条纯行为铁律（思考改动/确定性判断/诚实冲突/测试/交互风格/硬边界）。删：路由 Lane / subagent 预算 / 监控阈值 / 工具使用 / 上下文管理 / 启动协议 / 记忆写入详表（全移层规格或操作细则）。加架构一句 + memory 源 + 接入索引指针。原文件备份在 task `_archive/pre-landing-backup/`
- **新建 `rules/`**：`执行层.md`（唯一含判断；code review分级/启动协议/TDD/路由细则/doc_gate强制点）/ `沉淀层.md`（触发表单一源+frontmatter硬约束+CHANGELOG分级+模板）/ `反馈层.md`（retrieve契约,只读fail-open,采纳判断不在本层）/ `维护层.md`（健康观测+版本治理+机件保护"不改hook"+只读优先）/ `接入索引.md`（AI主目录+非skill入口）。同构骨架：定位→职责边界→接入→接出→本层细则→引用铁律→强制点
- **新建 `docs/`**：`工具组件总览.md`（按层索引+新工具接入+缺口#3）/ `主循环与日志地图.md`（hook链速查+日志地图12条）/ `多数据源治理方案.md`（全局机制§0自声明扫描+M1-M4模式+reconcile.py设计,未实现）
- **work SKILL 抽薄**：`skills/work/SKILL.md` 257→~143 行。移 TDD/路由/doc_gate/存储→执行层规格；删 /work implement + 重复铁律引全局；留全部必跑命令。frontmatter(name/description)保留。原文件备份同上
- **`RULE_ENFORCEMENT_MATRIX.md` v1.2**：加 R1-R19 索引（层规格 R 号引用权威）。RULE-NNN↔R 全量合并 + smoke 留 matrix v2
- 跨盘链接用绝对路径接活（`~/.claude/`↔`D:\global-memory\`）；R-id 按定稿 CLAUDE 编号校正（AI判断R8/恢复边界R9/Tests R13/同错R17/审查R18）
- 落盘前体检（rules-predeploy-review workflow 27确认/15剔除）：0 真 blocker（"文件缺失"类经核实皆存在=沙箱幻觉）；现修 3 cheap；驳回 3 撞已锁决策（PARAM_REGISTRY/Lane展开/concurrent-access）
- 落盘后 Minor（8 项打磨细节）合并为单条 `issues/ISSUE-2026-06-03-rules-layer-minor-backlog.md`（非拆 10 文件，避免 issues/ 噪声）
- 设计/讨论全程见 task `harness-3layer-architecture`（design/ 10 草稿 + ops/CHANGELOG）

### [2026-06-03] [CHORE] harness-3layer-architecture 落地映射 P1 清理（删→清登记）
- 删 4 个 retrieve 一次性诊断脚本：retrieve_optin_compare / retrieve_task_context_simulation / retrieve_task_context_trial_pack / view_retrieve_log（+pyc）
- 删过时报告：tasks/bepinex-generic-multiplayer-framework.md、archives/(2+.gitkeep)、test-reports/(4)
- 同步清 5 处登记：capability_manifest.json / scripts-registry.md / capability-map-and-oss-gap.md / harness/README.md / meta-evidence-pipeline.md（.meta/ 历史证据保留，产出脚本标退役）
- README 计数 140→139
- 验证：check_capability_manifest errors 4→3（剩 3 既有 unassigned，零新增）；scan_orphan STALE_in_registry=0
- **新增 `issues/` 文件夹 + 首条 `ISSUE-2026-06-03-registry-single-source-autoindex.md`**（反馈型 issue 缺口#3 落地）：5 处手登记应改为单一全局索引 + 脚本自动注册/回填
- VERSION 暂不 bump：P1-P3 重构进行中，待阶段收口统一处理

### [2026-06-02] [FEAT] Tier2 强证据门（quality_gate.py test-quality review）
- **VERSION 1.3.0 → 1.4.0**（共享门行为变更 = minor）；README Release Notes 加 v1.4.0
- `harness/scripts/quality_gate.py`：加 `REVIEW_EXTRA_REQUIRED_SECTIONS{test-quality: (Red-Evidence, Mutation)}`；`parse_review_result` 加 `extra_required_sections` 参数（默认空，不破坏现有调用）+ 新 helper `has_concrete_evidence`（比 has_real_section_item 严，`- none` 也判空）；`evidence_state` 按 `evidence.test_quality_red_evidence`（默认 True）接线；`review_prompt` test-quality 模板补两节
- `quality_gate.yaml` + DEFAULT_CONFIG_DATA：加开关 `evidence.test_quality_red_evidence: true`
- `QUALITY_GATE.md`：Review 结果格式加 test-quality 额外必需说明
- `harness/tests/test_quality_gate.py`：+4 用例（缺节/空节/真证据/不传 extra 不变），16 passed
- **原因**：防 AI 写全绿假测试（mock 切错误路径、同义反复断言）；强制红证据 + 变异结论。背景见 feedback/ai-test-failure-modes-four-defenses.md
- **Red-Evidence**：先把 has_real_section_item 用于 extra section → `test_test_quality_review_rejects_empty_red_evidence` 失败（`- none` 被当真内容）→ 改用 has_concrete_evidence 后转绿
- **影响范围**：global-memory 质量门；仅 Tier2 test-quality review，Tier0/1 及其它 kind 不受影响

### [2026-06-02] [REFACTOR] agents/CLAUDE.md 措辞原子化 + 去模糊（对照 Karpathy 12-rule 风格）
- 动因：对照外部 12-rule CLAUDE.md 模板，发现自有 CLAUDE.md 少数处未贯彻自身已有的"量化/原子/表格"写法
- 歧义判断：删模糊"拿不准/优先考虑"，改引用 Lane A 三条件的可判定句（堵 :69 盖 :20-23 的自我稀释）
- 行为规则：拆"技术验证"复合句 → 3 条原子（能验证即验证 / 失败重试 / 不中断+中断条件）；"正式任务>10轮复盘"从"其他"移入
- 工具使用：「大文件」→「文件 >500 行」（补阈值）
- 安全边界：CHANGELOG「简要即可」→「≥1 行：改了什么+为什么」
- 启动协议：「正式任务」加可判定定义（>3 轮 或 需改文件）
- 记忆规范：6 路"记忆写入条件"行内映射 → 表格；拆"/check | guardian"为 2 条
- 「## 其他」垃圾抽屉拆解 → 复盘归行为规则、记忆映射归记忆区、四层架构+存储位置入新「## 架构」节
- 净效果：模糊→可判定、复合→原子、行内映射→表格；表格/分层/量化全保留，无新增/删除规则语义

### [2026-06-02] [ADD] feedback/ai-test-failure-modes-four-defenses.md
- 新增记忆：AI 写测试系统性失效模式（代码焊死→mock 切错误路径→全绿假覆盖）+ 四道防线（RED 先行/独立 oracle/变异测试/属性测试）；锚点 XDAP QualcommPerfMonitor P0-1

### [2026-06-02] [FEAT] vendor learning-opportunities skill + auto hook（git commit 触发学习练习）
- 装第三方 skill `learning-opportunities`（github.com/DrCatHicks/learning-opportunities，CC-BY-4.0）：`skills/learning-opportunities/v1/SKILL.md` + `resources/PRINCIPLES.md`（193 行 vendored），软链 `~/.claude/skills/learning-opportunities`
- 机制：AI 辅助编码完成架构性工作后提议 10-15min 微练习（预测/生成对比/追踪/debug/teach-back/检索），核心「Pause for input」硬停逼用户主动生成，对抗 generation effect/fluency illusion
- auto hook：上游 bash `post-tool-use.sh` **port 成 python** `harness/hooks/learning_opportunity_nudge.py`（Windows 兼容本地约定）；PostToolUse matcher `Bash`，检测 git commit → 注入 additionalContext 提醒主模型提议练习；限频 2 次/session（状态文件 `logs/lo_auto_state/<sid>.state`）；失败静默不破业务
- settings.json PostToolUse 加 matcher `Bash` 条目
- 验证：hook 5 用例全过（commit 注入/限频/git log 不触发/非 Bash 不触发）；verify_all 软链 14→15、SKILL.md YAML 12 个完整、0 ERROR

### [2026-06-01] [ARCHIVE] cross-task-experience-retrieval 归档
- **来源任务**：D:\ClaudeTasks\archived\cross-task-experience-retrieval
- **归档原因**：P1-P4 全完，验收清单全 [x]，跨任务经验召回层 + work skill 删 v1 收尾
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\cross-task-experience-retrieval/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-01] [REFACTOR] work skill 删 v1（P4，跨任务经验召回层收尾）
- `skills/work/v1/SKILL.md`：去 8 处 v1 块——两结构表→单 v2 + 3 行 legacy 读兼容；删 v1 立项流程/v1 落地表/v1 任务收尾/v1 implement 子流程；各标题去 `（v2 任务）` 限定词；「不做的事」末条改「不新建 v1 平铺；老平铺只读兼容」
- `decisions/decision_work_mode_workflow.md`：加 2026-06-01 supersede banner，§4/§7 v1 机制（SPEC平铺/discussion·implementation 二阶段/check_doc_status 三层防线）标历史；frontmatter `stages` 保留（属通用 retrieval vocab 非 v1 状态机）
- `docs/task-lifecycle.md`：无需改（已 v2-canonical，line 204 legacy 框架正确）
- 重渲 `~/.codex/skills/codex-work/SKILL.md`（render_codex_work_skill.py，单源同步 ✅）
- 验证：verify_all 10 PASS/5 WARN/0 ERROR（codex 同步✅/YAML✅/doc 一致✅；warn 全 pre-existing 或 uncommitted）；smoke 23 PASS/0 FAIL

### [2026-06-01] [FEAT] task_experience_index.py 加 --promote-candidates（B 升进提醒）
- 列 index 中 pitfall/retro 类、与 global fixes/knowledge keyword 重合<2 的条目 = 疑似漏升进 global
- 实测 47 候选，高 conf 在顶（WITH_LIVE_CODING UFunction 布局/FTicker 生命周期/单例线程安全）
- 纯启发式列出，人工判普适与否；不自动升进

### [2026-06-01] [FEAT] task-local 层重定向：CLI 自动记忆 → ClaudeTasks 跨任务经验索引
- 认知纠正：上一版 task-local 建在 CLI 自动记忆（CC 原生自查 MEMORY.md，重复造轮子）→ 撤
- 改读 **ClaudeTasks 跨任务经验索引**（旁路索引，不焊 schema 到 336 异构历史文件）
- 索引由 workflow `task-experience-triage`（57 agent/197s）内容分类产出：235 候选 → 163 reusable（design48/pitfall36/knowledge27/reference18/decision16/retro18），37 任务
- `harness_retrieve.py`：`load_task_experience_index` 取代 `resolve_project_memory`/`scan_project_local`；retrieve 参 `project_memory_root`→`task_index_path`；索引条目带真 keyword 走正常阈值
- `retrieve_inject.py`：接 `DEFAULT_TASK_INDEX_PATH`（跨任务，不再 cwd 隔离）
- 新增 `task_experience_index.py`：枚举/diff/prune/build 维护工具（triage 走 workflow，脚本只做确定性部分；triaged 全集记录避免拒掉的反复当 new）
- 新增 `data/task_experience_index.json`（进 git，可重建）
- 验证：U17-19 改写 + 全 55 passed/9 skip；实测安卓/puerts/多线程 query 跨任务浮出埋藏经验，4-24ms；smoke 0 FAIL

### [2026-06-01] [DECISION] decision_retrieve_injector_feedback_failure 追加两层架构
- 记录 global 库(前者,独立) + 局部层(后者,依赖前者) 设计；洞2 第二条路：升进降级为例外，局部经验按 cwd 隔离浮出
- 记录为何不选 A(并进 global 索引,破单一来源+污染) / 纯 B(全量升进,局部噪音污染全局)；分层归因(洞1 匹配层/洞2 索引层/洞3 投递层)
- 复审条件加：局部层读回率一周后评估；CLI 记忆无 git 备份单独处理不靠塞 global

### [2026-06-01] [FEAT] retrieve 两层架构：项目局部记忆层（task-local）
- 设计：global 库独立可用；局部层（CLI 自动记忆 `~/.claude/projects/<slug>/memory`）依赖 global、按项目 cwd 隔离、不进 global 库。避免局部噪音污染全局，且无 git 的 CLI 记忆只读浮出不批量升进
- `harness_retrieve.py`：加 `resolve_project_memory(cwd)` + `scan_project_local()`；retrieve 加 `project_memory_root` 参，独立低阈值(0.3 让 desc-token 浮出)、上限 1 条、标 `source:task-local`、与 global 缓存物理隔离；Pointer 加 `source` 字段
- `retrieve_inject.py`：从 cwd 解析项目记忆目录传入；沿用类型选择性（feedback_ 仍排除）
- 验证：U17-19 新测 + 全 55 passed/9 skip；实测 22 文件 13ms（hook 1s 预算内）；安卓 runbook 经局部层浮出（洞2 第二条路，免手动升进）；非匹配 cwd 自动隔离不泄漏
- 起步仅 description 回退匹配（不读正文），一周看局部层读回率不够再上正文匹配

### [2026-06-01] [ARCHIVE] chlight-submitter-version-check 归档
- **来源任务**：D:\ClaudeTasks\archived\chlight-submitter-version-check
- **归档原因**：P4V TorchlightSubmitter 版本检查根因已定位+修复验证，fix 记忆已落 global-memory
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\chlight-submitter-version-check/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-01] [DECISION] 修订 decision_retrieve_injector_feedback_failure（类型选择性）
- 从"砍全部 pointer"改为类型选择性：feedback 排除、fixes/knowledge/decisions 带 summary 保留 + CN alias 桥 + 经验升进
- 收尾验证 workflow 3 路全 PASS：e2e 中英 query 准确召回带 summary、feedback 排除；smoke 24/0/0；7 处与实现矛盾已同步修订
- 复审条件更新：summary 注入读回率 <5% 则收紧；alias 误召回加精度审计；真新颖改写漏则评估 embedding

### [2026-06-01] [MEMORY] 新增 fixes/fix_android_apk_packaging_pitfalls.md（洞2 覆盖）
- 安卓打包经验从 CLI 自动记忆升进 global-memory/fixes：5 类复发坑(MAGT-8/A10 AThermal/A11 AppsFilter/OBB丢失/推送铁律)+Git Bash 路径陷阱
- 正文留权威全文 runbook 指针(不复制全文防失同步)；中文 query 经 alias 命中、带 summary 注入
- 验证：'安卓打包重签名obb'/'打安卓包遇到闪退' 现浮出此 doc

### [2026-06-01] [ADD] fixes/fix_torchlight_submitter_version_check.md
- 新增 P4V TorchlightSubmitter 版本号检查失败的根因+解法（运行副本在 C:/submitter_log，sync 主干不刷新，须重跑 update_submitter.bat）
- 反编译取证（pyinstxtractor + uncompyle6/xdis）；lint PASS

### [2026-06-01] [FEAT] alias 表加 CN→EN 桥（洞1，改 per-doc 双语为中央 alias）
- triggers_aliases.yaml 加 安卓/打包/重签名/obb/真机/性能 → platform:android 等映射
- 放弃 per-doc 双语关键词（撞 lint 5-cap + overtagging）；改中央 alias 一处维护、自动惠及所有未来 doc
- 验证：中文"安卓打包/打安卓包/安卓真机性能"query 现命中 android fixes（此前空命中）

### [2026-06-01] [FEAT] retrieve 类型选择性注入 + summary 投递（洞3）
- `score_entries`：summary 回退到 description，fixes/knowledge/decisions 召回带一句话预览，AI 直接吃免再 Read（治"裸路径不读"投递洞）
- `retrieve_inject`：改"全砍 pointer"为"只滤 feedback"（feedback 归 CLAUDE.md），保留 fixes/knowledge/decisions 注入
- 修订前一条全砍决策：feedback 排除对、但 fixes/knowledge 跨 task 浮出是真价值不该一刀切

### [2026-06-01] [FIX] retrieve_inject 砍 pointer 只留 handoff
- 落地 decision_retrieve_injector_feedback_failure：`_run_retrieve` 清空 `brief.relevant_pointers`，只注 handoff
- write_retrieve_log 仍记完整 brief(含 pointer)，分析数据不丢；仅实际注入剔除
- 验证：无 handoff prompt→零注入；有 handoff→注 handoff+pointer 空；端到端+功能测通过
- 预计省 ~10-21万 token/月(此前 pointer 命中率上限 0.82%)

### [2026-06-01] [FEAT] 新增 harness/readback_audit.py
- 文档回读率审计脚本，复用 tool_audit.jsonl 无埋点。基线：正式任务会话 HANDOFF 整会话回读 68.4%、开头回读 21.1%
- 用途：持续量化文档体系真实价值，区分"文档有用"(整会话)与"启动协议执行度"(开头)
- 注：retrieve_inject 砍 pointer (decision 已定案)因该文件被并发会话重构中，暂缓

### [2026-06-01] [DECISION] 新增 decisions/decision_retrieve_injector_feedback_failure.md
- 实测 retrieve 注入器对 feedback 无效(94%注入是feedback, 0.33%被读); 定案砍 pointer 只留 handoff + feedback 走 CLAUDE.md 毕业路径
- 数据依据: 30天 4808 pointer注入 / memory读39次 / summary字段0% / handoff读回68%

### [2026-06-01] [MEMORY] 新增 fixes/fix_linter_false_positive_guard_test.md
- 记录路径 linter 误报守护测试 + smoke-test WARN 不透明这对工具坑（含排查时「先查 mtime/git 防并发误判」提示）

### [2026-06-01] [FIX] 路径 linter 假阳性 + smoke-test WARN 可读性
- **fix_hardcoded_paths.py**：跳过测试文件（`tests/`、`test_*`、`*_test`、`__pycache__`）。守护测试用 `assert 'Path("D:/...")' not in text` 断言「硬编码不应存在」，旧逻辑裸正则把守护测试本身误报成违规（假阳性）
- **smoke_test.py**：新增 `summarize_output()`，run/hook 类脚本 exit≠0 且无崩溃时，detail 从 `"exit 1"` 升级为摘一行有信息量的输出（命中 发现/问题/drift/缺少 等关键词，否则取末行）——此前根因被埋成不透明 WARN
- **验证**：linter 复跑 Python 段 `✅ 无硬编码路径`；smoke 24 PASS/0 WARN/0 FAIL；`summarize_output` 3 用例单测通过
- **未触碰**：archive_task.py / test_warning_cleanup.py 正被并发会话重构（env-based task-root，未提交），本次提交仅含 linter + smoke 两文件

### [2026-06-01] [FIX] work skill 路径/措辞修复（harness 审计补充，文件在 skills/ 非 global-memory）
- **P0 阻断**：`task_template` 引用从 `global-memory/_bootstrap/...` 修正到真实盘 `skills-repo/_bootstrap/templates/task_template`（此前 v2 立项 Copy-Item 必失败）
- **P1**：子目录措辞统一为「core/design/ops/test 4 工作子目录 + _archive 归档」（description 原写 5、正文 4 矛盾）
- **P3**：`update_phase_status.py` 路径去双 `scripts`，改 `global-memory/harness/scripts/...` 对齐约定
- **P2**：`codex-adapter.md` 标注 design-reserved（Codex runtime 覆盖层，Claude Code 不加载，勿删）
- **文件**：`~/.claude/skills/work/SKILL.md`

### [2026-06-01] [ARCHIVE] work-skill-phase-tdd 归档
- **来源任务**：D:\ClaudeTasks\archived\work-skill-phase-tdd
- **归档原因**：完成
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\work-skill-phase-tdd/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-01] [ARCHIVE] work-skill-maintenance-sync 归档
- **来源任务**：D:\ClaudeTasks\archived\work-skill-maintenance-sync
- **归档原因**：完成
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\work-skill-maintenance-sync/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-01] [ARCHIVE] codex-work-skill-mvp 归档
- **来源任务**：D:\ClaudeTasks\archived\codex-work-skill-mvp
- **归档原因**：完成
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\codex-work-skill-mvp/_archive/extract_candidates.md`（人工判定入库）

### [2026-06-01] [FEAT] fixes: UE /fp:fast NaN 比较不可靠
- **来源任务**：D:/ClaudeTasks/active/xdap-thermal-flow-align（DIFF-3）
- **变更内容**：新增 `fixes/ue_fpfast_nan_compare_unreliable.md`——UE 默认 `/fp:fast` 下 `NaN==X` 比较被优化成误判，丢值或误命中；修复用 `FMath::IsFinite`（位检查，fast-math 免疫）短路。
- **验证**：`harness_memory_lint.py` PASS；实战来源 `AndroidSamples.RawZoneSamplesFedToFlowLayer` 实机绿。

### [2026-05-29] [FEAT] ai-quality-gate 初版
- **来源任务**：D:/ClaudeTasks/active/ai-quality-gate
- **变更内容**：新增 `QUALITY_GATE.md`、`quality_gate.yaml`、`harness/scripts/quality_gate.py`、`harness/tests/test_quality_gate.py` 和根 `AGENTS.md`，提供跨 Claude Code / Codex 的风险分级代码质量门。
- **验证**：见任务 `test/测试.md`。

### [2026-05-29] [FEAT] ai-quality-gate review 格式校验
- **来源任务**：D:/ClaudeTasks/active/ai-quality-gate
- **变更内容**：`quality_gate.py verify` 校验 review 结果文件格式，拒绝 prompt 模板占位、非法 Verdict/Confidence、缺固定 section、BLOCK 无 Blocking 条目。
- **验证**：`python -B -m unittest harness.tests.test_quality_gate -v` 12 tests OK。

### [2026-05-22] [ARCHIVE] harness-doc-completion 归档
- **来源任务**：D:\ClaudeTasks\archived\harness-doc-completion
- **归档原因**：完成
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\harness-doc-completion/_archive/extract_candidates.md`（人工判定入库）

### [2026-05-22] [ARCHIVE] harness-usage-audit 归档
- **来源任务**：D:\ClaudeTasks\archived\harness-usage-audit
- **归档原因**：完成
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\harness-usage-audit/_archive/extract_candidates.md`（人工判定入库）

### [2026-05-21] [ARCHIVE] harness-governance-followup 归档
- **来源任务**：D:\ClaudeTasks\archived\harness-governance-followup
- **归档原因**：8/8 Phase done; 7 候选已入 global-memory/{fixes,decisions,knowledge}; HANDOFF + 复盘齐备; 后继任务 harness-handoff-sync-gate + harness-usage-audit 已开
- **物理位置**：active → archived
- **抽取候选**：见 `D:\ClaudeTasks\archived\harness-governance-followup/_archive/extract_candidates.md`（人工判定入库）

### [2026-05-21] [MEMORY] harness-governance-followup 归档蒸馏 7 条
- **来源任务**：D:/ClaudeTasks/active/harness-governance-followup（归档前蒸馏）
- **变更内容**：从 `_archive/extract_candidates.md` 10 候选人审选 7 条入库
  - `fixes/fix_subprocess_windows_cross_process_encoding.md` — subprocess Windows 缺 errors="replace" UnicodeDecodeError 污染 stderr
  - `fixes/fix_handoff_drift_no_gate.md` — HANDOFF.md 多 Phase 推进无 gate → 全程不回写
  - `decisions/decision_skip_right_explicit_keyword.md` — 5 护栏跳过权用显式关键词 vs 文件缺省
  - `decisions/decision_three_mode_cli_argparse_mutex.md` — 互斥多模式 CLI 单脚本 argparse mutex group
  - `decisions/decision_irreversible_op_double_guard.md` — 不可逆操作双守护 (--yes flag + 内部前置 check)
  - `knowledge/knowledge_subprocess_windows_encoding_fallback.md` — subprocess Windows 跨进程读编码原理 + reader 线程异常机制
  - `knowledge/knowledge_topic_shift_window_count_pitfall.md` — 滑动窗口 item count vs cumulative total 分离
- **跳过**：3 条任务内信息（HANDOFF 导航 / 复盘 meta / 坑点.md 模板噪音）
- **验证**：`harness_memory_lint.py` 7/7 PASS（一处 `tool:python` 改 `concept:mode` 通过 source token check）

### [2026-05-21] [DOC] task-lifecycle § Phase 拆分加 M1 反问规则
- **来源任务**：D:/ClaudeTasks/active/harness-governance-followup（伪需求审计）
- **变更内容**：`docs/task-lifecycle.md` § 1.必做步骤 + § 2.必做行为 各加一条 M1 反问规则（每 Phase 必填「不做会怎样？」，Phase done 时反问复审）
- **背景**：harness-governance-followup 8 Phase 事后审计 P2/P5 伪需求（metrics 无 action / daemon 从未启动），暴露 D9 治理预算反向激励 + status=done≠有用问题
- **影响**：所有未来任务设计阶段 / Phase done 阶段；不破坏现有 Phase 卡

### [2026-05-21] [FIX] verify_all.check_auto_sync stderr UnicodeDecodeError
- **来源任务**：D:/ClaudeTasks/active/harness-governance-followup（smoke_test WARN 清理）
- **变更内容**：
  - `harness/verify/verify_all.py:check_auto_sync` 三处 subprocess（PowerShell `Get-CimInstance` / `tasklist` / `ps aux`）补 `errors="replace"`
- **根因**：其他系统进程 CommandLine 含 cp936 字节，`text=True, encoding="utf-8"` 无 errors fallback → subprocess reader 线程抛 `UnicodeDecodeError` 写 stderr，主程序吞掉 exit 0；`smoke_test.py` 用 CRASH_PATTERNS 扫 stderr 命中 Traceback → WARN
- **影响**：`smoke_test.py` WARN 数从 3 降到 2（剩 2 WARN 为 G9 存量硬编码 + `check_health.py` 87 处 lint，均独立任务范围）；`gate_check.py` G1-G9 仍全 PASS；`pytest harness/tests/` 119 项不动
- **验证**：`python verify_all.py 2>&1 1>/dev/null` 输出空；smoke_test 重跑 23 PASS / 2 WARN / 0 FAIL

### [2026-05-21] [FEAT] harness-governance-followup P8 archive-extractor
- **来源任务**：D:/ClaudeTasks/active/harness-governance-followup
- **变更内容**：
  - 新建 `harness/scripts/archive_task.py`：单脚本三模式 CLI（`--check` / `--extract` / `--commit`，mutually_exclusive_group）；零依赖手写 frontmatter 解析；task 参数支持 id / 绝对路径 / `.`
  - `--check`：扫 `design/Phase*.md` 全 done → `ready_to_archive: true`（rc=0），否则列未完 Phase（rc=1）
  - `--extract`：先 lint `core/复盘.md`（P6 5 护栏 — `^self_check: rails=\{...\}\s+reasoned=true` 锚 + 「下次可能踩」+「不打算修」+ 引用密度 ≥1 `file.ext`；含「本任务无重大踩点」/「跳过复盘」视为 P6 护栏 2 跳过权合法），FAIL → rc=2 拒绝产出；通过则扫 HANDOFF/复盘/坑点 按 `## ` 切块、关键词分类 fixes/knowledge/decisions/feedback，产 `_archive/extract_candidates.md`（D8：不自动写 global-memory）
  - `--commit`：必须 `--yes`（D10）+ 内部 `--check` PASS；`shutil.move(active/<task>, archived/<task>)`；display_names 保留；append 全局 CHANGELOG 一行 `[ARCHIVE] <task>`
  - `docs/scripts-registry.md` 注册 `scripts/archive_task.py | Manual | REPORT`
- **触发**：harness-doc-completion 复盘 § 1.5「归档即蒸发」+ D5/D8/D10
- **D9 治理预算**：1 脚本 + 1 doc rule（注册 + Phase 卡）+ 1 自动检查（extract 5 护栏 lint），合规
- **验证**：5 场景实测全过 — (a) `--check` 本任务 ready；(b) `--extract` 无复盘 → rc=2；(c) `--extract` fixture 完整复盘 → 5 候选分类正确；(d) `--commit` 无 `--yes` → rc=1；(e) `--commit` --check 失败 → rc=1；scan_orphan UNREGISTERED=0；全量 66 pytest 回归 PASS
- **设计文档**：`design/Phase8-archive-extractor.md`（status=done）

### [2026-05-21] [FEAT] harness-governance-followup P7 compact-nudge
- **来源任务**：D:/ClaudeTasks/active/harness-governance-followup
- **变更内容**：
  - `harness/hooks/route_check.py` 扩话题切换检测：模块常量 `TOPIC_WINDOW_FILE` / `TOPIC_WINDOW_SIZE=5` / `TOPIC_MIN_TURNS=10` / `TOPIC_JACCARD_THRESHOLD=0.08`；新增 `tokenize_topic` (ASCII 词 ≥3 字符 + CJK 2-gram，零依赖)、`load_topic_window` / `save_topic_window` (写 `~/.claude/.topic_window.json`，含 prompts 列表 + cumulative total)、`jaccard`、`check_compact_nudge` (total≥10 且 jaccard<threshold 时返回 `💡 考虑 /compact 清理上下文`)、`update_topic_window` (同话题合并扩词)；`main()` 维护窗口 + cumulative+1；compact nudge 优先级最低，前置 stdin 关键词/stats nudge 未命中才出声
- **触发**：harness-doc-completion 复盘 § 1.6「新无关任务忘 /compact」+ D6
- **D9 治理预算**：0 新脚本（扩既有 hook）+ 1 doc rule（阈值/算法记 Phase 卡）+ 0 新检查（复用 UserPromptSubmit hook），合规
- **验证**：3 场景实测 — (a) 12 同话题 + 1 不相关 prompt → sim=0.07 触发；(b) 12 同话题 + 1 相关 prompt → 静默；(c) 5 同话题（未达 MIN_TURNS）+ 1 不相关 → 静默；全量 66 pytest 回归 PASS
- **设计文档**：`design/Phase7-compact-nudge.md`（status=done）

### [2026-05-21] [DOCS] harness-governance-followup P6 archive-retro
- **来源任务**：D:/ClaudeTasks/active/harness-governance-followup
- **变更内容**：
  - `docs/task-lifecycle.md` § 4 (archived) 在「转换条件」与「必做步骤」之间插入「归档前复盘（5 条护栏）」节：5 行表（门槛 / 跳过权 / 引用强制 / ROI 强制 / 自检节，含 FAIL 处置）+「护栏触发方式」节（`self_check: rails={1,2,3,4,5}  reasoned=true` 锚行约定）+ 前向引用 P8 `archive_task.py --extract` 做 lint
- **触发**：harness-doc-completion 复盘 § 1.5「归档即蒸发」+ D5
- **D9 治理预算**：1 doc rule（5 护栏 + self-check 锚约定）+ 0 自动检查（lint 落 P8）+ 0 新脚本，合规
- **验证**：doc-only 不影响代码路径；全量 66 pytest 回归保持 PASS
- **设计文档**：`design/Phase6-archive-retro.md`（status=done）

### [2026-05-21] [FEAT] harness-governance-followup P5 governance-daemon
- **来源任务**：D:/ClaudeTasks/active/harness-governance-followup
- **变更内容**：
  - 新建 `harness/governance_pulse.py`：复用 auto_sync_daemon 结构；`run_one_pulse()` 直接 import `gate_check.check_prereqs` + subprocess 跑 scan_orphan / scan_dual_storage；写 `~/.claude/logs/governance_pulse.jsonl`；CLI `--once` / `--daemon` / `--interval` / `--show-latest`；任何 step 异常吞掉只写 error 字段
  - patch `bin/statusline.py`（在 C:/Users/XINDONG/.claude/bin/，不在 global-memory 仓内但属本任务交付）：头部 utf-8 stdout 包装（cp936 兜底）；末尾读 jsonl tail 2KB 显示 🔴N
  - `docs/scripts-registry.md`：注册 `governance_pulse.py`
- **触发**：harness-doc-completion 复盘 § 1.4「巡检写一次跑一次」+ D3
- **D9 治理预算**：1 脚本（daemon）+ 1 doc rule（jsonl schema）+ 1 自动检查（聚合周期跑）+ 0 hook（D3 红线），合规
- **验证**：
  - `--once` 写一行 jsonl ✅
  - statusline 干净显示无红点；注入 issues=3 显示 `🔴 3` ✅
  - orphan 巡检 UNREGISTERED=0（governance_pulse.py 已注册）✅
  - 全量 66 pytest PASS ✅
- **设计文档**：`design/Phase5-governance-daemon.md`（status=done）

### [2026-05-21] [FEAT] harness-governance-followup P4 warn-sunset
- **来源任务**：D:/ClaudeTasks/active/harness-governance-followup
- **变更内容**：
  - 新建 `harness/scripts/warn_sunset.yaml`：WARN 注册表 + 内嵌 schema/政策注释；初始注册 G9（sunset=2026-08-31，owner=gaoxiang，tracking=harness-hardcoded-cleanup）
  - `harness/scripts/gate_check.py`：加 `load_warn_sunset()` + `apply_sunset_policy(entry, base_pass, base_detail, strict, today=None)`（pure helper 便测）；`check_prereqs(strict_sunset=False)`；G9 评估后套 sunset 策略；CLI `--strict-sunset`
- **触发**：harness-doc-completion 复盘 § 1.3「WARN 永远不修」
- **D9 治理预算**：1 doc rule（yaml schema）+ 1 自动检查（sunset 策略+flag）+ 0 新脚本，合规
- **验证**：
  - 默认 G9 detail 含 `[sunset 2026-08-31 owner=gaoxiang tracking=harness-hardcoded-cleanup]` ✅
  - `--strict-sunset` 在 sunset 期内仍 PASS（rc=0）✅
  - 5 状态单测（today 注入）：过期默认 PASS、过期 strict FAIL、过期+extended strict PASS、未注册默认 PASS、未注册 strict FAIL ✅
  - 全量 66 pytest 回归 PASS ✅
- **设计文档**：`design/Phase4-warn-sunset.md`（status=done）

### [2026-05-21] [FEAT] harness-governance-followup P3 retrieve-optin
- **来源任务**：D:/ClaudeTasks/active/harness-governance-followup
- **变更内容**：
  - `harness/scripts/harness_retrieve.py`：SCHEMA_VERSION v1→v2；`Pointer` 加 `summary`；`scan_trigger_files()` 扩 docs/ opt-in 分支（须 `retrieve: true` + `retrieve_summary` 非空 str，截断到 200 字）；`load_trigger_cache()` watch 加 `"docs"`；`retrieve()` 把 summary 传进 Pointer
  - `harness/scripts/harness_memory_lint.py`：新增 `_check_retrieve_optin()` + `_is_docs_file()`；docs/ 走精简校验（不套 memory 强约束）；memory 文件末尾再调一次保险
  - `docs/hook-chain.md` + `docs/task-lifecycle.md`：frontmatter 加 `retrieve: true` + `retrieve_summary`
  - `harness/tests/context_governance/{unit,regression}/`：3 处 schema 锚 v1→v2
- **触发**：harness-doc-completion 复盘 § 2.2 + § 4
- **D9 治理预算**：1 doc rule + 1 自动检查 + 0 新脚本，合规
- **验证**：lint 两 docs PASS；负样本（缺 summary）正确 FAIL；retrieve hook query 命中 docs/hook-chain.md 并返回 summary；未 opt-in docs 不进库；全量 66 pytest PASS
- **设计文档**：`design/Phase3-retrieve-optin.md`（status=done）

### [2026-05-21] [FEAT] harness-governance-followup P1 infra-base
- **来源任务**：D:/ClaudeTasks/active/harness-governance-followup
- **变更内容**：
  - `harness/_lib.py` 加 `run_utf8(cmd, timeout, cwd, input, env, check)`：统一 subprocess 封装，强制 utf-8 + errors=replace + stdout 兜底空串 + 子进程 PYTHONIOENCODING 注入
  - `harness/scripts/update_phase_status.py` 新建（~150 行）：CLI `<task> <N> <status>` 一键三同步（卡 frontmatter / 设计文档表行 / 验收清单），幂等
  - `harness/scripts/scan_orphan_scripts.py` 加 glob 解析：`parse_registry()` 返回 `(literal, globs, orphans)`；registry 可写 `path/**/*.py` 通配
  - `harness/scripts/gate_check.py` 迁到 `run_utf8`：去本地 `encoding=` 散落写法
  - `docs/scripts-registry.md`：注册 `update_phase_status.py`；scan_orphan 描述加「glob 通配」
- **触发**：harness-doc-completion 复盘 § 1.1 / 1.2 / 1.5
- **验证**：
  - gate_check `--phase P3` G1-G9 全 PASS ✅
  - `update_phase_status.py harness-doc-completion 5 done` 三处 ✅ 幂等
  - `scan_orphan_scripts.py` UNREGISTERED=0 ✅
- **设计文档**：`design/Phase1-infra-base.md`（status=done）

### [2026-05-21] [TASK-INIT] harness-governance-followup scaffold
- **来源任务**：D:/ClaudeTasks/active/harness-governance-followup
- **变更内容**：仅 ClaudeTasks/ 下新任务 scaffold，未改 global-memory 文件
  - `core/背景.md`：6 痛点 / 边界 / 利益相关方
  - `design/设计文档.md`：7 Phase（infra-base / retrieve-metrics / retrieve-optin / warn-sunset / governance-daemon / archive-retro / compact-nudge）+ 7 决策 + 5 护栏 + 8 不做 + 7 验收
  - `core/HANDOFF.md`：下次起 P1
  - `~/.claude/projects/task_display_names.json`：加 `harness-governance-followup → Harness治理v2`
  - `~/.claude/.current_task` 切到 harness-governance-followup
- **触发**：harness-doc-completion 复盘抓出 11 条优化 + 2 条工作流提案，集中实施
- **关联**：上游 `D:/ClaudeTasks/active/harness-doc-completion/design/复盘.md`

### [2026-05-21] [FEAT] harness-doc-completion 5 Phase 落地（P1-P5 全 done）
- **来源任务**：D:/ClaudeTasks/active/harness-doc-completion
- **变更内容**：
  - `docs/scripts-registry.md` 新建（~220 行，9 节，全 109 .py 注册；新增 control_panel_pyside 14 行内部模块）
  - `docs/hook-chain.md` 新建（~180 行，5 hook event 顺序图 + stdin/output/失败降级）
  - `docs/gate-template.md` 新建（~130 行，Gx 接入 5 步 + FAIL/WARN 二分 + 反模式 + 当前 Gate 列表 G1-G9）
  - `docs/task-lifecycle.md` 新建（~180 行，4 状态机 create→active→paused→archived→deleted + 归档 5 步 + 反模式）
  - `CONTRIBUTING.md` § 3.5 加「接入 gate_check.py」5 步简版；§ 3.6 加「别让脚本成孤儿」3 条约束
  - `harness/scripts/scan_orphan_scripts.py` 新建（~140 行，UNREGISTERED/ORPHAN_LISTED/STALE 三类，CLI + JSON + strict 三模式）
  - `harness/scripts/gate_check.py`：check_prereqs 加 G9（fix_hardcoded_paths.py / WARN）；run() 子进程 utf-8 修复 GBK NoneType 崩；标题 G1-G8 → G1-G9
- **触发**：harness 文档与孤儿脚本治理空缺 → 5 Phase 设计 → 全实施 + 每 Phase 实施卡
- **验证**：
  - `scan_orphan_scripts.py` 跑通：UNREGISTERED=0 / ORPHAN_LISTED=2（route_gate.py / work_context_pack.py 旧版）/ STALE=0 ✅
  - `gate_check.py` 首跑 G9 行入报告 detail=`WARN: 22 hardcoded issues`，Verdict PASS（WARN 不阻断）✅
  - GATE-REPORT-2026-05-21-P5.md 归档 task/test/ ✅
- **设计文档**：`D:/ClaudeTasks/active/harness-doc-completion/design/设计文档.md` + 5 个 Phase 卡（全 status=done）

### [2026-05-21] [FEAT] work 文档标准化 v2 落地（P1+P2，scripts P3）
- **来源任务**：D:/ClaudeTasks/active/harness-context-governance
- **变更内容**：
  - `harness/hooks/retrieve_inject.py`：`_resolve_task()` 改优先读 `~/.claude/.current_task`，cwd→registry 降级为 fallback
  - `harness/hooks/statusline.py`：弃 `.session_tasks/<session_id>` 双写；改读 `.current_task` 单源；加 `load_display_name()` 查中文映射
- **配套（在 ~/.claude/ 下，非 global-memory）**：
  - `~/.claude/projects/task_display_names.json` 新建（13 条 task→中文）
  - `~/.claude/scripts/work_context_pack.py` 加 STATUS.md 派生 + 单行 echo + `tasks_root` fallback
  - `D:/skills-repo/_bootstrap/templates/task_template/` 新建（13 文件 + 5 子目录：core/design/ops/test/_archive）
- **触发**：v1 文档静默无感、`.current_task` 不生效（statusline + brief 抓错 task）、HANDOFF 流水账化、文件夹平铺混乱
- **验证**：
  - `.current_task=harness-context-governance` → statusline 显示「上下文治理」✅
  - `python work_context_pack.py --task harness-context-governance` → echo `📋 任务 上下文治理 已加载` + 写出 7 字段 STATUS.md ✅
  - `--json` 模式 schema 不变 ✅
- **方案文档**：`D:/ClaudeTasks/active/harness-context-governance/方案-work文档标准化-v2.md`（status=done）

### [2026-05-20] [CHORE] decisions/ trigger 补全 → 100% coverage
- **来源任务**：D:/ClaudeTasks/active/harness-context-governance
- **变更内容**：
  - `decisions/conventions.md`：加 trigger.keywords(concept:convention/project/spec) + tags(workflow/design/tooling) + stages + priority/status/last_updated
  - `decisions/decision_work_mode_workflow.md`：加 trigger.keywords(tool:work / concept:workflow / tool:skill) + tags(workflow/design/skill) + stages
- **触发**：trigger coverage 卡 24/26 = 92.31%；decisions/ 早期 SUBS 排除未自动生 .proposed；现手补完成
- **验证**：
  - `harness_memory_lint.py` 双 PASS ✅
  - `check_trigger_coverage.py` 28/28 = **100.00%** ✅
  - retrieve `concept:convention 项目规范` → 命中 conventions.md ✅

### [2026-05-20] [FEAT] harness retrieve 数据驱动日志回路落地
- **来源任务**：D:/ClaudeTasks/active/harness-context-governance
- **变更内容**：
  - `harness/scripts/harness_retrieve.py`：加 `write_retrieve_log()`，main() 调用，每次 retrieve append 一行 JSONL 到 `~/.claude/logs/retrieve_calls.jsonl`（含 ts/task/query/hits/scores/elapsed_ms/warnings）。env `HARNESS_RETRIEVE_LOG=0` 关
  - `harness/scripts/analyze_retrieve_log.py`（新）：扫日志输出 noisy_kw 候选 / 空召回 query / namespace 分布 / top1 文件排行。`--days N` `--json` 双模式
  - `harness/health/checks/retrieve_hitrate.py`（新）：周期面板检查。zero_hit ≥30% → warning，单 kw share ≥0.5 → warning
  - `harness/health/runner.py`：import retrieve_hitrate 触发注册
  - `harness/maintenance_manifest.json`：token_savers 加入 analyze_retrieve_log
  - `harness/generate_catalog.py`：sections 加 "上下文治理脚本" → 自动扫 `harness/scripts/*.py` 入 README
  - `harness/README.md`：catalog 重生，含新增脚本
  - `feedback/feedback_harness_maintenance_flow.md`（新）：5 步入流程文档化（docstring/manifest/catalog/health/CHANGELOG），防止以后新脚本被遗忘
- **触发**：harness-context-governance E5 NEG_FAIL 暴露 `kw:tool:ue` 万金油，但无数据回路证明、无衡量手段。先落数据基础设施，再回头改 keywords。
- **验证**：
  - 跑 retrieve 后 `tail -1 ~/.claude/logs/retrieve_calls.jsonl` 得合规 JSON ✅
  - `analyze_retrieve_log.py` 识别 `kw:tool:ue` freq=5 share=0.833 ✅
  - `health/runner.py --check retrieve_hitrate` warning 2 条（空召回 + 噪声 kw） ✅
  - `harness_memory_lint.py feedback_harness_maintenance_flow.md` PASS ✅
  - `generate_catalog.py` 重生 README 含 analyze_retrieve_log + harness_retrieve ✅

### [2026-05-20] [FEAT] harness/tests/* — L4-D 预 apply 仿真 + L4-E Codex 驱动探活
- **来源任务**：D:/ClaudeTasks/active/harness-context-governance
- **变更内容**：
  1. 新增 `harness/tests/context_governance/regression/test_l4_staged_apply.py`（12 用例）：tmp_path 合并 24 个 `.proposed` → 跑 retrieve → 写 L4D-STAGED-METRICS.md → 卡 gate 70%（target 90%）
  2. 探活 codex CLI v0.132.0 在 wt 可弹可见可 tee（脚本 `D:/ClaudeTasks/active/harness-context-governance/codex-runs/spawn_codex.ps1`，发现 codex 需 `--skip-git-repo-check`，Tee 默认 UTF-16 改 UTF-8）
  3. 写 `D:/ClaudeTasks/active/harness-context-governance/L4E-CODEX-RUNBOOK.md`（外部 Codex 当模拟用户生成 user_msg → 喂 retrieve → 量真实命中）
  4. 5 个真实任务场景 prompt：`codex-runs/scenarios/E1-pyside-qss.txt` ... `E5-ue-puerts.txt`
- **测试**：65/65 PASS in 1.92s（原 53 + 新 L4-D 12）
- **关键发现 (L4-D 暴露)**：真数据下命中率 73%（8/11）。3 个 link-error query 全推 `compile_after_module_change` 而非 `common_build_errors` → 两个 build error 文件 sidecar keywords 没区分，G4 apply 前要修
- **遗留**：L4-E `run_l4e.py` 驱动器待用户审批 runbook §8 后再写

### [2026-05-20] [FEAT] context-governance · 方向 B 骨干（P0-P2 + tests）
- **变更内容**：
  1. 新增 `harness/scripts/`：harness_retrieve.py / triggers_vocab.yaml / scan_dual_storage.py / check_trigger_coverage.py / add_trigger_metadata.py / context_meter.py / gate_check.py / test_context_governance.py
  2. 新增 `harness/tests/context_governance/`：L1 单元×11 + L2 集成×7 + L3 烟测×5 = 23 用例（pytest 全绿 0.72s）
  3. 生成 24 `.proposed` 触发 frontmatter sidecar（feedback×13 / knowledge×9 / fixes×2）—— **未 apply**，原文件 0 改动
  4. 生成 `MEMORY.md.proposed`（1430B vs 原 8805B，可省 ~1843 token）—— **未 swap**
  5. git tag `pre-context-governance-cleanup`（基线锚点）
- **bug fix**：retrieve cache JSON 写不支持 YAML `date` → `json.dumps(default=str)`，新增 U11 回归用例
- **未动**：MEMORY.md / 任何 feedback/knowledge/fixes 原文件 / settings.json / hooks

### [2026-05-20] [FEAT] note skill 支持文件
- **变更内容**：新增 `harness/note.py`（便利签管理脚本）和 `notes.md`（便利签存储）

### [2026-05-19] [FEAT] route-system-v2：lane 分类 + 职能 agent + 行为审计
- **变更内容**：
  1. 废弃 route_gate 强制计划文件机制（Goodhart 问题），route_check 改为默认静默 nudge
  2. 新建 4 个职能 agent：sidecar-explorer(haiku)/log-triage(sonnet)/bounded-worker(sonnet)/code-reviewer(sonnet)
  3. 新建 agent_prompt_gate.py（PreToolUse Agent，5选3质量门）
  4. CLAUDE.md 路由从高/低耦合二分改为 5 Lane 分类（A主模型/B探索/C Worker/D Reviewer/E模型策略）
  5. audit_logger/subagent_logger 补 turn_id，subagent_stop_logger 记录撞上限信息
  6. route_audit.py 重写：读真实日志统计 subagent 调用频次/撞上限/missed opportunities

### [2026-05-18] [UPDATE] 任务路由优化：检查清单 + 低耦合表扩展
- **变更内容**：CLAUDE.md 路由规则从"宁可不派"改为"过检查清单才派"。新增 4 条派遣检查清单（输入自包含/输出可验证/无前序依赖/无后续阻塞）。低耦合表新增 CHANGELOG 生成、单文件新建、模板化修改三类。独立文档/commit message 免检直接派

### [2026-05-18] [FEAT] /work 轻量模式重设计 + CHANGELOG 降级
- **变更内容**：
  1. 轻量 /work 从"缩水版完整流程"变为"智能挂靠器"：--match 匹配活跃任务 DESIGN Step，匹配到则 claim_step 挂靠，没匹配到则创建独立文件夹+HANDOFF
  2. CHANGELOG 检查从 warning 降为 info，版本级变更记 README Release Notes
  3. /work 启动自动写 .current_task 标记（statusline 显示）

### [2026-05-17] [UPDATE] 全仓库 docstring/frontmatter 中文化 + catalog 重生成
- **变更内容**：26 个文件的描述从英文改为中文（agents 4 个、skills 8 个、harness 脚本 8 个、hooks 3 个、verify 2 个），重新生成 3 个子目录 README

### [2026-05-17] [FEAT] v1.2.0 — 仓库目录梳理 + Release Notes + 架构图
- **变更内容**：
  1. 新增 `harness/generate_catalog.py` — 从 docstring/frontmatter 自动生成子目录 README
  2. 生成 `agents/README.md`、`skills/README.md`、`harness/README.md`
  3. 主 README 追加组件调用关系图 + Release Notes 段 + 子目录文档链接
  4. VERSION 更新到 1.2.0
  5. CLAUDE.md 新增版本级变更规则（Release Notes + VERSION 同步）

### [2026-05-17] [FEAT] Phase 2: DESIGN.md 替代 SPEC.md + /work skill 改造
- **来源项目**：multi-agent-sync 任务 Phase 2
- **变更内容**：
  1. `SKILL.md` 所有 SPEC 引用改为 DESIGN，implement 描述改为执行蓝图
  2. `check_doc_status.py` 双向兼容：find_project_docs 同时搜索 DESIGN.md 和 SPEC.md
  3. `check_doc_sync.py` 双向兼容：优先找 DESIGN.md，没有再找 SPEC.md
  4. `project_registry.json` required_docs 和 implementation 列表从 SPEC.md 改为 DESIGN.md
  5. 新增 `DESIGN_模板.md` 模板文件

### [2026-05-16] [FIX] 审查修正：advisory 定位 + registry 路径 + step 事件
- **来源项目**：multi-agent-sync 设计审查
- **变更内容**：
  1. `sync_inject.py` TASKS_ROOT 改从 project_registry.json 读取，去掉硬编码
  2. `sync_inject.py` 增加 claim_step/complete_step 事件图标
  3. `task_sync.py` VALID_EVENTS 增加 claim_step/complete_step

### [2026-05-16] [FEAT] 多 Agent 同步基础设施 + harness 修复
- **来源项目**：harness / multi-agent-sync 任务
- **变更内容**：
  1. 新增 `harness/task_sync.py` — 共享事件流 CLI（append/read/locks/release）
  2. 新增 `harness/hooks/sync_inject.py` — UserPromptSubmit hook，每轮注入其他 agent 状态
  3. `bootstrap.py` hooks_json() 补注册 UserPromptSubmit（changelog_inject + sync_inject）
  4. `agents/CLAUDE.md` 添加 Multi-Agent Sync 协议
  5. `harness/post_task_hook.py` 修复：git sync 失败从 error 降为 warning；error 写 stderr
  6. `harness/hooks/statusline.py` 精简重写：只保留 git branch + context 压力警告
  7. `skills/work/v1/SKILL.md` + `HUMAN_DOC_STYLE.md` 中 § 符号替换为章节标题引用
- **原因/案例**：多终端分工时彼此不知道对方进展，编辑器/设备互踩；stop hook git sync 间歇性失败导致 "No stderr output"；statusline 显示信息密度低

### [2026-05-15] [FIX] verify/ 和 reporting/ 子目录 _lib import 路径修复
- **来源项目**：harness 1.0.0 收敛重构
- **变更内容**：11 个文件 sys.path.insert 从 `parent` 改为 `parent.parent`，指向 harness/ 根目录的 _lib.py；verify_all.py 的 verify_docs.py 引用加 verify/ 前缀
- **原因/案例**：doctor 验证发现 ModuleNotFoundError: No module named '_lib'——文件移到子目录后 sys.path 仍指向当前目录

### [2026-05-15] [UPDATE] pre-1.0.0 审查修复
- **来源项目**：harness 1.0.0 收敛重构
- **变更内容**：harness-history-boundary-review.md 审查期间的修正——agents 配置微调、bootstrap 改进、doc_gate/work_context_pack 降低误伤、maintain.py 增强、work skill 流程简化、文档模板精简
- **原因/案例**：审查过程中发现的边界问题就地修复，纳入 1.0.0 基线

### [2026-05-15] [RELEASE] v1.0.0 — 四层架构基线
- **来源项目**：harness 1.0.0 收敛重构
- **变更内容**：
  - 定义四层架构：L1 Rules / L2 Skills / L3 Subagent / L4 Scripts + Utilities
  - harness/ 目录重组：verify/、reporting/、md2html/ 三个新子目录
  - 删除废弃文件：旧 Tkinter panel、cleanup.sh、spike
  - 权威入口收敛：maintain doctor 唯一默认，check_health.py 降级 legacy
  - 文案迁移：去"铁律"硬匹配，verifier 匹配四层架构关键词
  - Git 卫生：清除 15 个已跟踪 pyc 文件
  - 创建 VERSION 文件，README 重写为架构文档
- **原因/案例**：harness-history-boundary-review.md 审查后执行的收敛型重构。从"快速铺设+频繁校正"阶段过渡到版本化稳定基线

### [2026-05-15] [UPDATE] 文案和 verifier 迁移
- **来源项目**：harness 1.0.0 收敛重构
- **变更内容**：verify_prompt_system.py 去"铁律"硬匹配，改为匹配四层架构关键词；CLAUDE.md "三层金字塔" → "四层架构"；交叉引用检查模式更新
- **原因/案例**：review 文档 §1.4 识别 verifier 锚定旧词拉回旧模式

### [2026-05-15] [UPDATE] 权威入口收敛
- **来源项目**：harness 1.0.0 收敛重构
- **变更内容**：check_health.py 标记 DEPRECATED，从 doctor 默认路径降级到 legacy_deep_checks；maintain doctor 定为唯一权威健康入口；RULE_ENFORCEMENT_MATRIX.md 标记 v1 待重评
- **原因/案例**：消除双重健康检查真相源，review 文档 §1.3 识别的核心问题

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


### 2026-05-20 FEAT harness/scripts/* — Context Governance L4 alias+fuzzy
- **来源任务**：D:/ClaudeTasks/active/harness-context-governance
- **变更内容**：
  1. `harness/scripts/triggers_aliases.yaml` 新增（13 类 alias，覆盖 diff/vscode/qt/qss/pyside/ui/build/link/shader/cpp/thread/ue/workflow）
  2. `harness_retrieve.py` 新增 `load_aliases()` / `expand_query()` / `_levenshtein_le1()` / `_fuzzy_token_match()`；scoring 加 fuzzy 分支（精确=2.0 / fuzzy=1.4）
  3. `add_trigger_metadata.py` v2：拉 alias YAML + 扫正文前 80 行 + 多 tag + H1→description + `--regenerate` 选项
  4. 测试目录新增 `tests/context_governance/regression/`：`test_l4_fuzzy.py`（10）+ `test_l4_realtasks.py`（18）+ `test_l4_hitrate.py`（1，含 L4-METRICS.md 生成）
  5. `unit/test_retrieve.py` 新增 U12（alias 展开）
  6. `test_context_governance.py` 加 regression 层
  7. 24 个 `.proposed` sidecar 用 v2 逻辑重生成，等用户人工 review → `--apply`
- **G1+G6 落地**：D:/global-memory/projects/{control-panel-v1, control-panel-v2-pyside, harness-governance-v1, token-cost-governance} 4 个 dup 文件夹清理（独有文件先 merge 到 active/archived）；settings.json atlassian + playwright 关
- **测试**：53/53 PASS in 1.14s；L4 命中率 100%（8/8 期望条目）≥ 80% 门禁
- **遗留**：G4（trigger coverage 0%）+ G5（MEMORY.md 8805B）仍需用户决策 apply


### 2026-05-20 FIX harness_retrieve.py — cache tmp-path 泄漏
- **来源任务**：D:/ClaudeTasks/active/harness-context-governance
- **症状**：dry-run 推荐 pointers 指向已删除的 `C:/Users/.../Temp/l4e_staged_*/...`
- **根因**：`~/.claude/cache/triggers.json` 全局单文件不按 memory_root 隔离；L4-E 测试用 tmp memory_root 覆写 cache；后续读取时 mtime 检查只看子目录里现存文件，tmp 已删 → 0 个 mtime > cache_mtime → 旧 tmp 数据原样回灌
- **变更**：
  1. 新增 `_cache_path_for(memory_root)`：md5(resolve(memory_root))[:8] → `triggers_<hash>.json`
  2. `load_trigger_cache` 加 sanity check：cached entry path 必须以 memory_root 开头，否则强制重扫
  3. CLI `--cache` 默认改 None → 由 `--memory-root` 派生
  4. 删 stale `~/.claude/cache/triggers.json`
- **回归**：65/65 PASS in 1.56s。conftest/integration/regression 都显式传 cache_path 不受影响
- **影响**：未来不同 memory_root（生产 / 测试 / staged）cache 各自独立，互不串扰


### 2026-05-20 FEAT G4 apply · 24 sidecar 合并入源
- **来源任务**：D:/ClaudeTasks/active/harness-context-governance
- **动作**：
  1. 24 个 `.proposed` strip TODO 标记（用户授权）
  2. `add_trigger_metadata.py --apply` 合并 frontmatter 入源 .md（applied=24）
  3. rm stale `~/.claude/cache/triggers_*.json` 强制 cache 重扫
- **覆盖率**：trigger coverage 0% → 92.31%（24/26；decisions/ 2 个 SUBS 排除）
- **scope 内 lint**：24/24 PASS
- **retrieval 验证**：dry-run `diff vscode` 命中 `feedback_diff_workflow.md` kw:tool:diff
- **回归**：65/65 PASS in 1.50s
- **遗留**：①decisions/conventions.md + decision_work_mode_workflow.md 待手工补 trigger（SUBS 范围）②MEMORY.md 8805B 待 slim（G5）
## 2026-05-20 P3-LINT 完结 · 模板 + CLAUDE.md 写记忆规则
- 写 4 模板：D:/global-memory/templates/memory_{feedback,knowledge,fixes,decision}.md.tmpl
- 改 D:/global-memory/agents/CLAUDE.md（~/.claude/CLAUDE.md 是 symlink）：加 "## 记忆文件写入规范" 段，硬约束 + 模板路径 + lint 自查命令
- 冒烟：手工 Write fixes/fix_retrieve_cache_tmp_path_leak.md → lint PASS 一次过

## 2026-05-20 L4-E 改 ground truth + 重跑
- run_l4e.py:39 E2-R2 android_build_and_test → None（文件在 ~/.claude/projects/，不在 global-memory）
- run_l4e.py:45 E5-R2/R3 mcp_troubleshooting → None（同上）
- --skip-codex 重跑：precision 46%→60% (6/10)，neg 50%→60% (3/5)
- 剩余 NEG_FAIL：E5-R1/R2 被 feedback_code_style/learning_path 当 desc-token noise 命中


## 2026-05-20 L4-E precision 60%→100% (补 4 keyword)
- knowledge_qt_pyside_styling: +concept:polish +tool:pyside
- knowledge_cpp_multithreading: 替 tool:ue → concept:tsan/lock_guard/mutex
- feedback_diff_workflow: 替 tool:ue/workflow → concept:git/vscode/cherry-pick
- 经验：concept: ns 不过 lint source check (只校 tool:)；substring 子串注意连字符 vs 空格（git-log ≠ git log）

### 2026-05-21 13:19 CREATE CONTRIBUTING.md
- **来源项目**：harness-context-governance
- **变更内容**：harness 接入指南：hook/skill/script/memory/agent/CLAUDE.md 接入规范
- **原因/案例**：之前 work 流程文档不全 + harness 收束后无新增物接入说明书
- **影响范围**：harness-context-governance 项目

### 2026-05-21 13:19 UPDATE harness/hooks/retrieve_inject.py
- **来源项目**：harness-context-governance
- **变更内容**：write_retrieve_log 异常改写 debug 日志而非 silent pass
- **原因/案例**：诊断 cc 调度下 log 不写盘的真因
- **影响范围**：harness-context-governance 项目

## 2026-05-22

- [feat] **harness 内核优化** (harness-usage-audit P3 实施)：
  - `harness/scripts/harness_retrieve.py` MAX_POINTERS 5→2 (D5-B1，治读端注入过载)
  - 3 文件 frontmatter 修剪 `concept:workflow` 泛 keyword：`feedback/feedback_diff_workflow.md` / `decisions/decision_work_mode_workflow.md` / `feedback/feedback_collaboration_meta.md`（D5-B2，治召回噪声）
  - 新 `harness/health/checks/retrieve_pointer_consumption.py` (D5-B5)：复用 `analyze_retrieve_log.compute_consumption`，7d call_rate/pointer_rate 报警
  - 新 `harness/health/checks/lint_failure_rate.py` (D8)：把 `memory_lint_gate.jsonl` 从 write-only 转活
  - `harness/health/runner.py` imports +2，runner 8→10 checks
- [docs] 不新增 daemon/hook（接 D3+D4 红线）；全部走既有 health check 复用模式


- [MEMORY] **6 候选记忆入库** (harness-usage-audit 复盘提取)：
  - `fixes/fix_sidecar_summary_verify_reader.md` — sidecar「无消费方」结论必须 grep reader 验证
  - `fixes/fix_health_runner_module_invocation.md` — health/runner.py 需 `python -m harness.health.runner` 启动
  - `decisions/decision_retrieve_optim_roi_priority.md` — retrieve 5 维优化 ROI 排序
  - `decisions/decision_respect_user_override_recommendation.md` — 尊重用户「不动」拍板，不二次说服
  - `knowledge/knowledge_retrieve_metrics_taxonomy.md` — retrieve 3 指标语义区分（zero_hit / pointer_rate / call_rate）
  - `knowledge/knowledge_health_check_register_3steps.md` — health check 新增 3 步法
  - 全部 6/6 lint PASS


- [ARCHIVE] **active/ 批量清理 5 老结构任务**（用户拍板）：
  - `xd-adaptive-performance-refactor`（XDAP 重构，老结构）
  - `diff-workflow-redesign`
  - `route-system-v2`
  - `harness-context-governance`（retrieve 链上游，已被 harness-usage-audit 接力）
  - `harness-governance-v1`（governance 老版）
  - 全部 mv 至 `D:/ClaudeTasks/archived/`，无 retro 提取（旧格式无 core/ 结构）


## 2026-05-22 [ARCHIVE] active 清理批 2
- mv `aik-frontend-refactor` → archived/（P1-P16 全完成）
- mv `claude-system-cleanup` → archived/（批次 1-3 + P0 全完成，32d 未动）
- 删孤儿 junction `control-panel-v2-pyside`（target D:\global-memory\projects\... 已删）
- 删孤儿 junction `token-cost-governance`（同上）
- active/ 剩 8 个（feedback-loop-v1 / harness-handoff-sync-gate / localds-perf-capture / multi-agent-sync / puerts-ai-prototype / sync-commit-noise-reduction / tapmaker-puerts-ai-ue / token-routing-optimization）

### 2026-06-01 11:01 CREATE docs/subsystem-map.md
- **来源项目**：workflow梳理(6-agent)
- **变更内容**：五大子系统功能图：injector/compiler/global-check/startup/governance + 配套关系图
- **原因/案例**：用户要求梳理 global-memory 主功能并存档速查
- **影响范围**：workflow梳理(6-agent) 项目

### 2026-06-01 11:18 UPDATE skills/skill-creator/v1/
- **来源项目**：anthropics/skills (Apache-2.0)
- **变更内容**：用官方 skill-creator 全量覆盖本地版：新增 scripts/(package_skill/run_eval/quick_validate等) + references/schemas.md + agents/ + eval-viewer/；旧版备份 v1_local_backup_20260601
- **原因/案例**：审计发现本地版死引用 init_skill.py/package_skill.py + license字段矛盾，官方版治本
- **影响范围**：anthropics/skills (Apache-2.0) 项目

### 2026-06-01 11:18 UPDATE agents/CLAUDE.md + docs/subsystem-map.md
- **来源项目**：fix_hardcoded_paths.py --fix
- **变更内容**：过时硬编码 D:/global-memory 路径归一为 ~/.claude/global-memory
- **原因/案例**：G9 硬编码路径检查命中
- **影响范围**：fix_hardcoded_paths.py --fix 项目

### 2026-06-01 11:25 UPDATE skills/smoke-test/v1/SKILL.md + skills/work/v1/SKILL.md
- **来源项目**：文档审计修复
- **变更内容**：smoke-test:修正死路径 ~/.claude/scripts/smoke_test.py→harness/verify/smoke_test.py + description措辞(硬编码清单subprocess执行);work:description 4→5 子目录(补_archive)
- **原因/案例**：审计阻断+drift项,用户确认修
- **影响范围**：文档审计修复 项目

### 2026-06-01 11:42 UPDATE skills/{check,diff,work,smoke-test}/SKILL.md
- **来源项目**：文档审计修复#2
- **变更内容**：4处 bash→PowerShell：date+FMT→Get-Date、echo -n→Set-Content -NoNewline、$(date)→$(Get-Date)、TS赋值
- **原因/案例**：默认shell为PowerShell,示例需可直接复制运行
- **影响范围**：文档审计修复#2 项目

### 2026-06-01 11:42 UPDATE harness/verify/verify_all.py
- **来源项目**：文档审计修复#2b/#3
- **变更内容**：新增 check_powershell_compat 检查项:扫SKILL.md的bash块flag POSIX习语(date+/echo -n//dev/null/NAME=);含_backups/archived路径排除(防审计误读旧副本)
- **原因/案例**：用户要求把bash兼容检查固化进确定性脚本+审计排除备份目录
- **影响范围**：文档审计修复#2b/#3 项目

### 2026-06-01 11:42 UPDATE harness/create_task.py + env
- **来源项目**：文档审计修复#1
- **变更内容**：create_task 改 import config.CLAUDE_TASKS_ACTIVE替代硬编码D:/ClaudeTasks;setx CLAUDE_TASKS_ROOT=D:/ClaudeTasks 持久化,任务路径单一来源(config/env驱动,16消费模块统一)
- **原因/案例**：create_task硬编码与config默认~/.claude/tasks脑裂,潜在bug
- **影响范围**：文档审计修复#1 项目

### 2026-06-01 14:06 UPDATE commit 69be979
- **来源项目**：本会话提交说明
- **变更内容**：本会话修复 commit 一并含此前未提交 backlog: work/v1/SKILL.md 由轻量/完整模型重写为 task_template 5子目录模型; agents/CLAUDE.md 新增 AI 质量门段
- **原因/案例**：缠绕文件 backlog 与本会话改动无法干净分离,经用户确认保留
- **影响范围**：本会话提交说明 项目

### 2026-06-01 14:25 UPDATE skills/skill-creator/v1/{eval-viewer/viewer.html,assets/eval_review.html}
- **来源项目**：本会话补全
- **变更内容**：git add -f 强加官方 skill-creator 的 2 个 eval 查看器 HTML 模板(被 .gitignore *.html 排除),否则 fresh clone 后 generate_review.py 读不到模板会崩
- **原因/案例**：保官方 skill 完整可移植
- **影响范围**：本会话补全 项目

### 2026-06-01 14:35 UPDATE harness/verify/verify_all.py
- **来源项目**：本会话
- **变更内容**：check_powershell_compat 加 _VENDORED_SKILLS 白名单,跳过上游 vendored skill(skill-creator),其 bash 示例随上游不强制 PS
- **原因/案例**：官方 skill-creator bash 习语为上游代码,误报 WARN 噪音
- **影响范围**：本会话 项目

### 2026-06-01 14:35 UPDATE skills/work/v1/SKILL.md
- **来源项目**：本会话
- **变更内容**：work:54 残留 echo -n→Set-Content -NoNewline(backlog 重写新增的第二处)
- **原因/案例**：PowerShell 兼容检查命中
- **影响范围**：本会话 项目

### 2026-06-03 14:22 CREATE feedback/feedback_doc_single_version_no_supersede_record.md
- **来源项目**：harness-3layer-architecture任务
- **变更内容**：新增feedback:文档单一版本,不留取代横幅/不标权威版v2v3,旧稿直接删,更替只在CHANGELOG记
- **原因/案例**：用户明确要求,删除文档迭代时挂取代横幅是噪声
- **影响范围**：harness-3layer-architecture任务 项目

### 2026-06-12 CREATE interview/basics-checklist-2026-06.md
- **来源项目**：秋招顾问对话
- **变更内容**：新增秋招基础/八股S/A/B分级清单(频率×简历关联度排序),含统一验收标准(90秒口答+一层追问)与防镀金负面清单;同日 knowledge_cpp_multithreading.md 学习路线已重排为3周冲刺版
- **原因/案例**：用户自列基础清单存在三大遗漏(网络八股/vtable/STL底层)且未分层,整理为可追进度的checklist供learning agent出题
- **影响范围**：interview/ 学习路线


### 2026-06-19 CREATE skills/collab + harness/collab
- **来源项目**：xd-maker-agent-collab-standalone
- **变更内容**：新增 collab skill、host-neutral 协同配置/adapter/dispatch plan 模块、`harness/scripts/collab_plan.py`、collab 单元测试，并注册 experimental capability / scripts registry / 自动目录。
- **原因/案例**：把 XDMaker/Orca 协同能力先落成 global-memory 可验证插件骨架，不复制 UI/host 依赖、不提升 client full-lifecycle 声明。
- **影响范围**：skills/collab、harness/collab、collab_plan CLI、capability/docs registry。

### [2026-06-23] [SKILL] 新增 document-structure-restorer
- 新增 `skills/document-structure-restorer/v1/SKILL.md`：中文文档结构重建流程，用于把被反复追加、补丁化、层级混乱的文档重新整理成完整、AI 可读的稳定结构。
- 刷新 `skills/README.md` 自动目录。


### [2026-06-23] [MIGRATE] 移除 Skill v1 中间层
- 将 `skills/<name>/v1/*` 扁平迁移为 `skills/<name>/*`，删除所有空 `v1` 目录；Skill 真源不再使用单独版本层。
- 更新 bootstrap、Claude/Codex skill 同步、catalog、skill audit、work skill 渲染脚本、部署脚本和相关测试的真源路径。
- 更新当前维护文档中的 Skill 布局说明；历史 CHANGELOG/change-packet 路径保持原样作为历史记录。
