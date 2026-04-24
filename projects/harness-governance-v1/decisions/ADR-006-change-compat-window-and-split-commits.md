# ADR-006 · 变更兼容期 + 拆 commit

- **状态**:Accepted
- **创建**:2026-04-24
- **关联 Phase**:0(文件名约定)、4-A(schema 演化)、未来所有 schema/约定变更
- **关联横切原则**:DESIGN §1.4 第 6 条

## 背景

harness 治理体系的几乎所有变更都涉及"约定切换":文件命名、registry 字段、JSONL schema、hook 行为。如果每次变更都"原子切换"(一次 commit 改完所有引用),会出现:

- 中途某个引用没改 → silent 失败,被掩盖
- 回滚时要么全回滚要么全保留,无中间态
- review commit 困难(diff 太大)

参考软件工程界的"灰度发布"和数据库的"扩展-收缩"(expand-contract)模式。

## 候选方案

### A. 原子切换(一个 commit 改全部)

**优**:历史干净,无中间态。
**劣**:diff 巨大难 review;一处遗漏 silent 失败;回滚要么全回要么全保留;实施过程中触发 auto-fix hook 会撕裂状态。

### B. 双名 / 双通道兼容期 + 拆 commit(本 ADR 选定)

把变更拆成 3 个 commit:
1. **expand**:让系统同时认旧和新约定(无破坏性,可回滚)
2. **migrate**:把所有存量从旧切到新(纯重命名/搬运)
3. **contract**:删除旧约定支持

每两个 commit 之间是"兼容期",系统两种约定并存。

**优**:每步独立可回滚;diff 小易 review;兼容期允许并行存量未迁移和新建已迁移;失败可停在 commit 1 或 2 任一点,系统仍可用。
**劣**:总 commit 数多;需要写"兼容代码"作为 commit 1 的产物(临时但必要)。

### C. 渐进迁移(每次新建用新约定,存量随机会迁移)

**优**:零集中工作量。
**劣**:存量永远不收敛,新旧并存成长期状态;可维护性持续退化。

## 选定

**B**。

理由:
- 我们已被"原子切换的隐性失败"咬过(§10.2 文件名约定 bug 就是因为最初没拆 commit,silent 错了一年才发现)
- 拆 commit 的额外工作量是一次性的,渐进迁移的代价是无限的
- expand-contract 模式有成熟先例(数据库 schema 演化、API 版本切换)

## 后果

**优**:
- 每个 commit 独立可回滚,bisect 友好
- 兼容期允许"边迁移边正常用",不停服
- review 时 diff 小,人脑可控
- silent 失败几率降低(commit 1 加双名,commit 2 grep 验证全切完,commit 3 删 fallback——三道关)

**劣**:
- commit 历史多 2 条(对比方案 A);但 git log 用 `--first-parent` 或 squash 视图可隐藏
- commit 1 的"兼容代码"是临时品(commit 3 会删),感觉不清爽

**风险**:
- commit 2 中途被 `post_task_hook` auto-fix 自动 commit 撕裂 → DESIGN §2.6 风险表已识别,执行前手动停 daemon
- commit 3 漏删某处 fallback → grep 在 commit 3 的 PR description 里强制贴

## 关联

- 落实在:Phase 0(三 commit 拆分)、未来所有 schema 变更
- 触发本 ADR 的横切原则:DESIGN §1.4 第 6 条
- 与 ADR-007 互补:本 ADR 管"约定切换的过程",ADR-007 管"schema 自身的版本演化"
