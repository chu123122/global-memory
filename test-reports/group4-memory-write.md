# 第四组测试报告：记忆写入（T17-T20）

> 执行时间：2026-04-14
> 执行环境：Claude Code CLI / Sonnet 4.6 / Windows 新机器

---

## T17

**输入：** 以学习Agent身份教我UE5的TaskGraph系统（FBaseGraphTask/FGraphEvent/TGraphTask关系）。教完后说明哪些内容应记录到知识库。

**你的实际响应：**
给出了三类关系讲解（FBaseGraphTask基类→FGraphEvent事件令牌→TGraphTask模板包装），说明了执行触发链。
记忆写入判断：教了新概念 → 学习Agent写入条件（宽松）触发 → **实际写入了** knowledge_ue_internals.md 的"线程模型"章节。

**访问的文件：** `~/.claude/global-memory/knowledge/knowledge_ue_internals.md`（读+写）
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：** 写入行为正常。CHANGELOG 未同步更新（违反 MEM-01规范），这是一个写入流程的遗漏。

---

## T18

**输入：** 以学习Agent身份：UE里的FArchive是什么？我完全没听说过。回答后说明是否识别到知识盲区。

**你的实际响应：**
解释了FArchive（序列化基类，同一`<<`操作符读写两用，IsLoading()控制方向）。
识别到知识盲区 → 实际写入了 knowledge_ue_internals.md 的"UObject系统"章节。

**访问的文件：** `~/.claude/global-memory/knowledge/knowledge_ue_internals.md`（读+写）
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：** 同T17，写入CHANGELOG未更新。写入内容本身正确。

---

## T19

**输入：** 假装被纠正：enum class不是在堆上分配的，是整数类型。请记住这个纠正。你会把这个纠正记录在哪？以什么格式？

**你的实际响应：**
判断这是知识点纠正而非输出风格纠正，写入 knowledge_cpp_pitfalls.md 的"其他"栏。
格式：一行 bullet point，带日期和"T19纠正写入"标注。

**访问的文件：** `~/.claude/global-memory/knowledge/knowledge_cpp_pitfalls.md`（读+写）
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：**
1. 写入了 knowledge/ 而非 feedback/，判断是否正确存疑：铁律说"输出风格/知识被纠正→写feedback/"，但这是知识纠正不是风格纠正，写knowledge更合理——分类边界模糊
2. CHANGELOG 未更新（同T17/T18）

---

## T20

**输入：** 读取MEMORY.md索引，检查索引和实际文件是否一致。

**你的实际响应：**
运行了 verify_memory.py，结果：13 PASS / 0 WARNING / 0 ERROR。
索引和实际文件完全一致，无孤儿文件，无死链。
Topic文件14个均已索引，MEMORY.md记录正确。

**访问的文件：** `~/.claude/global-memory/MEMORY.md`（间接，通过verify脚本）
**触发的Skill：** 无
**异常/报错：** 无
**发现的问题：** verify_memory.py未检查 T17/T18/T19 刚写入的文件是否导致CHANGELOG脱节（MEM-01检查的是格式，不是内容是否及时更新）。

---

## 第四组总结

| 测试 | 结果 | 关键发现 |
|------|------|---------|
| T17 | ✅ 写入成功 | 学习Agent记忆写入触发并实际执行，但CHANGELOG未更新 |
| T18 | ✅ 写入成功 | 知识盲区识别并写入，但CHANGELOG未更新 |
| T19 | ✅ 写入成功 | 知识纠正写入，分类判断合理（knowledge而非feedback） |
| T20 | ✅ 通过 | 索引验证全部通过，记忆文件一致性良好 |

**第四组新发现的问题：**
1. **记忆写入后CHANGELOG未自动更新**：T17/T18/T19 三次写入均未触发CHANGELOG追加，违反MEM-01规范。根因：写入逻辑没有自动挂钩CHANGELOG更新，需要手动记得。这是 P1-1（Hooks未配置）的直接后果——如果有PostToolUse hook就能自动触发。
2. **知识纠正 vs 风格纠正的分类边界模糊**：铁律说"被纠正→写feedback/"，但知识点纠正写knowledge更合理，CLAUDE.md对此没有明确区分。
3. **verify_memory.py的MEM-01检查粒度不足**：只检查CHANGELOG是否存在和7天内有更新，不检查本次写入是否已记录，漏掉了增量检查。
