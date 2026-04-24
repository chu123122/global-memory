# ADR-002 · registry 作为单一数据源

- **状态**:Accepted
- **创建**:2026-04-24
- **关联 Phase**:0(human_doc_patterns)、1-B(rule list)、2-A(active tasks)、2-B(漂移扫描)、4-A(任务列表)
- **关联横切原则**:DESIGN §1.4 第 2 条

## 背景

harness 的脚本/hook/skill 需要知道:活跃任务列表、任务路径、人类文档命名模式、阶段-必备文档映射、tasks_root 等。这些信息有两种来源:

- **registry 单源**:统一存 `~/.claude/projects/project_registry.json`
- **散落硬编码**:每个脚本/hook 自己维护一份字典常量

当前实际状态(grep 结果):
- ✅ 大部分脚本已读 registry(`stage_lib.py`、`doc_gate.py`、`check_doc_status.py` 等)
- ❌ 部分脚本仍 hardcode(`generate_project_context.py:43` 写死 `("docs/TECHNICAL_DESIGN.md", ...)`)
- ❌ test_stage_lib.py 测试用例 hardcode "REQUIREMENTS.md / DESIGN.md" 字符串(虽在 fixtures 里,但 Phase 0 重命名时需要同步改)

## 候选方案

### A. 强制 registry 单源(本 ADR 选定)

所有运行时数据从 registry 读;脚本不允许 hardcode 任务名/路径/文件名模式。
**优**:改一处全局生效;Phase 0 改 `human_doc_patterns` 立刻被所有脚本认;新增任务/字段不需改代码。
**劣**:registry 字段膨胀;多脚本读同一文件需注意并发(本场景非高频写,可忽略)。

### B. 散落硬编码 + 集成测试兜底

每脚本自己维护;靠 CI 测试发现不一致。
**优**:每脚本独立可读;无外部依赖。
**劣**:Phase 0 这种全局变更要改 N 处;遗漏一处就 silently 退化(本任务 §10.2 文件名约定就是这种 silently 退化的产物)。

### C. 注入式(每脚本 main 函数显式接受配置参数)

调用方传入 config;脚本本身无源。
**优**:可测试性最高;依赖反转。
**劣**:对 hook 不友好(hook 由 Claude Code 直接 spawn,没法注入);引入复杂度大于收益。

## 选定

**A(registry 单源)**。

理由:
- 散落硬编码是 §10.2 文件名约定 bug 的根因——已经吃过亏
- 与 §1.4 第 2 条横切原则一致
- Phase 0 / 1-B / 2-A / 2-B / 4-A 多个 Phase 都需要从 registry 读,统一规则成本最低

## 后果

**优**:
- Phase 0 改 `human_doc_patterns` 一行,所有脚本立刻生效
- 新加任务只需 registry 加 entry,无脚本改动
- 漂移扫描(Phase 2-B)有明确比对基准:实际行为 vs registry 声明

**劣**:
- registry 文件本身成为"超级配置文件",字段会膨胀——靠 ADR + schema_version(ADR-007)管控
- registry 解析失败/字段缺失需要 fail-fast(避免脚本默认值掩盖错误)

**风险**:
- registry 字段命名歧义/重叠 → 走 ADR 记录每个新字段的语义和归属层(L1-L5)
- 不同脚本对同字段语义理解不一致 → Phase 2-B 漂移扫描兜底

## 关联

- 落实在:几乎所有 Phase
- 强制约束:Phase 1-B RULE_MATRIX 必须列出"哪些脚本读了 registry 哪些字段",作为漂移扫描基准
- 反例(应当修复):`generate_project_context.py:43` hardcode → 列入 Phase 1-A 之后的 cleanup 单
