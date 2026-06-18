---
description: 骨折版 codex worker 会遇临时服务故障(error/异常终止)非"必崩"；恢复后正常；官方版 model 可能被 fallback 回骨折版
priority: high
status: active
trigger:
  keywords:
    - tool:orca
    - concept:multi-agent
    - error:worker-crash
  tags:
    - tooling
    - workflow
last_updated: 2026-06-17
---

# 骨折版 codex worker 临时服务故障（非必崩）+ model 参数 fallback

## 现象

用 lizi_orca 创建 `codex/gpt-5.5`（骨折版 / budget）worker。空创建全部 done 正常。给 researcher 派真实任务时连续两次 error / 异常终止，最小探针也崩。**一度误判为"骨折版执行必崩、官方版才行"。**

后续 list_workers 发现真相：
1. 把 model 改传 `gpt-5.5`（官方版）重建，worker 实际仍是 `codex/gpt-5.5`（骨折版）——**官方版 model 参数未生效，被 host fallback 回骨折版**。即"换官方版"从未真正发生。
2. 用户反馈"骨折 gpt 又可以了"；随后骨折版 worker 正常跑完大任务（知识考据）并产出。

## 根因（修正后）

前两次崩溃是**骨折版 gateway 的临时服务故障**，不是"骨折版执行任务必崩"。服务恢复后骨折版 worker 正常执行。第三次"成功"的真正原因是**服务恢复**，不是换了官方版（官方版根本没切成功）。

附带观察：create_worker 的 `model` 参数在当前 host 可能 fallback——传 standard tier（gpt-5.5）实际仍得到 budget tier（codex/gpt-5.5）。`effort` 参数基本按传入生效（developer=high / tester=medium / maintainer=medium 都符）。

## 应对

- worker error / 异常终止时，**先怀疑临时服务故障**：等待或稍后重试，而非归因模型本身、急着重建。
- 不要假设传 `gpt-5.5` 就切到了官方版；以 `list_workers` 实际显示的 model 为准。
- 真要官方版需确认 host 是否支持该 tier（可能受 API key 模式 / 可用性限制）。

## 教训

**归因要等证据闭环**：第一次"换官方版后成功"的相关性被误读为因果（实际是服务恢复 + model 没真切换）。多 worker 崩溃先查服务状态与 `list_workers` 实际配置，别急着下"模型必崩"的结论。
