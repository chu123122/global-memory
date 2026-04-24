# ADR-008 · 是否引入 portalocker 第三方依赖

- **状态**:Proposed(未触发,占位以解 verify_doc_drift D7 悬空引用)
- **创建**:2026-04-24
- **触发条件**:stdlib(`msvcrt.locking` / `fcntl.flock`)在某 Windows 边缘场景失效(如网络挂载 / WSL 跨边界 / 高并发)
- **关联**:由 ADR-005 §后果·风险 引用 + DESIGN §3.8 风险表 引用
- **关联横切原则**:DESIGN §1.4 第 5 条(append-only)

## 背景

当前 Phase 4-A 的文件锁实现走 stdlib 路径(`_lib._file_lock`),无第三方依赖。但 ADR-005 与 DESIGN §3.8 都指出存在边缘场景:

- 跨网络挂载点(SMB / NFS)的文件锁语义不一致
- WSL 跨边界(WSL2 内访问 Windows mount)
- 高并发(账本场景实际不会触发,但通用工具会被复用到 audit_logger 这种高频写场景)

如果将来这些场景之一真出问题,选项是 vendoring `portalocker`(成熟封装)。

## 候选方案(预占位,未真正评估)

### A. 维持 stdlib 路径(现状)
**优**:零依赖。**劣**:边缘场景需自行处理。

### B. 引入 portalocker
**优**:成熟跨平台封装,网络挂载兼容性更好。**劣**:增加 pip 依赖,需进 requirements。

### C. 自己写更厚的封装(类似 portalocker mini-fork)
**优**:零依赖 + 处理边缘。**劣**:维护成本高。

## 选定

**未选定**(Proposed 状态)。当前用方案 A;只有当 4A-V3 验收 + 实战 ≥ 6 个月内出现锁失效 case 时,触发本 ADR 升级到 Accepted 并选 B。

## 后果

(待触发后填充)

## 关联

- 引用方:ADR-005 §后果·风险(锁失效 fallback);DESIGN §3.5(并发与原子性);DESIGN §3.8(风险表)
- 升级到 Accepted 时同步:ADR-005 文件锁实现段、`_lib._file_lock` 实现切换、`requirements.txt`(若引入)
