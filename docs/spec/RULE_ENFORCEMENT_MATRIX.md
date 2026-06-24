# RULE ENFORCEMENT MATRIX

> **v2 — 2026-06-04 全量合并：矩阵补全 17 hooks（8→17，+9 缺失 hook）+ 加 claude_rule_id 列（RULE-NNN↔R 交叉）+ CLAUDE 铁律 R1-R19 索引（层规格引用权威）。smoke 由 smoke_test_hooks.py 回填（25 case 全绿）。**
> harness 治理体系的规则到执行点的显式映射。Phase 1-B v1 产物(harness-governance-v1)。
> 真值源:本文件。Phase 2-B 的 `verify_doc_drift.py` 按本表自动校验偏离;Phase 3 的 `smoke_test_hooks.py` 反向回填 `smoke_test_id` 字段。
>
> 字段定义见 ADR-003(smoke_test_id 共享 schema);强度 S1/S2/S3 见 DESIGN §1.3 信任边界。

## 字段说明

- **rule_id**:`RULE-NNN` 全局递增,不复用
- **description**:一句话规则内容
- **strength**:`S1` 硬阻断 / `S2` 软校验 / `S3` 文档约定(AI 自觉)
- **enforcer**:实际执行的脚本/hook 路径,或 `AI/human`(纯文档约定)
- **failure_behavior**:`deny` / `ask` / `warn` / `log` / `none`
- **smoke_test_id**:`TBD-Phase3` 占位,Phase 3 实现 smoke 用例时反向回填具体 `SMK-NNN`;`manual` 表示无法机器化测试(纯 AI 自觉)
- **source**:规则来源(settings.json hook 配置 / CLAUDE.md 铁律 / feedback memory / 等)

## 矩阵 v2(覆盖 17 hooks + 6 hard rules,共 23 行)

> `claude_rule_id` 列 = 该强制点背后的 CLAUDE 行为铁律（多数 hook 是基础设施，无对应铁律，标 —）。
> `smoke_test_id` 由 `harness/verify/smoke_test_hooks.py`（matrix v2，25 case 全绿）回填。

