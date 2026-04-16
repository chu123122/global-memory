# 个人 AI 系统审查报告（2026-04-16）

> 审查对象：`global-memory` + `skills-repo`
> 审查范围：记忆系统、Prompt / Agent 体系、脚本检查层、Harness 运行边界
> 结论先行：**当前最大问题不是“没有 harness”，而是 harness 仍以“静态规则 + 事后脚本审计”为主，缺少“运行时硬约束 + 统一规则来源 + 可观测性闭环”。**

---

## 1. 一句话结论

你的系统已经具备较强的**基础设施能力**：

- 双 Agent（学习 / 工作）行为边界清晰
- 四层记忆 + 三层金字塔有明确设计
- `verify_memory.py` / `verify_conventions.py` / `verify_all.py` / `verify_prompt_system.py` 组成了一个“结构审计层”
- `guardian-agent` 和 `task_complete.py` 已经在尝试把“检查”串成流程

但当前最关键的问题是：

> **规则层过厚、规则来源过多、规则与检查脚本的映射不清，且缺少真正的运行时 hook 层。**

这会导致三类问题同时出现：

1. **AI 忽略规则**：因为规则分散在 `CLAUDE.md`、Agent 文件、memory-rules、conventions、README、SYSTEM_STATUS 里，且存在冲突与过期信息。
2. **脚本“看起来很强”，但部分检查并没有真的验证到宣称的内容。**
3. **系统是“离线审计强，运行时拦截弱”** —— 更像 lint / health-check 体系，而不是完整 harness。

---

## 2. 目前系统的真实状态

### 2.1 已经做得很好的地方

#### A. 架构意识已经成熟
你不是在“随便写点 prompt”，而是在做一个完整的个人 AI 工作系统：

- `global-memory` 明确设计了四层记忆、CHANGELOG、跨项目 conventions、健康检查脚本
- `skills-repo` 明确设计了 Script → Skill → Agent 的三层金字塔、双 Agent、模板、守护进程和检查脚本
- `SYSTEM_STATUS.md` 还在尝试把这套系统讲给“接手的新 AI”听

这说明：**你的问题不是“没体系”，而是体系进入了治理阶段。**

#### B. 你已经有了“把规则写成脚本”的意识
`verify_memory.py`、`verify_conventions.py`、`verify_all.py`、`verify_prompt_system.py` 都在努力把“规则”下沉成可检查内容。
这非常重要，因为这比单纯堆 prompt 高一个层级。

#### C. 你已经意识到 prompt system 本身也要被审查
`verify_prompt_system.py` 的存在很关键。它说明你已经不满足于“写规则”，而是在检查：

- 规则是否重复
- 是否冲突
- 是否引用了不存在 / 归档对象
- 是否跨文件不一致

这一步已经接近真正的 harness engineering。

---

## 3. 当前最大问题：不是“规则太多”，而是“规则没有统一成一个可执行系统”

### 3.1 根因 1：规则来源太多，而且已经发生冲突

目前规则至少分散在这些地方：

- `_bootstrap/CLAUDE.md`
- `_bootstrap/agents/learning-agent.md`
- `_bootstrap/agents/work-agent.md`
- `_bootstrap/agents/guardian-agent.md`
- `global-memory/memory-rules.md`
- `global-memory/decisions/conventions.md`
- 两个仓库的 README
- `SYSTEM_STATUS.md`
- 各种 verify 脚本自己的注释/设计宣言

问题不只是“多”，而是**已经出现具体冲突**：

#### 冲突 A：CHANGELOG 规则冲突
- `CLAUDE.md` 写的是：**修改 `global-memory/` 下任何文件后，当场追加 CHANGELOG**。
- `memory-rules.md` 写的是：`knowledge/` 和 `interview/` 的 **append 不需要** 写 CHANGELOG；只有 `decisions/`、`feedback/`、UPDATE / DELETE 等必须写。
- `global-memory/README.md` 也写了同样的“分级规则”。

这意味着：**顶层铁律和详细规则冲突**。AI 不是“忽略规则”，而是**面对两个权威来源时不知道谁才是最终答案**。

#### 冲突 B：guardian-agent 自身存在行为冲突
- `guardian-agent.md` 的执行流程第一步写的是运行 `task_complete.py <项目目录> --fix`
- 但同一个文件铁律又写：**绝不自动修复**，即使 `--fix` 只修复格式问题

这会让守卫 Agent 的角色从“只检查”变成“边检查边修”，破坏角色边界。

#### 冲突 C：脚本声明和脚本实现不一致
`verify_conventions.py` 顶部写的是：

