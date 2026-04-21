---
name: smoke-test
description: >
  基础设施冒烟测试。自动运行 ~/.claude/scripts/ 下所有脚本（verify/sync/hooks 等），
  验证无崩溃、编码错误、路径失效。测试逻辑在 Python 脚本中，Skill 只做编排，极省 token。
  Use when: 用户说"冒烟测试""smoke test""跑一遍脚本""检查基础设施"，
  或修改了 scripts/hooks/global-memory 后需要验证完整性。
---

# smoke-test

## 流程

### Step 1: 运行测试

```bash
python ~/.claude/scripts/smoke_test.py --log --json
```

读取 JSON 输出，解析 `summary` 字段获取 PASS/WARN/FAIL/SKIP 计数。

### Step 2: 报告结果

向用户展示汇总表：

| 状态 | 数量 | 说明 |
|------|------|------|
| PASS | N | 正常通过 |
| WARN | N | 退出码非零但无崩溃（列出具体脚本） |
| FAIL | N | 有 Traceback 或超时（列出具体脚本+错误摘要） |
| SKIP | N | 有副作用，已跳过 |

如有 FAIL，逐个列出失败脚本和 `detail` 字段。

### Step 3: Git 同步（仅全 PASS 或仅 WARN 时）

```bash
git -C ~/.claude/global-memory add -A && git -C ~/.claude/global-memory commit -m "smoke-test: $(date +%Y%m%d_%H%M%S) PASS" && git -C ~/.claude/global-memory push
```

有 FAIL 时**不同步**，提示用户先修复。

## 注意事项

- 测试清单硬编码在 `smoke_test.py` 的 `MANIFEST` 中，新增脚本需手动注册
- `--log` 写入 `~/.claude/logs/smoke_test.log`（自动轮转）
- `--json` 输出供本 Skill 解析，不要用终端格式
- 每个脚本超时 30s，超时判定为 FAIL
