---
name: skill-auditor
description: Skill 结构合规检查。验证文件完整性、渐进隔离分层。
---

# Skill 结构合规检查器

> 定位：Skill 质量体系的第一层门槛。只检查"结构对不对"，不判断"好不好用"。

## 能力边界

| 能做到 | 做不到 |
|--------|--------|
| 文件完整性 | 指令是否真的有效 |
| 格式规范 | 比裸跑好多少 |
| 语法正确 | 长期是否稳定 |
| Token 成本预估 | 别人能不能用 |
| Harness 结构覆盖 | Harness 是否真正起作用 |

**Skill 质量的五个层次（本工具只覆盖第 1 层）：**
```
第5层：生态质量 — 别人用了也好使吗？
第4层：演化质量 — 越用越好还是越用越烂？
第3层：效能质量 — 比不用 Skill 好多少？      ← 需要 A/B 对比
第2层：行为质量 — 输出稳定一致吗？            ← 需要一致性测试
第1层：结构质量 — 文件完整、格式正确、能跑     ← 本工具覆盖
```

## 使用方式

优先运行 deterministic audit。这是本 Skill 的硬启动动作，不是可选建议：

```bash
python ~/.claude/scripts/audit_skill.py --skill <skill-name-or-path>
python ~/.claude/scripts/audit_skill.py --all --json
```

运行后必须先基于脚本输出判断 `PASS / CONDITIONAL / FAIL`。脚本会写入 `~/.claude/logs/harness_tool_invocations.jsonl` 作为“脚本实际运行过”的证据；Claude 的 `tool_audit.jsonl` 仍是“AI 是否直接调用”的证据。

AI 只解释脚本输出和给修复建议，不再手工重复检查 YAML、行数、引用文件和部署 junction。脚本不可用时，必须在报告开头声明：`audit_skill.py 未运行`，再降级按以下清单逐项验证：

**必检项（🔴 不通过则 FAIL）：**
1. `SKILL.md` 文件是否存在
2. YAML frontmatter 是否完整（name/description/version/created/updated）
3. description 是否包含触发条件说明
4. SKILL.md 行数是否 ≤ 500 行

**建议项（🟡 缺失计入 CONDITIONAL）：**
5. 是否有 examples/ 目录或内联示例
6. 如引用了 scripts/，对应文件是否存在
7. 如引用了 references/，对应文件是否存在
8. Token 成本是否合理（行数 × 1.2 ≈ token 数，建议 < 600 tokens）

```
# 手动运行示例（AI 在对话中逐项检查）
# 1. 读取目标 Skill 目录结构
# 2. 读取 SKILL.md
# 3. 按上述清单逐项判定
# 4. 输出 PASS / CONDITIONAL / FAIL
```

## 判定标准

| 判定 | 条件 | 含义 |
|------|------|------|
| **PASS** | 无 🔴，🟡 ≤ 2 | 结构合规，可进入效能验证 |
| **CONDITIONAL** | 无 🔴，🟡 3~5 | 基本合规，有改进项 |
| **FAIL** | 🔴 ≥ 1 或 🟡 > 5 | 结构不合规，需修复 |

判定优先级：`脚本 exit code > 命令输出 > AI 判断`

## 报告末尾固定附带"下一步建议"

每份报告都会明确告诉用户：结构检查通过只是第一步，还需要做 A/B 对比测试和一致性测试。
具体步骤模板见报告输出。

## 参考文档
- `references/design-tradeoffs.md` — 设计决策权衡
- `references/review-dimensions.md` — 检查维度定义
