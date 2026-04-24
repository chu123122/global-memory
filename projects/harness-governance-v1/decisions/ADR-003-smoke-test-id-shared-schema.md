# ADR-003 · smoke_test_id 作为 RULE_MATRIX 与 smoke 的共享 schema

- **状态**:Accepted
- **创建**:2026-04-24
- **关联 Phase**:1-B(RULE_MATRIX 定字段)、3(smoke_test_hooks 反向回填)
- **关联横切原则**:DESIGN §1.4 第 3 条

## 背景

Phase 1-B 的 RULE_ENFORCEMENT_MATRIX 列每条规则,Phase 3 的 smoke_test_hooks 跑 hook 回归测试。**两者必须能对账**——给定一条规则,要能找到对应的 smoke 用例;给定一个 smoke 用例,要能查出它验证的规则。

不对账的失败模式:
- 矩阵列了 6 条规则,smoke 只跑了 4 条,但没人发现少了哪两条
- smoke 用例改名/删除,矩阵的"smoke 状态"列还指向旧用例
- 加了新规则没补 smoke,通过门禁仍 PASS

## 候选方案

### A. 引入 `smoke_test_id` 字段(本 ADR 选定)

矩阵每行有 `smoke_test_id` 列(`SMK-001` / `SMK-002` ...);smoke 脚本每个用例 docstring 第一行写对应 ID。漂移扫描比对两边 ID 集合。
**优**:对账机制简单;新增规则 → 矩阵填 `TBD-Phase3` → Phase 3 实现时回填具体 ID;ID 全局唯一,grep 即可。
**劣**:ID 命名空间需要管理(防止重复 / 跨 ADR 复用)。

### B. 用规则名当 key 关联

矩阵行的"规则名"字段直接等于 smoke 用例函数名。
**优**:无新字段。
**劣**:命名耦合——规则改名 = smoke 函数改名 = 全部 grep 改;长名字不利于 ID 标识。

### C. 不要对账机制,靠人工 review

每次改规则/smoke 时 reviewer 自己保证一致。
**优**:零机制成本。
**劣**:跟"靠 AI 自觉"一样不可靠;Phase 2-B 漂移扫描没法机器化执行。

## 选定

**A(`smoke_test_id` 字段)**。

理由:
- §1.4 第 3 条横切原则要求两边对账机器可验证
- ID 是稳定 anchor,规则改名/重写不会破坏关联
- Phase 1-B v1 里所有 `smoke_test_id` 都填 `TBD-Phase3`(占位),Phase 3 实现时反向回填具体 ID——形成"文档先于实现、实现回填文档"的闭环
- 这条机制本身可以被 Phase 2-B 漂移扫描验证(grep `TBD-Phase3` 应在 Phase 3 完成后归零)

## 后果

**优**:
- Phase 1-B 与 Phase 3 解耦,可不同步开发
- 漂移扫描(Phase 2-B)有具体可执行规则:`所有 SMK-NNN 必须在 smoke 脚本和 matrix 各出现 1 次`
- ID 出现在 task_outcomes.jsonl 的 lesson 字段时,可直接溯源到对应规则

**劣**:
- ID 命名空间需要 ADR 管(本 ADR 不细化,Phase 1-B 启动时定;参考 RFC 风格三位数递增)
- Phase 1-B v1 的 `TBD-Phase3` 占位会持续 1-2 周直到 Phase 3 完成,期间漂移扫描会有 "已知未实现" 噪音 → 漂移扫描需支持白名单忽略 `TBD-*`

**风险**:
- ID 重复 → 命名空间管理 + Phase 2-B 扫描去重检测
- smoke 脚本拆分/重组导致 ID 漂移 → ID 写在用例 docstring 第一行,grep 即可定位

## 关联

- 落实在:Phase 1-B(矩阵字段定型) + Phase 3(用例反向回填)
- 被 Phase 2-B 引用:漂移扫描的"smoke 覆盖完整性"规则
- 命名空间细则:留给 Phase 1-B 启动时的子决策(不另起 ADR,记入 Phase 1-B 详细设计)