> 只检查标了 🔒 的规范

但实际它检查了 `DOC-04`、`GIT-02`、`HARNESS-02` 等**未标 🔒 的软约束**。
这意味着“规范文档”和“脚本行为”已经发生漂移。

---

## 4. 当前 harness 的真实能力边界

### 4.1 你现在更像“离线审计系统”，不是“运行时控制系统”

当前仓库里能看到的，主要是：

- `CLAUDE.md`
- Agent 配置
- 各类 verify 脚本
- `guardian-agent`
- `task_complete.py`

但我在当前能读到的 Git 资产中，**没有看到被纳管的 Claude Code hooks 配置**（例如 runtime hook 定义、settings 中的 hook handler 配置、InstructionsLoaded / PreToolUse / SubagentStart 等事件的实际接线文件）。

这意味着你的系统当前更偏向：

- **事后检查**：任务做完后跑 `verify_*`
- **静态检查**：文件存在、格式、字段、标题、提交信息等
- **文本一致性检查**：prompt 规则是否重复、是否漂移

而不是：

- **运行时拦截**
- **运行时记录**
- **运行时强制注入规则**
- **运行时拒绝危险操作**

所以你前面那句判断是对的，但需要更精确：

> **你现在不是完全没有 harness，而是 runtime harness 还没真正成型。**

---

## 5. 脚本层：哪些检查“真实有效”，哪些只是近似代理

下面按“强 / 中 / 弱”给出真实性评级。

### 5.1 `verify_memory.py`
**定位：结构健康检查**
**真实性：中高**

它真正能有效检查的内容：

- `MEMORY.md` 索引是否覆盖 topic 文件
- 索引链接是否存在死链
- topic YAML 头字段是否缺失
- CHANGELOG 是否存在、是否过旧
- 活跃项目表是否有交接文档字段
- 文件总数是否接近上限
- 空文件 / 极少内容文件
- 显式的 orphan 文件

这些都属于**结构性真检查**，是有效的。

但它也有明显边界：

1. `MEM-12 规范硬检查覆盖率`  
   实现只是在 `conventions.md` 中统计了多少条 `🔒`，**并没有验证这些条目是否真的被脚本一一覆盖**。  
   也就是说，这一项的名字比实现能力强。

2. `MEM-13 内容重复检测`  
   只是在比对不同文件里的 `##` 标题是否重复，不能真正发现“同一知识换个说法重复写”的问题。  
   这更像“章节模板重复检测”，不是“内容重复检测”。

**结论**：  
`verify_memory.py` 很适合做**结构体检**，不适合承担“知识质量”或“规则落实程度”的最终判断。

---

### 5.2 `verify_conventions.py`
**定位：项目规范 / 记忆规范检查**
**真实性：中**

它真正有效的检查：

- `docs/SPEC.md` / `HANDOFF.md` / `TECHNICAL_DESIGN.md` / `PROGRESS.md` 是否存在
- `.cs` 文件是否有 namespace
- `.h/.hpp` 是否有 include guard
- 最近 commit message 是否接近 conventional commits
- 当前分支是否是 main/master 且是否有代码改动
- `MEMORY.md` 的索引引用与实际文件是否同步

这些属于**可执行、可验证的真检查**。

但它也有几个关键问题：

1. 顶部说“只检查标了 🔒 的规范”，实际不是。
2. `MEM-01: 修改记忆文件必须写 CHANGELOG`  
   从实现看，它只是检查 `CHANGELOG.md` 是否存在并统计条目数，**并没有把最近 commit 中改动的 memory 文件与 changelog 条目做关联验证**。  
   所以它并没有真正验证“改了就记了”。

**结论**：  
`verify_conventions.py` 现在是“部分真检查 + 部分命名过强的近似检查”。

---

### 5.3 `verify_all.py`
**定位：系统基础设施总健康检查**
**真实性：中**

它有效的地方：

- 检查 CLAUDE.md 是否存在及行数
- 检查 MEMORY.md 索引引用文件是否存在
- 检查 skill symlink / SKILL.md / YAML / examples
- 检查两个 Git 仓库是否脏
- 检查模板、Agent、脚本是否在位
- 对比 baseline，确保“只升不降”

但它的边界和问题也很明显：

1. **硬编码严重**：`E:/CS-Study/Vibe`  
   这和“跨设备同步 / 新设备初始化”的目标是冲突的。  
   你虽然用 Git 做了跨设备，但 `verify_all.py` 仍然带有强烈的“某台 Windows 主机”的路径假设。

