---
description: feedback_no_speculative_semantics_in_comments
priority: medium
status: active
trigger:
  keywords:
    - concept:style
    - concept:comment
  tags:
    - doc
  stages:
    - implementation
last_updated: 2026-05-20
---

---
name: 不实证就不写"语义"注释
description: 工作偏好 — 写出现 "语义/含义/意思是/对应" 等字眼的注释、文档前必须 grep/Read 一手定义实证, 凭印象写就是误导
type: feedback
created: 2026-04-28
updated: 2026-04-28
source: XDAdaptivePerformance plugin MTK 错误码注释审查（design-reviewer 实测发现错误）
access_count: 0
---

写代码注释 / 文档 / 日志文案时，**任何描述错误码语义、API 含义、字段意思的句子都属于"语义声明"**。这种声明只有两种合法来源：

1. **一手实证** — grep/Read 到 SDK header / 协议定义 / 代码常量
2. **明示推断** — 在注释里加 `⚠️ 推断未验证` 或 `待 X 答` 标记

**禁止**：凭印象写 "X = service unavailable" / "Y 表示 license 失败" 这种"我以为"注释。

**Why:** 注释是诊断时的第一信任源。错误注释 + 后续诊断 = 错上加错链。XDAdaptivePerformance plugin 实战教训（2026-04-27）：

- 我在 `MediaTekPerfMetricsMonitor.cpp:185` 的 `InitGameConfig Result` log 后凭印象注释 "-6=service unavailable on device"
- design-reviewer 翻 `MAGTModuleDef_V1.h:100-121` 实证 → **真实是 -6=UNINITIALIZED, -7=SERVICE_NA**
- 后果：后续任何排错的人看到 -6 都会以为"MAGT 系统服务不可用"（应该排查 ROM/OEM），实际真因是 plugin 自己 init 没走完（应该排查 plugin 调用顺序）。**根因方向反了**

跟之前批 v3 文档"想当然"是同一类错 — 出现 "我记得" / "应该是" / "好像" 的瞬间就是危险信号。

**How to apply:**

1. 写注释前自检：句子里有没有 `=` `表示` `对应` `语义` `意思是` `含义` 这些"语义声明"词
   - 没有 → 直接写
   - 有 → 进入步骤 2
2. 必须出示实证：
   - 错误码 / enum 值：grep 该 enum 定义文件，或 Read SDK header
   - API 行为：grep 实现 / 找官方文档
   - 字段单位：找 doc / 看赋值处的注释
3. 找不到实证：
   - 注释加 `⚠️ 推断` / `待 X 答`，不要直接写
   - 或者 spawn explore agent 帮忙找
4. 高风险场景（必查）：
   - vendor SDK 错误码（MAGT / QAPE / NDK 系列）
   - 第三方 API 单位 / scale（BatteryManager.EXTRA_VOLTAGE 实测在 OPPO 上 unit 异常）
   - 跨平台行为（iOS/macOS/Android NDK 行为差异）
   - 线程模型 / lifecycle 依赖

**反例（必须避免）**：

```cpp
// ❌ 凭印象
result = init();  // 0=ok, -1=fail, -2=invalid（脑补的）

// ❌ "我以为"
queryServiceVersion();  // 返回 SDK 服务版本号
                        // ↑ 没看 SDK 文档，可能返设备版本/license版本/别的

// ✅ 实证
result = init();  // 详见 MAGTModuleDef_V1.h:100-121 EResult enum
                  // 0=OK, -1=GENERAL_ERROR, -6=UNINITIALIZED, -7=SERVICE_NA, -8=LICENSE_VERIFY_ERROR
```

**写文档同理**：HANDOFF / DESIGN / REVIEW / 日志文案里"为什么 / 因为 / 所以 / = / 语义" 这些词触发同样自检。

**Self-check tip**：写完注释/日志后用 explore agent 抽查："grep 我刚写的 X SDK 定义" — 如果 agent 找到的跟我写的不一样，立即修。

不为难自己，但不糊弄诊断。
