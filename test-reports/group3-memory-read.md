# 第三组测试报告：记忆读取（T12-T16）

> 执行时间：2026-04-14
> 执行环境：Claude Code CLI / Sonnet 4.6 / Windows 新机器

---

## T12

**输入：** 我在之前的面试中，哪些知识点答得不好？具体是哪几场面试的什么问题？

**你的实际响应：**
读取了 interview_weakness_tracker.md，回答：
- 心动引擎二面：mutex/atomic/condition_variable不熟（❌扣分严重）
- 米哈游线下 + 字节三面：系统设计表达崩（知识够但组织不清）
- 多次面试：DP/图算法现场卡住

**访问的文件：** `~/.claude/global-memory/interview/interview_weakness_tracker.md`
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：** 文件内容是"初始创建"时迁移的数据，access_count=0，显示从未被AI自动读取。验证了T05发现：AI没有在"分析用户情况"时主动读取interview文件的习惯。

---

## T13

**输入：** 我之前面试中被问过哪些C++多线程相关的题目？

**你的实际响应：**
读取了 interview_question_bank.md，找到3道多线程题：
1. mutex/atomic/condition_variable（心动二面，❌不熟）
2. 怎么通知主线程（多次面试，❌反复答不出）
3. std::atomic的memory_order（面试追问，❌没接触过）

**访问的文件：** `~/.claude/global-memory/interview/interview_question_bank.md`
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：** 数据存在且可读取，内容真实（非预填）。但 access_count 仍为 0，说明正常对话中 AI 从未主动检索这个文件。

---

## T14

**输入：** 我目前对UE引擎底层了解到什么程度？哪些已掌握，哪些还没有？

**你的实际响应：**
读取了 knowledge_ue_internals.md：
- 已掌握（实习经验）：Pak加载/模块依赖/资源管线/Git工具链/三线程模型（知架构）
- 待学习：TaskGraph调度原理/UObject反射GC序列化/源码阅读进度

**访问的文件：** `~/.claude/global-memory/knowledge/knowledge_ue_internals.md`
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：** knowledge_ue_internals.md 的"源码阅读记录"和"已掌握"栏大量为空（"待学习"/"随学习进度更新"），说明知识库在UE这块积累严重不足，不能作为可靠的知识来源。

---

## T15

**输入：** UE的FTimerManager内部是怎么实现的？请优先使用知识库文档回答。

**你的实际响应：**
主动搜索知识库，在 ue-source-deep-dive.md 第279行找到了FTimerManager完整章节：
- 数据结构：TSparseArray+最小堆+PendingSet+PausedSet
- 流程：SetTimer→PendingSet，Tick→堆遍历→到期调回调→循环/移除
- 源码位置：Runtime/Engine/Private/TimerManager.cpp

**访问的文件：** `~/.claude/global-memory/knowledge/docs/ue-source-deep-dive.md`（第279-307行）
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：** 无，知识库检索成功，内容可用。这是第三组唯一一个"知识库真正发挥作用"的测试。

---

## T16

**输入：** 你知道我之前纠正过你的哪些代码风格问题吗？

**你的实际响应：**
读取了 feedback_code_style.md 和 feedback_output_format.md，发现：
- 两个文件都是"初始预填的通用规则"，没有真实纠正记录
- C++/Lua/C# 风格栏内容均为"随使用积累"（空）
- 回答：没有任何你纠正过AI的具体记录，文件是空壳

**访问的文件：** `~/.claude/global-memory/feedback/feedback_code_style.md`, `feedback_output_format.md`
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：** **feedback系统完全没有启用**。两个文件只有初始通用规则，从未有真实纠正记录写入。说明学习Agent/工作Agent的记忆写入条件"输出风格被纠正→写入feedback/"从未被触发过（或触发了但没写入）。这是记忆系统的一个严重空洞。

---

## 第三组总结

| 测试 | 结果 | 关键发现 |
|------|------|---------|
| T12 | ✅ 通过 | 数据可读，但AI平时不主动读 |
| T13 | ✅ 通过 | 数据可读，但AI平时不主动读 |
| T14 | ⚠️ 部分通过 | 文件可读，但UE知识积累严重不足 |
| T15 | ✅ 通过 | 知识库深度文档发挥作用，FTimerManager有完整记录 |
| T16 | ❌ 暴露问题 | feedback系统完全是空壳，没有任何真实纠正记录 |

**第三组新发现的问题：**
1. **知识库文件平时不被主动读取**：access_count全部为0，AI在分析/回答时倾向于用训练数据而非读文件
2. **feedback系统空洞**：两个feedback文件无真实数据，记忆写入的"风格纠正"触发器从未生效
3. **knowledge文件内容参差不齐**：深度文档（docs/）内容扎实，Topic文件大量空白 —— 两级内容密度差距过大
4. **access_count字段从未更新**：设计了但没有任何机制更新它，是废字段