2. **平台依赖强**：`check_auto_sync()` 明显偏 Windows / PowerShell / tasklist  
   这在个人系统里可接受，但如果你把它当“跨设备基础设施”，就说明 portability 还不够。

3. `check_memory_health()` 的“内容不足”判断本质是启发式：
   它统计非 YAML / 非空行数量，无法判断 topic 是“合理简洁”还是“空壳”。

**结论**：  
`verify_all.py` 是有用的 infra health check，但离“设备无关的系统基线工具”还有距离。

---

### 5.4 `verify_prompt_system.py`
**定位：Prompt 系统一致性检查**
**真实性：中高**

这是你体系里非常有价值的部分，因为它真的在检查：

- 重复定义
- 过时引用
- 优先级违规
- 格式不一致
- 必要区块缺失
- Agent 是否在重述 CLAUDE.md 而不是引用

它的优点是：**直指你目前最痛的问题——规则漂移和 prompt 重复。**

但它依然只是静态文本检查，做不到：

- 某条规则在 runtime 是否真的被加载
- subagent 启动时到底拿到了什么上下文
- 哪条规则真的在某次任务中发挥了作用
- AI 为什么临场忽略了某条规则

**结论**：  
它非常适合做“防 prompt 腐化”的 lint，但不是 runtime harness 本身。

---

## 6. 当前系统的第二大问题：文档漂移已经开始了

你的系统里已经出现明显的“设计文档 / README / 状态说明 / 实现脚本”漂移。

典型表现：

1. `global-memory/README.md` 写的是“当前 15 条规范，14 条有硬检查”，但 `SYSTEM_STATUS.md` 里又写成“12 条，8 条硬检查”，而 `conventions.md` 实际内容已经继续演化。
2. `global-memory/README.md` 里一些统计数字和目录描述已经和 `MEMORY.md` 当前状态不一致。
3. `SYSTEM_STATUS.md` 自己明确承认很多内容是“框架搭好了但未真实使用验证”。

这类漂移会导致一个很现实的问题：

> **AI 读到的不一定是“当前规则”，而是“某个时间点的规则快照”。**

这比“规则太少”更危险，因为它会让系统显得很完整，但实际行为依据已经不统一。

---

## 7. 当前系统的第三大问题：记忆系统已经接近容量上限，且分类边界开始吃紧

`MEMORY.md` 里写的是：

- 总文件数：46 / 50

这本身不是立即爆炸的问题，但它说明：

1. 你的系统已经不是“还没长起来”，而是开始进入**存量治理阶段**
2. 继续把各种规则、审计、案例、模板都丢进 memory repo，会加快臃肿
3. “跨项目规范 / 深度文档 / 审查报告 / 临时 handoff / review-logs” 的边界必须更清楚

你前面说“最大问题可能是 harness 没设计到位”，我会更具体地说：

> **harness 的“治理边界”还没完全拉开。**

---

## 8. 目前系统的能力边界（总结版）

### 能做到的
- 跨设备同步记忆和 skill
- 用双 Agent 区分学习 / 工作场景
- 对 prompt system 做静态一致性检查
- 对 memory 结构做健康检查
- 对项目文档/代码/Git 规范做一部分自动化检查
- 在任务结束后做一次“交付前门禁”式收尾

### 做不到或做得不够稳的
- 运行时强制执行某条规则
- 运行时知道“本轮到底加载了哪些规则”
- 运行时知道 subagent 继承了哪些限制
- 运行时拒绝高风险操作（缺少显式 hook 层证据）
- 真正验证“改了记忆文件就一定写了 changelog”
- 真正验证“所有 🔒 规范都有一一对应的检查实现”
- 设备无关、路径无关的全平台健康检查

---

## 9. 你现在最该修什么（按优先级）

## P0：统一规则来源，先消灭冲突
先把以下四处里的冲突合并掉：

- `_bootstrap/CLAUDE.md`
- `global-memory/memory-rules.md`
- `global-memory/decisions/conventions.md`
- Agent 文件（learning/work/guardian）

**建议：**
- `CLAUDE.md` 只保留“摘要级铁律 + 优先级 + 启动协议”
- `memory-rules.md` 成为**唯一**的记忆写入细则来源
- `conventions.md` 成为**唯一**的跨项目规范来源
- Agent 文件只写“角色差异”，不重述公共规则

### 你要的效果
AI 再也不会同时看到两条互相冲突的 CHANGELOG 规则。

---

## P0：把 runtime harness 补起来
当前最缺的不是更多脚本，而是**运行时 hooks**。

建议至少补三类：

