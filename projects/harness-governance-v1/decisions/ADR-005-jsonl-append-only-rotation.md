# ADR-005 · JSONL append-only + 按大小/行数轮转

- **状态**:Accepted
- **创建**:2026-04-24
- **关联 Phase**:4-A(任务结果账本写入端)、Phase 1-C(control-panel-v1 REVIEW 风险 1-2 修复)
- **关联横切原则**:DESIGN §1.4 第 5 条

## 背景

ADR-001 选定 JSONL 作为载体后,留下两个未决问题:

1. **历史是否允许就地修改?**(改某条历史记录的 lesson 字段?)
2. **文件膨胀如何收敛?**(`control_panel_events.jsonl` 长跑后会 GB 级)

control-panel-v1 的 REVIEW 已经标 🟡 风险:"JSONL 日志无轮转"和"2 秒轮询是否维护 last_offset 未声明"。本 ADR 把这两条统一定型。

## 候选方案

### A. Append-only + 大小阈值轮转(本 ADR 选定)

- 写入只追加,从不就地改;
- 文件 ≥ 5 MB **或** 行数 ≥ 10000 时自动滚动到 `<file>.1`,旧的 `.1` → `.2`,保留最近 3 份;
- reader 维护 last_offset(per file),只读增量。

**优**:历史不可篡改,审计性强;轮转触发明确;reader 性能稳定。
**劣**:跨文件查询(读 .0 + .1 + .2)需要 reader 支持;改写历史需要"新写一条带 ref 字段"的间接方式。

### B. 就地可改 + 时间窗口归档

写入端可 update 已有行(by ts);超过 30 天的归档到 `<file>.archive.jsonl`。
**优**:更正容易;归档机制天然。
**劣**:破坏审计性;并发更新需要锁;reader 无法 stream(任何行都可能被改)。

### C. 不轮转,无限增长

依赖 reader 的 last_offset 足够快。
**优**:零运维。
**劣**:磁盘膨胀;迁移/备份成本累积;查询性能无上限。

## 选定

**A(append-only + 大小/行数阈值轮转)**。

理由:
- 审计可信度优先(任务结果账本作为度量底座,数据可信是命脉)
- 跟 git commit 设计哲学一致:不可改历史,只可叠加更正
- 与 control-panel-v1 REVIEW 的风险修复方向一致
- 5 MB / 10000 行的阈值参考 `control_panel_events.jsonl` 实测——该文件日均 ~50 条事件,5 MB 大约 3-4 个月一次轮转

**阈值反思**(REVIEW-2026-04-24-1601):账本写入是"任务完成时一次",日均 1-2 条,5 MB 实际**几年才轮转一次**。轮转代码在账本场景近乎死代码,但**仍按本 ADR 实现**(理由:`rotate_log` 是通用工具,未来会被其他 jsonl 复用,如 `tool_audit.jsonl` 的 PostToolUse hook 触发频率高)。账本本身的 4A-V4 验收用 mock 文件触发即可。

## 后果

**优**:
- 历史不可篡改,Phase 4-B 趋势分析可信
- reader 用 last_offset 增量读,GUI 不卡顿
- 旧文件 `.1` `.2` 可直接 gzip 归档,长期占用可控

**劣**:
- 更正历史只能"再 append 一条带 corrects: <ts>"——schema 需预留 corrects 字段
- 同时读 .0/.1/.2 需要 reader 框架封装(放 Phase 4-B,Phase 4-A 不做)

**风险**:
- 多 writer 并发 append 顺序错乱 → 不依赖 POSIX 隐式语义,**显式上锁**:Windows 用 `msvcrt.locking()`,POSIX 用 `fcntl.flock()`,二者都是 stdlib(无 portalocker 依赖)。统一封装在 `_lib._file_lock()`,见 DESIGN §3.0
- 轮转时 reader 正在读 → 用 inode 检测 + reset offset 兜底,Phase 4-B 实现

**REVIEW-2026-04-24-1601 修订**:之前本节说"用 `portalocker` 或自旋 + `os.O_APPEND`",但实际上:
- `portalocker` 不在任何 requirements 文件里(grep 实测无匹配)
- DESIGN §3.5 之前说"写一个 50 行的 fcntl-fallback"也是错的——`fcntl` 是 POSIX-only 模块,Windows 上 `import fcntl` 直接抛 `ModuleNotFoundError`,不能作 Windows 兜底
- 正确做法已修订为"按 `is_windows()` 分支选 `msvcrt.locking()` 或 `fcntl.flock()`",二者都是 stdlib

## 关联

- 落实在:Phase 4-A(写入端的轮转检查)、Phase 4-B(reader 的多文件聚合)
- 修复 control-panel-v1 REVIEW 的中风险:"JSONL 轮转无阈值" + "last_offset 策略未声明"
- 文件锁实现细节:留给 Phase 4-A 详细设计
