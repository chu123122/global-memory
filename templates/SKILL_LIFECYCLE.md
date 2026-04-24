# Skill 生长闭环规范

> 位置：~/.claude/global-memory/templates/SKILL_LIFECYCLE.md
> 用途：定义 Skill 从诞生到成熟到退役的完整生命周期
> 核心原则：Skill 不是设计出来的，是从重复劳动中长出来的

---

## 一、Skill 生命周期

```
 观察          提取          验证          成熟          下沉/退役
  │             │             │             │             │
  ▼             ▼             ▼             ▼             ▼
┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐
│ 🌱  │───>│ 🌿  │───>│ 🌳  │───>│ 🏛️  │───>│ ⬇️  │
│萌芽 │    │成长  │    │验证  │    │稳定  │    │下沉  │
└─────┘    └─────┘    └─────┘    └─────┘    └─────┘
 手动做了    提取为     3+次使用   10+次使用   固定步骤
 3+次同     SKILL.md   评分≥3.5   评分≥4.0   抽为Script
 类操作     +1个示例   +3个示例   + 反例
```

## 二、各阶段触发条件与动作

### 🌱 萌芽（观察期）

**触发**：你发现自己手动做了 3+ 次类似的操作（给 AI 类似的指令、做类似的检查、走类似的流程）

**动作**：在 `global-memory/knowledge/knowledge_skill_design.md` 中记一条：

```markdown
## 潜在 Skill 观察
- [日期] [操作描述]：已手动做了 N 次，考虑提取
```

**不做**：不急着写 SKILL.md。先确认是通用模式还是偶然重复。

### 🌿 成长（提取期）

**触发**：确认是通用模式（至少能想到 3 个不同场景会用到）

**动作**：

1. 创建 `global-memory/skills/[skill-name]/v1/SKILL.md`
2. 写至少 1 个 example（输入→期望输出）
3. 创建 `CHANGELOG.md`
4. 建软链接到 `skills/`

**检查清单**（提取时必须过）：

```
- [ ] SKILL.md ≤ 500 行
- [ ] 有 YAML 头部（name, description）
- [ ] description 用第三人称写触发条件
- [ ] 至少 1 个 example
- [ ] CHANGELOG.md 存在
```

**元数据**：在 SKILL.md 头部标注

```yaml
maturity: seed   # seed / growing / verified / stable
use_count: 0
```

### 🌳 验证（打磨期）

**触发**：实际使用 3+ 次后

**动作**：

1. 补充 example 到 3 个（含至少 1 个反例/边界案例）
2. 在每个 example 末尾记录实际评分：

```markdown
## 使用记录
| 日期 | 场景 | 评分(1-5) | 问题 | 改进 |
|------|------|----------|------|------|
```

3. 根据使用反馈修改 SKILL.md（**修改前先问：通用问题还是特殊场景？**）
4. 更新 `maturity: growing → verified`

**关键防线——防过拟合**：

修改 Skill 前必须回答：
1. **这个改动适用于所有使用场景吗？** → 是 → 改 SKILL.md
2. **只适用于当前场景？** → 是 → 不改 SKILL.md，记入 example 作为特殊案例
3. **不确定？** → 先不改，标注为"待观察"，等下次遇到再判断

### 🏛️ 稳定

**触发**：10+ 次使用，平均评分 ≥ 4.0

**动作**：
1. 更新 `maturity: verified → stable`
2. 锁定核心流程——之后只能加 example，不能改核心逻辑（除非重大 Bug）
3. 如果要大改，创建 `v2/`，保留 `v1/` 作为回退

### ⬇️ 下沉 / 退役

**下沉触发**：Skill 中某个步骤的逻辑完全固定，无需 AI 判断

**动作**：把该步骤抽取为 Script（bash/python），Skill 中改为调用 Script

```
SKILL.md 中的步骤：
  "检查所有 .cpp 文件的语法"
    ↓ 下沉为
  scripts/check_cpp_syntax.sh
    ↓ SKILL.md 改为
  "运行 check_cpp_syntax.sh 并处理结果"
```

**退役触发**：6 个月未使用

**动作**：移入 `global-memory/skills/_archived/[skill-name]/`，删除软链接

---

## 三、版本升级流程

```
v1/ 稳定运行中
    ↓ 发现需要结构性改动
创建 v2/（从 v1 复制并修改）
    ↓ 更新软链接指向 v2
~/.claude/skills/xxx → global-memory/skills/xxx/v2
    ↓ v2 经过 3 次验证后
v1 标记为 deprecated，保留 30 天
    ↓ 30 天后
v1/ 归档或删除
```

**版本升级 CHANGELOG 格式**：

```markdown
## v2 (YYYY-MM-DD)
### 为什么升级
- [具体原因，引用使用记录中的问题]

### 变更内容
- [具体改了什么]

### 不兼容变更
- [如果有的话]

### 回退方式
- 将软链接指回 v1 即可
```

---

## 四、Skill 质量指标

| 指标 | 怎么算 | 健康标准 |
|------|--------|---------|
| 使用频率 | 最近 30 天使用次数 | ≥ 1 次/月 |
| 平均评分 | 最近 5 次使用的平均分 | ≥ 3.5 (verified) / ≥ 4.0 (stable) |
| 示例覆盖率 | examples 数量 / 已知使用场景 | ≥ 50% |
| 过拟合风险 | SKILL.md 修改次数 / 使用次数 | ≤ 0.3（每 3 次使用最多改 1 次）|

---

## 五、与 verify_all.py 的集成

`verify_all.py` 中的 `check_skill_line_limits` 检查 SKILL.md ≤ 500 行。
后续可以扩展检查：
- [ ] 每个 verified+ 的 Skill 至少有 3 个 example
- [ ] 每个 stable 的 Skill 有使用记录
- [ ] 6 个月未使用的 Skill 标记为退役候选
