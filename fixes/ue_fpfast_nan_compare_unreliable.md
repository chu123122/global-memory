---
description: UE 默认 /fp:fast 下 NaN==X 比较不可靠会误判，需用 FMath::IsFinite 位检查短路
priority: medium
status: active
trigger:
  keywords:
    - error:nan-compare
    - concept:floating-point
    - tool:UE
  tags:
    - debug
    - build
  stages:
    - debug
last_updated: 2026-06-01
---

# UE /fp:fast 下 NaN 浮点比较不可靠，丢值或误命中

## 现象

XDAdaptivePerformance 热温度样本流程：provider 应把 NaN 原样透传给流程层过滤（DIFF-3 口径统一契约）。实测 NaN 在 provider 内被丢，样本数组从期望 `{35, NaN, 99}` 变成 `{35, 99}`（诊断输出 `Samples.Num=2`）。修了 provider 后，测试 helper `SamplesContain(samples, -1.0f)` 又对纯 `{35, NaN, 99}`（无 -1.0）误报「含 -1」，因为 NaN 元素 `NaN == -1.0f` 返回真。

## 根因

UE 编译默认开 `/fp:fast`（FastFloatingPoint）。该模式下编译器假设运算数永不为 NaN/Inf，`NaN == X` / `NaN != X` / `NaN > X` 等有序比较可被优化成不符合 IEEE 的结果（实测 `NaN == -1.0f` 误判为真）。所以任何用 `==`/`!=`/`<`/`>` 直接判 NaN 或拿 NaN 跟哨兵比，都不可靠。

`FMath::IsFinite(x)` 例外可靠：它是位检查 `((*(uint32*)&x) & 0x7F800000) != 0x7F800000`，不走浮点比较单元，对 `/fp:fast` 免疫。NaN 指数位全 1 → 恒返 false。

## 修复

凡是「区分 NaN vs 某具体浮点值」的判断，用 `FMath::IsFinite` 先短路：

```cpp
// 丢哨兵：只丢有限的 -1.0，NaN 短路保留透传
if (FMath::IsFinite(Temp) && Temp == NO_COUNTER_VALUE_FLOAT) { continue; }

// 数组查找：NaN 元素不冒充被查的有限值
for (float S : Samples) { if (FMath::IsFinite(S) && S == Value) return true; }
```

反例（被咬）：`if (Temp == NO_COUNTER_VALUE_FLOAT)`、`if (Sample == Value)` 单独用。

注意 `x != sentinel && IsFinite(x)`（取 max 那种）天然安全：NaN 经 `IsFinite` 已被排除，无需额外改。

## 验证

UE 4.26 源码引擎 headless 自动化：注入 `{-1, 35, NaN, 99}`，断言 provider 喂 `{35, NaN, 99}`（NaN 位 0x7FC00000 finite=0）、流程层过滤 NaN 后 max 99。改前 `Samples.Num=2`（NaN 丢）红，改后 `Num=3` 绿。命令：`UE4Editor-Cmd.exe <uproject> -ExecCmds="Automation RunTests XDAdaptivePerformance.Thermal.AndroidSamples; Quit" -nullrhi -ReportExportPath=<dir>`，看 `index.json` failed=0。
