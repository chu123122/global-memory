---
name: feedback-output-format
description: 输出格式要求，包括代码块、折叠、表格等偏好
type: feedback
created: 2026-04-01
updated: 2026-04-14
source: CLAUDE.md 提取 + 测试 T16 暴露空壳问题后补填
access_count: 0
---

# 输出格式要求

## 代码输出
- 代码块必须标注语言
- 长输出用折叠（<details>）

## 回答风格
- 直接给方案，少说废话（学习 Agent 面试辅导子模式例外）
- 有争议时列出 trade-off
- 不确定时明说"我不确定，建议验证"——不用"应该""大概"掩盖
- 完成任务后只陈述事实，不自评质量（不要说"这个方案很好""希望对你有帮助"）
- 方案设计必须至少给2个方案+对比（工作 Agent 铁律）
- **事实 vs 推断分层**（debug/排查任务必守）：写诊断结论时明确分开"直接观测的事实"（log 直证 / 命令直接输出）和"推断"（基于时间戳接近 / 架构知识 / 经验联想得出的因果）。不要把推断写成"根因是 X"。
  - **Why**：2026-04-23 XDAdaptivePerformance MAGT verify -8 排查中，把 `bind 失败 → verify=-8` 当成单根因写进 HANDOFF TD-15，用户挑战"AppLicenseHubService bind 这个日志在哪里"才发现 PID 1386 vs 984 的因果**没有 stacktrace 直证**。仅凭时间戳接近+架构知识脑补的因果不是事实。
  - **How to apply**：诊断报告分 3 段写 — ① 直接观测的事实（每条标 log/命令出处）② 推断（标"基于 X 推测"）③ 缺口/未验证项（列出可证伪的步骤）。下次"我跳到 Theory B"这种中途换理论也要写进缺口段。
- **当某假设的"修法"不奏效时，先质疑假设本身，不要立刻找别的原因**：
  - **Why**：2026-04-23 同一个 MAGT verify -8 排查走完整版后发现，从一开始用 `xdaperf.keystore` 重签就**没解 -8**，但我没怀疑"xdaperf 是不是错的"，反而连续跳 4 个新理论（class 缺失 / AppsFilter / Not Support MAGT / ROM 不支持）。最终真因是 `torchlight.keystore` 才对，xdaperf 从来就是错的方向。如果当时第一次 re-sign 后仍 -8 就回头列全部 keystore 试，能省 4 小时。
  - **How to apply**：当"按假设 A 改了 X，问题仍在"时，先做的两件事 ——（1）把"假设 A 是不是错的"明确列为新分支，跟"假设 B/C/D"平等对待；（2）如果 A 是个有限集（如"用哪个 keystore"），**直接列出全集逐个试**，不要预先排除。**不要立刻发明新假设跳过去** —— 那只是在已经塌的地基上盖新楼。
- **机制层推断必须列候选集合，不锁定单一假设**（"事实 vs 推断分层"的子规则 #3）：
  - **Why**：2026-04-24 排查 MIUI 高通设备 QAPE 全 timeout，看到"3 台跨 SoC 跨 Android 跨 MIUI 一致失败"就直接脑补"MIUI 把 vendor service 从 vintf manifest 移除"。用户挑战"如何判断的？查没？" 才意识到这是脑补具体机制，没任何证据。后来跑实测发现真因是 **SELinux 拒 untrusted_app find vendor service**（avc denied 直证），跟 vintf manifest 完全无关。**列候选集合时 manifest 移除是 6 候选之一，单独锁定它就错了**
  - **How to apply**：现象推断（"X 系列性问题"）跟机制推断（"因为 X 在 manifest 里没注册"）是两个层次。
    - 现象推断从跨设备一致性下结论 = 强推断（高可信）
    - 机制推断必须列候选集合 + 给可证伪验证方法 + 不锁定单一假设
    - 套用模板：
      ```
      ✅ 事实层（log/cmd 直证）：3 台 X
      🟡 强推断（现象层）：跨多维度一致 → Y 系列性问题
      ❌ 弱推断（机制层）：候选 ABCDEF — 待坐实，每条配验证命令
      ```
  - **常见的脑补机制（要警惕，遇到先列候选）**：
    - 系统层：vintf manifest / SELinux policy / Binder permission / AppsFilter / cgroup / capability
    - 链路层：dlopen/dlsym 失败 / 参数命名错配 / 版本兼容 / NDK API level
    - 数据层：ABI 错配 / endian / alignment

## 文档格式
- 标题层级不跳级
- 表格对齐
- 长文档有目录

## 记忆写入格式
- 写入后必须附上 `[MEMORY_WRITTEN]` 格式标注（见 Agent 配置）

---
## 更新日志
- 2026-04-01: 初始创建
- 2026-04-14: 从 CLAUDE.md 和测试结果提取已知偏好，激活文件
- 2026-04-23: 加"事实 vs 推断分层"条款（XDAdaptivePerformance MAGT verify -8 排查中把推断当事实写进 HANDOFF 被用户纠正）
- 2026-04-23: 加"修法不奏效时先质疑假设本身"条款（同一次排查里，xdaperf re-sign 仍 -8 时该回头试 torchlight.keystore，但我连续跳 4 个新理论结果绕了 4 小时，真因就是 keystore 选错）
- 2026-04-24: 加"机制层推断必须列候选集合"子规则（XDAdaptivePerformance MIUI QAPE 排查中脑补"vintf manifest 移除"被用户挑战，验证后真因是 SELinux + 描述符错配双层）