| rule_id | description | strength | enforcer | failure_behavior | smoke_test_id | claude_rule_id | source |
|---|---|---|---|---|---|---|---|
| **RULE-001** | 拦截 `rm -rf` / `git reset --hard` / `DROP TABLE` / fork bomb 等危险 Bash | S1 | `harness/hooks/dangerous_command_blocker.py` | deny | SMK-001H/F | — | `settings.json` PreToolUse Bash |
| **RULE-002** | 改 `CLAUDE.md` / `agents/` / `conventions` → 弹确认;改 `global-memory` 其他文件 → 放行+日志 | S1 | `harness/hooks/memory_file_protector.py` | ask | SMK-002H/F | R3(关联) | `settings.json` PreToolUse Write\|Edit |
| **RULE-003** | 编辑 `watched_paths` 下的文件时,按 task `Status` 阶段检查每个活跃任务的必填文档 | S1 | `harness/hooks/doc_gate.py` | deny | SMK-012H(放行); deny-path 待 fixture | — | `settings.json` PreToolUse Write\|Edit;registry `required_docs_by_stage` |
| **RULE-004** | 所有工具调用追加审计到 `~/.claude/logs/tool_audit.jsonl` | S1(被动写) | `harness/hooks/audit_logger.py` | log | SMK-003H/R | — | `settings.json` PostToolUse * |
| **RULE-006** | 白名单目录内 Edit/Write 前先备份原文件到 `<task>/.diff/now/<name>.<sha8>.bak` | S1 | `harness/hooks/diff_backup.py` | log | SMK-009BH/R | — | `settings.json` PreToolUse Write\|Edit |
| **RULE-008** | Stop 事件触发 post_task_hook:索引同步 + CHANGELOG 检查 + auto-fix + git push | S1(副作用大) | `harness/post_task_hook.py --auto-fix` | log + 副作用 | SKIP(git push 副作用,不在 smoke 跑) | — | `settings.json` Stop |
| **RULE-009** | memory 文件总数不超过 `MAX_FILES` | S2 | `harness/verify_memory.py` MEM-09 | warning | manual(非 hook) | — | `_lib.py` 常量 + `verify_memory.py` |
| **RULE-010** | 命名/输出风格遵循 CLAUDE.md(不擅自加 emoji / 不写废话 / 不自评质量) | S3 | AI/human | none | manual | **R14** | CLAUDE.md 铁律 |
| **RULE-011** | 审查只报告不修复(三种例外可直修:注释错别字、行尾空格、文件末尾换行) | S3 | AI/human | none | manual | **R18** | CLAUDE.md 铁律 |
| **RULE-012** | 不代替用户对外发言(只草拟,用户确认后自己发送) | S3 | AI/human | none | manual | **R19** | CLAUDE.md 铁律 |
| **RULE-013** | 写 REQUIREMENTS/DESIGN 前必读 `HUMAN_DOC_STYLE.md` + `style-refs/` 至少 1 份样例 | S3 | AI/human | none | manual | — (执行层规格) | `feedback_human_doc_style` memory + work SKILL |
| **RULE-014** | 用户给反馈/纠正/元偏好时,主动写 memory 并明确告知"已记忆到 X" | S3 | AI/human | none | manual | — (沉淀层规格) | `feedback_collaboration_meta.md` §2 |
| **RULE-015** | 大文件 Read 前拦截/告警(防上下文爆) | S2 | `harness/hooks/read_large_file_guard.py` | warn | SMK-005H/R | — | `settings.json` PreToolUse Read |
| **RULE-016** | Agent 派遣前检查 subagent prompt 质量(5 选 3) | S1 | `harness/hooks/agent_prompt_gate.py` | ask | SMK-006R | — | `settings.json` PreToolUse Agent |
| **RULE-017** | 记忆文件写入须有合规 frontmatter(keywords/tags/last_updated/status) | S1 | `harness/hooks/memory_lint_gate.py` | deny | SMK-007H/R | — (沉淀层规格 frontmatter 硬约束) | `settings.json` PreToolUse Write\|Edit |
| **RULE-019** | Bash 后注入学习机会提示 | S3(注入) | `harness/hooks/learning_opportunity_nudge.py` | none | SMK-011R | — | `settings.json` PostToolUse Bash |
| **RULE-020** | UserPromptSubmit 注入 CHANGELOG(关键词命中) | S3(注入,fail-open) | `harness/hooks/changelog_inject.py` | none | SMK-010 | — | `settings.json` UserPromptSubmit |
| **RULE-022** | UserPromptSubmit 路由 nudge(低耦合提示) | S3(注入,fail-open) | `harness/hooks/route_check.py` | none | SMK-010 | — | `settings.json` UserPromptSubmit |
| **RULE-023** | UserPromptSubmit 注入 Context Brief(记忆召回) | S3(注入,fail-open) | `harness/hooks/retrieve_inject.py` | none | SMK-010 | R8(召回=确定性变换) | `settings.json` UserPromptSubmit |

## v1 覆盖范围与已知缺口

**已覆盖(v2)**:
- 全部 13 个 hook 配置(UserPromptSubmit×3 + PreToolUse×7 + PostToolUse×2 + Stop + statusLine；subagent/sync/diff_show hooks 已退役)
- 6 条 CLAUDE.md / feedback 提取的硬规则
- smoke 25 case 覆盖 12 hooks(全绿);claude_rule_id 列建立 RULE-NNN↔R 交叉

**已知缺口(后续)**:
- 对每条 S1 hook 加"近 7 天实际触发证据"列(由漂移扫描填充)
- post_task_hook smoke(git push 副作用,需隔离 fixture);doc_gate deny-path smoke(需 fake task+registry fixture)
- statusLine 未建 RULE-NNN 行(每帧渲染,非约束点)
- 本表 hook 行镜像 `hook_manifest.json` → 纳入 `docs/多数据源治理方案.md` M1(reconcile 自动渲染后本表 hook 段改派生)

## v1 与 Phase 3 / 2-B 的接口契约

