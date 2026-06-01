---
doc_type: template
status: active
last_updated: 2026-05-21
trigger:
  keywords: [concept:gate, tool:gate_check, concept:checklist]
  tags: [tooling, workflow]
---

# Gate Gx 接入模板

> 想把一个检查脚本变成「gate_check 必跑、违反 BLOCK」的硬关。本文档给完整步骤。
>
> 当前 Gate 列表与 G1-G8 见 `harness/scripts/gate_check.py`。
> 加新 Gx 前先看 `docs/scripts-registry.md` 确认脚本未被任何 Gate 覆盖。

---

## 前提

你的检查脚本必须满足：

| 条件 | 要求 |
|---|---|
| 退出码 | 0 = 通过；非 0 = 违规 |
| stdout | 含一个可被 grep 的稳定标志字符串（例：`dual_count=0`、`coverage=100.00%`）|
| 运行时间 | < 60s（gate_check 默认 timeout）|
| 副作用 | 只读（写报告 OK，改文件不行）|
| 失败模式 | 缺依赖 → 退出码非 0；不能假绿 |

不满足 → 先改脚本，别接 Gate。

---

## 步骤 1 — 在 `gate_check.py` 加 Gx 项

打开 `~/.claude/global-memory/harness/scripts/gate_check.py`，在 `check_prereqs()` 末尾追加：

```python
rc, so, _ = run([sys.executable, str(SCRIPTS / "<your_script>.py"), "<arg1>", "<arg2>"])
gx_ok = rc == 0 and "<stable_marker_in_stdout>" in so
out.append({
    "id": "G<N>",                    # 下一个未用编号
    "name": "<短语，<30 字>",        # 表头展示
    "pass": gx_ok,
    "detail": so.strip()[:200],      # 报告里截断
})
```

**编号约定**：当前 G1-G8 已占，新增从 G9 起。

---

## 步骤 2 — 决定违反时的严重度

| 模式 | gate_check 行为 | 适用 |
|---|---|---|
| **FAIL** | `pass: False` → Verdict BLOCKED → exit 1 | 真硬约束，违反必须修才能 P3 推进 |
| **WARN** | 把 `pass` 改成 `True` 但 `detail` 含 `WARN: <n> issues` | 存量遗留多，一刀切会卡死所有流程；先给修复窗口 |

> WARN 模式样例：硬编码扫描接入时，存量 22 处，FAIL 会卡所有任务 → 改 WARN 给迁移期。

---

## 步骤 3 — 验证

```powershell
# 只读机器输出（不写 GATE-REPORT）
PYTHONIOENCODING=utf-8 python ~/.claude/global-memory/harness/scripts/gate_check.py --json

# 兼容旧报告模式（写 GATE-REPORT）
PYTHONIOENCODING=utf-8 python ~/.claude/global-memory/harness/scripts/gate_check.py

# 看输出 GATE-REPORT-*.md 是否含 G<N> 行
Get-Content (Get-ChildItem "$env:CLAUDE_TASKS_ACTIVE/*/GATE-REPORT-*.md" | Sort-Object -Property LastWriteTime -Desc | Select-Object -First 1)
```

应看到：

```
| G<N> | <name> | ✅/🔴 | <detail> |
```

---

## 步骤 4 — 更新文档

| 文件 | 改什么 |
|---|---|
| `docs/scripts-registry.md` § 2 Gate 调用脚本 | 加一行「`scripts/<your_script>.py` / 用途 / G<N> / REPORT」 |
| `docs/gate-template.md`（本文件）末「当前 Gate 列表」 | 添 G<N> 行 |
| `CONTRIBUTING.md` § 3.5 | 不动（指向本文件即可）|
| `CHANGELOG.md` | append `[FEAT] gate_check G<N>: <名称>` |

---

## 步骤 5 — 移除孤儿标记

如果你接入的脚本之前在 `scripts-registry.md` 标了 ORPHAN，去掉标记 + 把「触发方」改为 `Gate`。

---

## 当前 Gate 列表

| ID | 名称 | 脚本 | 严重度 | 触发条件 |
|---|---|---|---|---|
| G1 | dual storage = 0 | `scan_dual_storage.py` | FAIL | dual_count > 0 |
| G2 | git snapshot tag | `git tag -l pre-context-governance-*` | FAIL | 无快照 tag |
| G3 | retrieve runs | `harness_retrieve.py --dry-run` | FAIL | rc≠0 或无 schema_version |
| G4 | trigger coverage ≥ 90% | `check_trigger_coverage.py --strict` | FAIL | rc≠0 |
| G5 | MEMORY.md ≤ 4000 bytes | `stat MEMORY.md` | FAIL | size > 4000 |
| G6 | plugins controlled | 读 settings.json | FAIL | atlassian/playwright 启用 |
| G7 | test suite green | `test_context_governance.py --all` | FAIL | pytest 失败 |
| G8 | 7d audit data | 占位 | n/a | 暂未实施 |
| G9 | 硬编码路径检查 | `harness/fix_hardcoded_paths.py` | WARN | 任何硬编码（存量 22 处给迁移期，不阻断）|

---

## 反模式（别这么干）

1. **把检查脚本写在 `gate_check.py` 内联**：单一职责丢失，脚本无法单独跑
2. **G<N> 用大于 `60s` 的脚本**：会被默认 timeout 杀掉，假阳性
3. **stdout 不含稳定标志**：导致 `pass` 判定靠 rc，rc==0 但部分失败时假绿
4. **FAIL 但不附 detail**：报告里只有 🔴 没说原因，等于没报
5. **加了 Gate 不改 scripts-registry**：本文档的「触发方」分类是 source-of-truth，孤儿状态不清
