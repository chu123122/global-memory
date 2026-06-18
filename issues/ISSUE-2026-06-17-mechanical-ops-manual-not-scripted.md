---
issue_id: mechanical-ops-manual-not-scripted
status: open
severity: minor
created: 2026-06-17
source: 2026-06-17 本会话复盘：/work 流程中机械确定性操作（占位符替换 / rename / 跑 update_phase_status.py·check_doc_sync.py / 生成 STATUS）被手动执行，而 /work 已内置这套脚本——重复脚本该干的活、浪费上下文、违反铁律 #8
tags: [workflow, work, tooling, scripts, context-cost, agent-discovery, doc]
---

# 机械确定性操作被手动重做，没走 /work 已有的脚本（根因：工具发现缺失）

## 事实

- 铁律 #8：确定性变换用代码不用 AI。属于「机械确定性」的活：占位符替换、文件 rename、跑校验脚本（用户举例 `update_phase_status.py` / `check_doc_sync.py`）、生成 STATUS 等。
- `/work` 流程**已经内置**了这套脚本。
- 但实际执行时这些操作被**手动 cp / 替换**完成 = AI 花上下文去重做脚本该干的确定性活。
- 后果：① 浪费上下文（token）；② 手工产出可能和脚本产出不一致（STATUS / 状态字段格式漂移风险）。

## 根因（疑似）

- **工具发现缺失**：AI 在某个任务目录 / 文件夹下工作时，不知道这里有哪些相互关联的脚本可用，于是 fallback 到手动操作。
- 不是脚本不存在，是「调用方不知道脚本存在 / 不知道该用哪个」——发现层断了。

## 影响

- 每个 /work 任务都可能重复踩：确定性活手动做 → 持续的上下文浪费。
- 侵蚀「AI 只做判断活」的边界（铁律 #8）。
- 手动产出与脚本产出不一致时，引入难察觉的格式 / 状态漂移。

## 修复方向（候选，未锁定）

1. **用户的想法**：在各个文件夹下各放一份 `CLAUDE.md` + `AGENTS.md`（两者内容相同），介绍该目录下相互关联的工具 / 脚本，让 AI 进入该目录工作时自动发现「这些活该调脚本，不该手动做」。
   - CLAUDE.md 给 Claude Code、AGENTS.md 给 Codex 等其他 agent，内容相同是为跨 agent 兼容（本库本就 Claude/Codex 共享）。
   - **风险（待解）**：两份内容相同 = 双副本，会漂移；一旦分叉不知哪份为准。更稳的是单一真源 + 生成另一份——本库已有先例 `harness/scripts/render_codex_work_skill.py`（从共享源生成 codex 变体），另见 `ISSUE-2026-06-03-registry-single-source-autoindex.md` 的单源思路。
   - **成本（待评估）**：CLAUDE.md 会按目录 just-in-time 拉进上下文，放进每个文件夹会增量抬高进入该目录时的常驻 token，和本库「压永驻 token」目标相冲。权衡：可能只在「确有脚本可调」的目录放，而非所有文件夹。
2. **替代 / 补充**：把「该目录有哪些脚本、什么活必须调脚本」做成可被 retrieve 召回的指针（走现有记忆 / Context Brief），而不是落成每目录的静态文件——零新增常驻成本，但依赖召回命中。
3. **行为侧**：在 /work skill 里加一个检查点——动手做确定性活前，先查本目录 / registry 有无对应脚本。

## 验收标准（修完怎么算好）

- [ ] AI 在 /work 任务里遇到机械确定性活（rename / 占位符 / STATUS / 跑既有校验脚本），会先发现并调用对应脚本，而不是手动做。
- [ ] 工具发现机制有单一真源，不靠双副本手工同步（或有生成步骤保证一致）。
- [ ] 方案的常驻 token 成本被评估过，只在必要目录承载发现信息。

## 负面清单（别做）

- 不要为了发现就在每个文件夹塞两份手维副本却没有同步机制——会漂移成新债。
- 不要只在某次 prompt 里提一句「记得用脚本」——要落进可检查的机制（skill 检查点 / 目录文件 / registry）。

## 关联

- 铁律 #8（确定性变换用代码）、#6（别静默超支上下文预算）。
- 相关 issue：`ISSUE-2026-06-03-registry-single-source-autoindex.md`（单一真源思路）。
- 先例：`harness/scripts/render_codex_work_skill.py`（从共享源生成 codex 变体，避免双写漂移）。
- 决策：`decisions/decision_work_mode_workflow.md`（/work 作为统一入口）。
- 待补：① 确认用户举例脚本的实际名称 / 位置（`update_phase_status.py` 已存在于 `harness/scripts/`；`check_doc_sync.py` 未在该目录扫到，需核实真实名称）；② /work 已有脚本清单落在 registry 何处。
