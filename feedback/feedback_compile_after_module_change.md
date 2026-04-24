---
name: 每模块改完拉一次编译
description: 工作偏好 — UE / C++ 项目每修改完一个模块后立即拉一次编译验证, 不要积累多模块改动一起编
type: feedback
created: 2026-04-23
updated: 2026-04-24
source: XDAdaptivePerformance 阶段 2a 测试基建反馈
access_count: 0
---

每次修改完一个模块（独立 Build.cs 单元 / 独立 .uplugin Module 节点）后立即拉一次编译看结果, 不要积累多模块改动一起编。

**Why:** 多模块改动一起编出错时定位难; 单模块改完单独编译能立即把问题归到那个模块, 加快迭代。用户 2026-04-23 在 XDAdaptivePerformance 阶段 2a 测试基建第 1 步(新建 XDAdaptivePerformanceTests 模块)后明确要求"每次修改完一个模块后就请拉一次编译看看情况"。

**How to apply:**
- UE 工程任何独立改动单元(新增模块 / 改 Build.cs / 改 .uplugin / 加 Mock / 加 Spec 文件 / 改头文件 API 边界)完成后, 立即用 `Build.bat <Target>Editor Win64 Development -Project="..."` 拉一次
- 编译失败先修再继续下一个改动, 不积压
- 增量编译通常 1-5 分钟, 不会显著拖慢节奏
- 用 `run_in_background: true` 跑, 让用户继续干别的事, 编译完系统会通知 — **不要主动 poll/sleep**
- 编译过 → 报告结果 + 进入下一步; 编译失败 → 看 tail 日志找 error, 修, 再编一次
- 不适用场景: 纯文档改动 / Skill 配置改动 / 不涉及编译的 .ini / 资源 .uasset 改动

**Quick check:**
- 改了 `*.Build.cs` / `.uplugin` / Module 目录结构 → 必编
- 改了公共头文件或跨模块 include → 必编
- 只改 README / DESIGN / HANDOFF → 不编
- 编译命令失败时优先看第一条 C++/linker error, 不被后续级联错误带跑