- **Phase 3**(smoke_test_hooks.py)实现时:
  - 为每条 `TBD-Phase3` 行写一个 happy + 一个 fail 用例(共 8×2 = 16 个测试)
  - 每用例 docstring 第一行写 `SMK-NNN` ID
  - 反向回填本表的 smoke_test_id 字段(把 TBD-Phase3 改为 SMK-NNN)
- **Phase 2-B**(verify_doc_drift.py)实现时:
  - 校验本表的 enforcer 字段实际指向的脚本/hook 文件存在
  - 校验本表的 smoke_test_id 在 Phase 3 完成后无 `TBD-*` 残留
  - 校验本表的 source 字段(settings.json hook / CLAUDE.md 引用)实际生效

## CLAUDE 铁律 R1-R19 索引（四层架构·层规格引用权威）

> 四层规格（`rules/*.md`）以 R 号引用全局铁律。本表 = R 号↔铁律名↔强制点 的权威映射。
> 铁律全文单一源 = `agents/CLAUDE.md`（本表只索引，不复述条文）。
> 多数 R 是 S3 行为约定（AI 自觉），少数有 hook/脚本背书（标 RULE-NNN）。

| R | 铁律名 | 主要强制 | 背书强制点 |
|---|--------|---------|-----------|
| R1 | Think before coding | S3 自觉 | — |
| R2 | Simplicity first | S3 自觉 | — |
| R3 | Surgical changes | S3 自觉 | RULE-002（改保护文件弹确认） |
| R4 | Read before write | S3 自觉 | — |
| R5 | Goal-driven | S3 自觉 | — |
| R6 | Checkpoint | S3 自觉 | — |
| R7 | Match codebase conventions | S3 自觉 | `verify_conventions.py`（项目级 conventions 硬检查） |
| R8 | AI 只做判断活 | S3 自觉 | — |
| R9 | 恢复边界 | S3 自觉 | — |
| R10 | Fail loud + 不掩饰 | S3 自觉 | — |
| R11 | Surface conflicts | S3 自觉 | — |
| R12 | 被指出错误→承认+根因+修正 | S3 自觉 | — |
| R13 | Tests verify intent | S2/S3 | `quality_gate.py`（Tier 2+ 测试证据） |
| R14 | 直接给方案+不自评 | S3 自觉 | RULE-010 |
| R15 | 讨论模式先给观点 | S3 自觉 | — |
| R16 | 自主验证不中断 | S3 自觉 | — |
| R17 | 同错 3 次停 | S3 自觉 | — |
| R18 | 审查只报告不改代码 | S3 自觉 | RULE-011 |
| R19 | 不代替对外发言 | S3 自觉 | RULE-012 |

> 落地期待办（matrix v2）：RULE-NNN 与 R 号全量双向合并为一张表 + 各 R 的 7 天触发证据列。本次仅建索引使层规格引用可解析。

## 修订记录

- v1 (2026-04-24):harness-governance-v1 Phase 1-B 创建,14 行覆盖 8 hooks + 6 hard rules
- v1.1 (2026-04-24):Phase 3 MVP 反向回填 RULE-001/002/004/005 的 smoke_test_id 为 SMK-NNN(各对应 happy + fail 用例)。RULE-003/006/007/008/009 仍 TBD-Phase3-v2 未覆盖(doc_gate / diff_backup / diff_show / post_task_hook / verify_memory MEM-09 留 v2)
- v1.2 (2026-06-03):harness 四层架构落地。加「CLAUDE 铁律 R1-R19 索引」使 `rules/*.md` 层规格的 R 号引用可解析
- v2 (2026-06-04):全量合并。矩阵 8→17 hooks（补 RULE-015~023：read_large_file_guard/agent_prompt_gate/memory_lint_gate/subagent_stop_logger/learning_opportunity_nudge/changelog_inject/sync_inject/route_check/retrieve_inject）+ 加 claude_rule_id 列。smoke_test_hooks.py 扩到 25 case（matrix v2，全绿），回填 RULE-003/006/007 的 smoke_test_id。修 smoke 真 bug：HARNESS_DIR 路径（文件移入 verify/ 后 parent 算错→hooks 找不到）
