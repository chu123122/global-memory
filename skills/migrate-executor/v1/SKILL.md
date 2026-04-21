---
name: migrate-executor
description: Code and resource migration executor — dependency analysis, migration plan, step-by-step execution with rollback, and regression verification. Use when the user needs to migrate modules, split packages, or refactor across 3+ files.
---

# 搬迁执行助手

> Execute code migrations step by step. Core principle: small increments, every step rollbackable, automated verification.

## 输入
```
搬迁目标：[什么东西要搬到哪里]
原因：[为什么要搬]
约束：[不能动的东西 / 兼容性要求]
```

## 执行流程

### Step 1：依赖分析
- 列出搬迁对象的所有依赖（上游和下游）
- 画出依赖图（文本格式）
- 标注高风险依赖（公共模块/循环依赖）

### Step 2：制定搬迁计划
- 拆分为可独立执行的步骤
- 每步有明确的输入/输出/验证条件
- 标注每步的回退方案
- 输出格式：

```markdown
## 搬迁计划

### Step 1: [描述]
- 操作：[具体做什么]
- 验证：[怎么确认成功]
- 回退：[失败了怎么办]

### Step 2: [描述]
...
```

### Step 3：逐步执行
- 一次只执行一步
- 每步执行后立即验证
- 验证失败 → 回退 → 分析原因 → 调整计划

### Step 4：全量验证
- 编译通过
- 运行脚本验证（优先用 scripts/ 下的现成脚本）
- 功能回归测试

### Step 5：清理 + 记录
- 删除过渡代码
- 更新文档
- 如有通用经验 → 写入 knowledge/

## 搬迁原则
- **先加后删**：先在新位置添加，确认可用后再删旧的
- **保持编译通过**：每一步都要能编译
- **最小影响**：优先搬不影响其他模块的部分
- **自动化验证**：能用脚本验证的不靠人工

## 关联记忆
- 搬迁中发现的通用模式 → knowledge/
- 踩过的坑 → fixes/
- 架构决策 → decisions/
