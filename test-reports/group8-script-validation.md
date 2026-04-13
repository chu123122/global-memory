# 第八组测试报告：脚本验证（T34-T36）

> 执行时间：2026-04-14
> 执行环境：Claude Code CLI / Sonnet 4.6 / Windows 新机器 / Git Bash

---

## 前置说明：路径错误

测试runner中三个命令均使用路径 `~/.claude/skills/_bootstrap/scripts/`，
但该路径**不存在**（`skills/` 下只有5个Skill软链接，无 `_bootstrap/` 子目录）。

实际正确路径：`~/.claude/skills-repo/_bootstrap/scripts/`

以下测试均按"先尝试测试runner给出的路径（失败）→ 再用实际路径执行"的方式记录。

---

## T34

**输入：** `bash ~/.claude/skills/_bootstrap/scripts/skill_regression_test.sh`

**你的实际响应：**

**步骤1：尝试测试runner路径**
```
bash: /c/Users/chu/.claude/skills/_bootstrap/scripts/skill_regression_test.sh: 没有那个文件或目录
```
→ 路径不存在，立即失败。

**步骤2：用实际路径执行（无参数）**
```
$ bash ~/.claude/skills-repo/_bootstrap/scripts/skill_regression_test.sh
用法: bash skill_regression_test.sh <skill_name>
exit: 1
```
→ 脚本正确检测到缺少参数并退出。

**步骤3：用实际路径执行（带参数 cpp-tutor）**
```
$ bash ~/.claude/skills-repo/_bootstrap/scripts/skill_regression_test.sh cpp-tutor
=== 回归测试: cpp-tutor ===
❌ SKILL.md 不存在
exit: 1
```
→ **FAIL**，但这是一个脚本Bug，不是 cpp-tutor 本身有问题。

**根因分析：**
脚本内使用 `find "$SKILL_DIR" -name "SKILL.md"` 来定位SKILL.md，
但 `~/.claude/skills/cpp-tutor` 本身是一个**目录级软链接**（symlink指向目录）。
`find` 默认不追踪软链接（不加 `-L` flag），导致找不到文件。

验证：
```bash
find  ~/.claude/skills/cpp-tutor -name "SKILL.md"  # → 空（不追踪symlink）
find -L ~/.claude/skills/cpp-tutor -name "SKILL.md" # → 找到 ✅
ls ~/.claude/skills/cpp-tutor/SKILL.md              # → 存在 ✅
```

**访问的文件：** `~/.claude/skills-repo/_bootstrap/scripts/skill_regression_test.sh`
**触发的Skill：** 无
**异常/报错：** 测试runner路径不存在；脚本本身有 `find` 不追踪软链接的Bug
**发现的问题：**
1. **测试runner中的路径写错了**：`skills/_bootstrap/` 不存在，应为 `skills-repo/_bootstrap/`。这是test-runner.md本身的一个测试用例路径错误。
2. **skill_regression_test.sh的`find`缺`-L`flag**：当Skills以目录级软链接部署时，脚本永远找不到SKILL.md。修复：将 `find "$SKILL_DIR"` 改为 `find -L "$SKILL_DIR"`。这是一个P1级Bug（所有现有Skills的回归测试都会失败）。

---

## T35

**输入：** `bash ~/.claude/skills/_bootstrap/scripts/memory_cleanup.sh`

**你的实际响应：**

**步骤1：尝试测试runner路径** → 不存在，失败（同T34）。

**步骤2：用实际路径执行**
```
$ bash ~/.claude/skills-repo/_bootstrap/scripts/memory_cleanup.sh
=== 记忆文件清理检查 ===
目录: /c/Users/chu/.claude/global-memory
阈值: 30 天未更新

/c/Users/chu/...memory_cleanup.sh: line 24: stat -f %m ...: syntax error in expression
（大量 stat 错误输出，每个文件都报错）

✅ 所有记忆文件活跃，无需清理
exit: 0
```

**表面通过，实际是静默失败（假阳性）。**

**根因分析：**
```bash
# 脚本中的 stat 调用：
MOD_TIME=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null)
```
- `stat -f %m`：macOS/BSD 语法，Linux/Windows 无效
- `stat -c %Y`：Linux GNU 语法，但在 Windows Git Bash 下 `stat` 输出的是整个 `stat` 的完整文本而非纯时间戳

