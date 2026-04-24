# RULE ENFORCEMENT MATRIX

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

## 矩阵 v1(覆盖 8 hooks + 6 hard rules,共 14 行)

| rule_id | description | strength | enforcer | failure_behavior | smoke_test_id | source |
|---|---|---|---|---|---|---|
| **RULE-001** | 拦截 `rm -rf` / `git reset --hard` / `DROP TABLE` / fork bomb 等危险 Bash | S1 | `harness/hooks/dangerous_command_blocker.py` | deny | TBD-Phase3 | `settings.json` PreToolUse Bash |
| **RULE-002** | 改 `CLAUDE.md` / `agents/` / `conventions` → 弹确认;改 `global-memory` 其他文件 → 放行+日志 | S1 | `harness/hooks/memory_file_protector.py` | ask | TBD-Phase3 | `settings.json` PreToolUse Write\|Edit |
| **RULE-003** | 编辑 `watched_paths` 下的文件时,按 task `Status` 阶段检查每个活跃任务的必填文档(中文人类向 + AI 派生) | S1 | `harness/hooks/doc_gate.py` | deny | TBD-Phase3 | `settings.json` PreToolUse Write\|Edit;registry `human_doc_patterns` / `required_docs_by_stage` |
| **RULE-004** | 所有工具调用追加审计到 `~/.claude/logs/tool_audit.jsonl` | S1(被动写) | `harness/hooks/audit_logger.py` | log | TBD-Phase3 | `settings.json` PostToolUse * |
| **RULE-005** | Subagent 启动记录到 `~/.claude/logs/subagent_audit.jsonl` | S1(被动写) | `harness/hooks/subagent_logger.py` | log | TBD-Phase3 | `settings.json` SubagentStart |
| **RULE-006** | 白名单目录内 Edit/Write 前先备份原文件到 `<task>/.diff/now/<name>.<sha8>.bak` | S1 | `harness/hooks/diff_backup.py` | log | TBD-Phase3 | `settings.json` PreToolUse Write\|Edit |
| **RULE-007** | 白名单目录内 Edit/Write 后异步弹 VS Code diff 三栏视图(5s 内同文件不重弹) | S1 | `harness/hooks/diff_show.py` | log-only | TBD-Phase3 | `settings.json` PostToolUse Write\|Edit |
| **RULE-008** | Stop 事件触发 post_task_hook:索引同步 + CHANGELOG 检查 + auto-fix + git push | S1(副作用大) | `harness/post_task_hook.py --auto-fix` | log + 副作用 | TBD-Phase3 | `settings.json` Stop |
| **RULE-009** | memory 文件总数不超过 `MAX_FILES`(当前 80,Phase 1-A 调高) | S2 | `harness/verify_memory.py` MEM-09 | warning | TBD-Phase3 | `_lib.py` 常量 + `verify_memory.py` |
| **RULE-010** | 命名/输出风格遵循 CLAUDE.md(不擅自加 emoji / 不写废话 / 不自评质量) | S3 | AI/human | none | manual | CLAUDE.md 铁律 |
| **RULE-011** | 审查只报告不修复(三种例外可直修:注释错别字、行尾空格、文件末尾换行) | S3 | AI/human | none | manual | CLAUDE.md 铁律 |
| **RULE-012** | 不代替用户对外发言(只草拟,用户确认后自己发送) | S3 | AI/human | none | manual | CLAUDE.md 铁律 |
| **RULE-013** | 写 REQUIREMENTS/DESIGN 前必读 `HUMAN_DOC_STYLE.md` + `style-refs/` 至少 1 份样例 | S3 | AI/human | none | manual | `feedback_human_doc_style` memory + `work skill SKILL.md` Step 1 |
| **RULE-014** | 用户给反馈/纠正/元偏好时,主动写 memory 并明确告知"已记忆到 X" | S3 | AI/human | none | manual | `feedback_collaboration_meta.md` §2 |

## v1 覆盖范围与已知缺口

**已覆盖**:
- 全部 8 个 hook 配置(7 个 PreTool/PostTool/SubagentStart + 1 个 Stop)
- 6 条 CLAUDE.md / feedback 提取的硬规则

**已知缺口(v2 补)**:
- 对每条 S1 hook 加"近 7 天实际触发证据"列(由 Phase 2-B 漂移扫描填充)
- 对 S3 加"复盘频率"字段(每月 review 一次哪些 S3 应升 S2)
- post_task_hook 的"auto-fix + git push 副作用"细化为子条目(对应 §10.1 auto-fix 噪音问题)

## v1 与 Phase 3 / 2-B 的接口契约

- **Phase 3**(smoke_test_hooks.py)实现时:
  - 为每条 `TBD-Phase3` 行写一个 happy + 一个 fail 用例(共 8×2 = 16 个测试)
  - 每用例 docstring 第一行写 `SMK-NNN` ID
  - 反向回填本表的 smoke_test_id 字段(把 TBD-Phase3 改为 SMK-NNN)
- **Phase 2-B**(verify_doc_drift.py)实现时:
  - 校验本表的 enforcer 字段实际指向的脚本/hook 文件存在
  - 校验本表的 smoke_test_id 在 Phase 3 完成后无 `TBD-*` 残留
  - 校验本表的 source 字段(settings.json hook / CLAUDE.md 引用)实际生效

## 修订记录

- v1 (2026-04-24):harness-governance-v1 Phase 1-B 创建,14 行覆盖 8 hooks + 6 hard rules