1. **InstructionsLoaded**  
   记录：本轮加载了哪些 `CLAUDE.md` / rules / agent 片段

2. **PreToolUse**  
   拦截：
   - 危险 bash
   - memory 文件写入但未附变更说明
   - 未满足条件却直接改受保护文件

3. **SubagentStart / SubagentStop**  
   记录：
   - 给子代理注入了哪些上下文
   - 子代理产出有没有结构化摘要

这样你就能把“AI 忽略 rules”变成可定位问题：
- 没加载？
- 加载了但冲突？
- 加载了但没强制？
- 执行了但没被审计？

---

## P1：脚本声明要和脚本实现严格对齐
优先修 4 个点：

1. `verify_conventions.py` 的头部说明要和实际检查项一致  
   如果它检查软约束，就不要再写“只检查 🔒”

2. `verify_memory.py` 的 MEM-12 要么真的做“规范→脚本”映射校验，要么改名  
   不要继续把“统计 🔒 数量”叫成“覆盖率检查”

3. `verify_conventions.py` 的 MEM-01 要么接 git diff / recent commits 做真校验，要么改成“CHANGELOG 存在性检查”

4. `guardian-agent.md` 的 `--fix` 矛盾必须去掉  
   要么只读检查，要么承认它会修非项目代码，但别两头都占

---

## P1：去掉 `verify_all.py` 的环境硬编码
把：

- `E:/CS-Study/Vibe`
- Windows 进程探测
- 本机固定目录假设

改成：

- repo 相对路径
- 环境变量优先
- 自动发现当前仓库根
- 平台分支处理（Windows / macOS / Linux）

否则这套系统会始终带着“某一台主机模板”的痕迹，与你的“跨设备同步工作系统”定位不一致。

---

## P1：把 README / SYSTEM_STATUS 变成自动产物，而不是手写状态板
你现在的漂移已经说明：
- 统计数字
- 文件数
- 规范条数
- 硬检查数
- Skill 完整度

这些不应该手写。

建议把以下内容自动生成：

- README 中的统计表
- SYSTEM_STATUS 中的文件数量、Skill 状态、规范数量
- conventions 的规则总数 / 🔒 数量
- MEMORY 的文件数和最后维护时间

**不要再让 AI 和你自己同时维护同一份“状态说明”。**

---

## P2：把 handoff / review-logs 的归属彻底定下来
你在 `SYSTEM_STATUS.md` 已经明确写出：
- `handoff/` 和 `review-logs/` 还只是本地目录，不在 Git 里

如果你希望这套系统跨设备、跨会话、可回溯，这两个目录迟早要决定：

- 纳入哪个仓库？
- 是项目级还是系统级？
- 是否参与索引？
- 什么时候归档？

这不是最急，但如果不定，未来会继续滋生“本地有、Git 上没有”的断层。

---

## 10. 最终判断

### 你的最大问题是什么？
**不是 agent 不够多，不是 memory 不够大，不是要不要换 Droid。**

而是：

> **规则系统已经进入“复杂度阈值”，但运行时 harness、规则来源治理、实现一致性还没跟上。**

### 一句话再压缩
> **你现在最缺的不是更多规则，而是“唯一权威来源 + 运行时 hook + 检查命名诚实 + 自动状态生成”。**

### 当前建议
在修完上面这些之前，**不建议把注意力转去更复杂的多 Agent 编排或 Droid 迁移**。  
因为你现在的痛点不是编排不够强，而是**系统基础治理正在开始漂移**。

---

## 11. 行动清单（最短路径版）

### 本周内
- [ ] 统一 CHANGELOG 规则：CLAUDE / memory-rules / README 三处只保留一个权威版本
- [ ] 修 guardian-agent 的 `--fix` 矛盾
- [ ] 给 `verify_conventions.py` / `verify_memory.py` 改正“名实不符”的检查项名称

### 下周
- [ ] 落地 3 个 runtime hooks：InstructionsLoaded / PreToolUse / SubagentStart
- [ ] 给 hooks 输出日志
- [ ] 做 5 条最小回归测试（危险命令、受保护路径、memory 写入、subagent 注入、规则加载）

### 之后
- [ ] 去硬编码路径
- [ ] 自动生成 README / SYSTEM_STATUS 的统计部分
- [ ] 再评估是否需要更高一层的编排系统

---

## 12. 结论标签

- **基础设施成熟度**：高
- **静态治理能力**：中高
- **运行时治理能力**：中低
- **规则一致性**：中低
- **跨设备可靠性**：中
- **当前最该补的层**：**runtime harness**