实际效果：`MOD_TIME` 被赋值为多行 stat 输出文本，不是时间戳。
后续 `DAYS_AGO=$(( (NOW - MOD_TIME) / 86400 ))` 的算术运算失败（syntax error）。
算术错误使 `$DAYS_AGO` 为空，`[ $DAYS_AGO -gt $THRESHOLD_DAYS ]` 条件从不成立。
→ `CANDIDATES` 始终为 0，脚本报告"无需清理"并退出 0——**跳过了所有检查**。

**访问的文件：** `~/.claude/skills-repo/_bootstrap/scripts/memory_cleanup.sh`
**触发的Skill：** 无
**异常/报错：** `stat` 语法错误（Windows Git Bash 不兼容），`DAYS_AGO` 算术运算失败
**发现的问题：**
1. **memory_cleanup.sh 在 Windows Git Bash 下完全失效**：`stat` 的 `-f` (macOS) / `-c` (Linux) 两路 fallback 均无法在 Git Bash 上产生纯时间戳输出。脚本看似正常退出，但从未实际检查任何文件。这是一个**静默失败**，比报错更危险：用户以为清理检查通过了，实际上什么都没检查。
2. **跨平台兼容问题**：系统在 macOS（原始设计环境）和 Windows（当前环境）上行为不同，且失败是静默的。修复建议：用 `python3 -c "import os; print(int(os.path.getmtime('$f')))"` 替代 `stat` 命令，Python3 跨平台一致。

---

## T36

**输入：** `bash ~/.claude/skills/_bootstrap/scripts/sync_memory.sh`

**你的实际响应：**

**步骤1：尝试测试runner路径** → 不存在，失败（同T34）。

**步骤2：用实际路径执行**
```
$ bash ~/.claude/skills-repo/_bootstrap/scripts/sync_memory.sh
=== 记忆同步 ===
✅ 无变更，已是最新
exit: 0
```

**完全正常。** git status 干净（之前已手动提交所有测试报告），无需同步。

**访问的文件：** `~/.claude/skills-repo/_bootstrap/scripts/sync_memory.sh`
**触发的Skill：** 无
**异常/报错：** 无（从实际路径执行正常）
**发现的问题：**
1. **sync_memory.sh 使用 `git add -A` 是潜在风险**：脚本会把所有未跟踪文件一起提交，包括可能的临时文件、密钥文件等。在 global-memory 这个特定仓库问题不大（内容都是md文件），但如果这个模式被复制到其他仓库就危险。建议改为 `git add *.md` 或更精确的路径。
2. 功能本身正常，auto-sync daemon 已经覆盖了这个职责，T36 属于重复功能。

---

## 第八组总结

| 测试 | 测试runner路径 | 实际路径执行结果 | 关键发现 |
|------|--------------|----------------|---------|
| T34 skill_regression | ❌ 路径不存在 | ❌ 脚本Bug（find不追踪symlink）| 所有现有Skills的回归测试均失败 |
| T35 memory_cleanup | ❌ 路径不存在 | ⚠️ 假阳性（stat跨平台失效）| Windows Git Bash静默失败 |
| T36 sync_memory | ❌ 路径不存在 | ✅ 正常（无变更，已同步）| 功能OK，`git add -A`有风险 |

**第八组新发现的问题：**

1. **test-runner.md路径错误**（文档缺陷）：三个测试均使用了 `~/.claude/skills/_bootstrap/` 而非正确的 `~/.claude/skills-repo/_bootstrap/`。test-runner.md需要修正路径（或者应该建立 `skills/_bootstrap` → `skills-repo/_bootstrap` 的软链接）。

2. **skill_regression_test.sh的 `find` 缺 `-L` flag**（P1新增）：Skills以目录级symlink部署时，脚本永远报"SKILL.md不存在"。当前所有5个已部署Skill的回归测试都会失败。修复：`find "$SKILL_DIR"` → `find -L "$SKILL_DIR"`。

3. **memory_cleanup.sh在Windows Git Bash下静默失效**（P1新增）：`stat` 跨平台不兼容，脚本从不检查任何文件但返回 exit 0。静默假阳性比报错更危险。修复：用 Python3 替代 `stat`。

4. **脚本跨平台兼容性整体未验证**：整个 `_bootstrap/scripts/` 目录是在 macOS/Linux 环境设计的，从未在 Windows Git Bash 下系统性测试。T35 已证实有兼容问题，其他脚本（memory_cleanup.sh / format_check.sh / check_lua_syntax.sh）也可能有类似问题。

---
## 更新日志
- 2026-04-14: 第八组测试执行完成，发现skill_regression_test symlink Bug + memory_cleanup.sh跨平台失效
