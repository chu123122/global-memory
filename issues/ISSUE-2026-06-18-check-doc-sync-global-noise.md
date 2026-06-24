---
issue_id: check-doc-sync-global-noise
status: open
severity: major
created: 2026-06-18
source: game-proto-mapping work 收尾验证：运行 check_doc_sync.py 时输出大量无关历史任务告警
tags: [workflow, work, tooling, validation, noise, v2-task]
---

# `check_doc_sync.py` 默认全局扫描导致任务内验证被无关旧任务噪音淹没

## 事实（现场）

在 `game-proto-mapping` 任务中，lead 为复核 maintainer 文档改动运行：

```powershell
python ~/.claude/skills/work/scripts/check_doc_sync.py
```

脚本输出不是只检查当前任务，而是扫描 `D:\ClaudeTasks\active` 下大量任务，产生大量与当前收尾无关的告警：

- 多个旧任务的 `SPEC.md` / `HANDOFF.md` 不存在。
- 多个几十天未更新的旧任务文档 stale warning。
- 若干已不存在任务目录的告警。
- 对当前 v2 任务 `game-proto-mapping` 也报 `SPEC.md` / `HANDOFF.md` 不存在，因为该任务实际使用 `core/HANDOFF.md` 等 v2 结构。

用户随后纠正：这应记录为 **global-memory issue**，不是 `game-proto-mapping` task-local 债。

## 根因（疑似）

`check_doc_sync.py` 的默认行为仍偏向“全局活跃任务扫描 / legacy 平铺结构检查”，但 `/work` Step 4 在单个任务收尾时直接调用它。

因此两个职责混在一起：

1. **任务内收尾验证**：只回答“当前 task 的文档是否同步”。
2. **全局健康巡检**：扫描所有 active tasks，报告历史任务 stale / 缺文档 / 目录缺失。

当前命令名和调用位置让 AI 预期它是 #1，但实际输出包含大量 #2。

## 影响

- 任务收尾时，真正需要看的当前任务信号被全局旧任务噪音淹没。
- AI 容易把“全局巡检噪音”误判为当前任务风险，或反过来忽略当前任务真告警。
- v2 任务使用 `core/HANDOFF.md` / `design/设计文档.md`，但脚本仍报根目录 `HANDOFF.md` / `SPEC.md` 不存在，形成假阳性。
- 违反“验证应服务当前成功判据”的原则：单 task 验证不应默认输出全局 unrelated backlog。

## 修复方向（候选，未锁定）

1. **默认作用域改为当前任务**：
   - 优先从 `work_context_pack.py --json` / session task 绑定 / `cwd` 解析当前 task。
   - 默认只检查该 task。
   - 全局扫描改为显式 `--all` 或 `--scan-all`。
2. **增加显式参数**：
   - `--task <task-id>`：只检查指定 task。
   - `--task-dir <path>`：只检查指定目录。
   - `--all`：保留当前全局扫描行为。
3. **v2 结构感知**：
   - v2 task 识别 `core/HANDOFF.md`、`core/STATUS.md`、`design/设计文档.md`、`ops/CHANGELOG.md`。
   - 不再对 v2 task 误报根目录 `SPEC.md` / `HANDOFF.md` 缺失。
4. **输出分级**：
   - 当前 task 的阻断/告警放在最前。
   - 全局巡检项若显式启用，单独归入 “global health warnings”，避免和 task-local validation 混杂。
5. **同步 work skill 调用**：
   - `/work` Step 4 应调用 `check_doc_sync.py --task <task-id>` 或等价 scoped 命令。

## 验收标准（修完怎么算好）

- [ ] 在 `game-proto-mapping` 这类 v2 task 内运行默认 `check_doc_sync.py` 时，只输出当前任务检查结果，不列出无关旧任务。
- [ ] v2 task 不再因缺根目录 `SPEC.md` / `HANDOFF.md` 被误报；能识别 `core/HANDOFF.md`。
- [ ] 需要全局巡检时，必须显式传 `--all`，且输出标题明确为 global health scan。
- [ ] `/work` 收尾调用路径更新为 scoped 检查，避免再次出现“全局老任务噪音”。
- [ ] 增加至少一个回归测试：构造两个 active tasks，其中一个 stale；在另一个 task 里 scoped 检查时不输出 stale task 告警。

## 负面清单（别做）

- 不要只让 AI 在读输出时“自行忽略全局噪音”——验证工具应默认给当前任务可读信号。
- 不要删除全局扫描能力；它仍有维护价值，但必须显式触发。
- 不要用扩大输出说明替代作用域修复；真正问题是默认作用域错。

## 关联

- 脚本：`skills/work/scripts/check_doc_sync.py`
- 流程：`skills/work/v1/SKILL.md` Step 4 收尾检查
- 相关问题：`ISSUE-2026-06-17-mechanical-ops-manual-not-scripted.md`（/work 确定性脚本发现与使用边界）
