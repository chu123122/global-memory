# 记忆变更审计日志

> 每次修改 global-memory 中的任何文件时，必须在此追加一条记录。
> 这是审计追踪的唯一来源——不记录就等于没改过。

### [2026-04-22 19:20] [APPEND] fixes_android_apk_build.md 加 7 类新坑（问题 4-10）
- **来源项目**：XDAdaptivePerformance Phase 1c 子线程化跨平台验证
- **变更内容**：`fixes/fixes_android_apk_build.md` 在原 3 类问题后追加 7 类新坑：
  - 问题 4：UE Editor 锁住编译输出 dll → LNK1104
  - 问题 5：单 OBB > 4 GiB 触发 stage 失败 + hybrid 拼装绕开方案
  - 问题 6：`adb install -r` 同 versionCode 覆盖装可能让 OBB 被 scoped storage 清（app uid 翻新）
  - 问题 7：Git Bash 下 `cmd //c "X.bat"` 不弹 console 进交互模式 → PowerShell 替代
  - 问题 8：`adb shell cp` 14.7 GB 慢/不稳 → 改用 mv 或直接 push 到目标
  - 问题 9：PSO Precompile + GMS 噪音淹 logcat → `-G 16M` + stream 模式 + 找最后一次 [T0] 起切分
  - 问题 10：MTK MAGT init `-8` (License Check Failed) — APK 签名 cert hash ≠ license 注册的，用 `xdaperf.keystore` (Lingyao Gan 持有) re-sign 而非 `torchlight.keystore`
- frontmatter `summary` 同步更新（10 类问题摘要）；`updated` → 2026-04-22；`source` 加 "Phase 1c 子线程化跨平台验证"
- **原因/案例**：今天跑 K60 + MT6899 真机验证 Phase 1c 子线程化时连撞 7 类坑，全部含具体修复方案。沉淀到 fixes 避免下次回头再踩
- **影响范围**：所有 UE 4 + Android 打包 / 装机 / OBB / MTK MAGT 鉴权场景

### [2026-04-22] [ADD] cpp-weak-token-async-lifetime.md 异步 lifetime 模式深度文档（博客草稿）
- **来源项目**：XDAdaptivePerformance Phase 1c 子线程化（用户提议把这个发现写成文档）
- **变更内容**：
  1. 新增 `knowledge/docs/cpp-weak-token-async-lifetime.md`（约 280 行，12 节）：问题起源 / 三类方案对比（裸 this / 手写 atomic flag / weak token）/ control block 本质 / 为什么需要 token 不直接 weak this / init-capture 语法 / Reset() 时机价值 / 跨语言对照 / UE 内部使用例 / 必须用 vs 可省 / 与 XD 插件的关联 / 4 类踩坑 / 30 秒面试讲法
  2. `knowledge/docs/INDEX.md` "C++ 语言与底层" 分组追加该文档链接
  3. `knowledge/knowledge_cpp_multithreading.md` 新增 "模式与文档" 段，索引该 doc + 一句话核心
- **原因/案例**：XD Phase 1c 实战中用户对 weak token 模式 + init-capture 语法的提问触发深度讲解。用户表示 "之前打算写一篇文档简单聊一下这个发现"，要求落地为文档。该模式跨语言通用（iOS [weak self] / Java WeakReference / Rust Weak<T>），值得作为博客草稿沉淀
- **影响范围**：C++ 多线程 / UE 异步编程 / 面试话术（已附 30 秒讲法）

### [2026-04-21 18:00] [ADD] feedback_diff_workflow + Edit/Write 后自动弹 VS Code diff 弹窗的全局 hook
- **来源项目**：XDAdaptivePerformance 重构（工作流改进副产物）
- **变更内容**：
  1. 新增 `feedback/feedback_diff_workflow.md`：B 协议规则 + 白名单目录定义 + 扩展/禁用方法 + "未来 AI 不要困惑" 现象解释
  2. 新增 `~/.claude/skills-repo/_bootstrap/scripts/hooks/diff_backup.py` (PreToolUse Write|Edit hook)：白名单内文件编辑前备份到 `D:\ClaudeTasks\.diff_backup\<name>.<sha1[:8]>.bak`
  3. 新增 `~/.claude/skills-repo/_bootstrap/scripts/hooks/diff_show.py` (PostToolUse Write|Edit hook)：编辑后异步 `start "" code --diff <bak> <file>` 弹 VS Code 三栏视图，5s 内同文件不重弹（debounce 状态记 `_lastshow.json`）
  4. `~/.claude/settings.json` 注册 hook：PreToolUse Write|Edit 数组追加 diff_backup；新增 PostToolUse Write|Edit 条目调 diff_show
- **白名单**（脚本顶部 WHITELIST 常量，两文件需同步）：
  - `D:\ClaudeTasks\active`（所有任务文档）
  - `C:\Perforce\tl_gaoxinag_01\frontend\trunk\Editor\UE_game\Plugins\XDAdaptivePerformance`（XD 插件源码）
- **原因/案例**：XD 重构期用户反馈 — AI 改完文件后 chat 贴 diff 描述表，用户扫一眼就过、把控感差。要求"修改完自动弹 diff 页面"，全脚本化避免每次 AI 跑命令的 token 消耗。三个决策点：白名单范围 OK / 5s 内不重弹 / 全局加白名单（不是项目级）
- **影响范围**：所有项目的 Edit/Write 行为，但仅白名单目录触发；其他目录无感
- **未来 AI 注意**：看到 VS Code 自动弹 diff 窗口或 `D:\ClaudeTasks\.diff_backup\` 下一堆 .bak 不是 bug，是这套 hook。详见 `feedback/feedback_diff_workflow.md`

### [2026-04-21 14:02] [UPDATE] README / MEMORY 元数据对齐 + 补 3 个 frontmatter
- **来源项目**：通用（记忆仓库整治）
- **变更内容**：
  1. `README.md` 改为当前实现口径：更新目录数量、健康检查入口为 `check_health.py`，并说明自动维护由部署侧 `Stop hook -> post_task_hook.py --auto-fix` 驱动
  2. `knowledge/knowledge_windows_dev_env.md`、`fixes/fixes_android_apk_build.md`、`decisions/decision_work_mode_workflow.md` 补齐 frontmatter（name/description/type/source/updated）
  3. `MEMORY.md` 中上述 3 个条目的描述改为可读版本，避免继续显示英文占位描述
  4. 部署侧 `post_task_hook.py` 的索引检查改为只读取 `MEMORY.md` 的 `AUTO-INDEX` 区块，不再把项目文档 / 系统索引误判成 topic 死链，减少无意义 `auto-fix` 提交
- **原因/案例**：README 仍引用历史脚本名 `verify_memory.py` / `auto_sync_daemon.py`，且健康检查持续报 3 个 YAML warning，导致入口说明和元数据都与现状不一致
- **影响范围**：所有项目（全局记忆入口 + 元数据质量）

### [2026-04-20 18:30] [APPEND] knowledge_cpp_pitfalls 加链接性/extern + TUniquePtr<前置声明>析构坑
- **来源项目**：心动 XDAdaptivePerformance 重构（学习副产物）
- **变更内容**：`knowledge/knowledge_cpp_pitfalls.md` 追加两大节：
  1. **链接性 vs 作用域 vs 存储期**：三维度区分表 + extern 工作机制（声明 vs 定义 + 链接器流程）+ external/internal/no linkage 表 + UE Unity Build 引发的 C4211 坑（static 定义 + extern 声明在同 TU 内冲突）+ header/cpp 标准模式
  2. **TUniquePtr<前置声明类> 析构 C4150**：PIMPL 必踩。原因（隐式 dtor 展开需完整类型）+ 修法（.h 显式声明 ctor/dtor，.cpp `= default`）+ 适用范围（unique_ptr/shared_ptr 都中招，TWeakObjectPtr 例外）
- **原因/案例**：CSV 采样逻辑抽 FCSVSamplerService 时连踩两坑：(1) Service.cpp `extern T CVar;` + Module.cpp `static T CVar(...)` 在 Unity Build 拼成同 TU 后 C4211 (2) Module.h 用 `class FCSVSamplerService;` forward decl + `TUniquePtr<FCSVSamplerService>` 成员，编译器为 Module 生成隐式 dtor 时报 C4150。两个都是面试高频 + 实战必遇
- **影响范围**：所有 C++/UE 项目

### [2026-04-20 17:00] [APPEND] 知识库追加 UE 智能指针 / 命名前缀 / Public-Private 语义 + C++ const 位置规则
- **来源项目**：心动 XDAdaptivePerformance 重构（学习副产物）
- **变更内容**：
  1. `knowledge/knowledge_ue_internals.md` 追加：TUniquePtr/TSharedPtr/MakeShared/MakeUnique/UE_NONCOPYABLE、FAutoConsoleCommand RAII 自注册、UE 类型命名前缀完整表（U/A/F/I/E/T/S/b）、Public/Private 目录的真正语义（不是 .h/.cpp 分开）
  2. `knowledge/knowledge_cpp_pitfalls.md` 追加：const 位置规则（const T / T const / T* const / const T* const 四态）+ 成员函数后置 const 的语义和约束
  3. 两文件 `updated` frontmatter 同步更新
- **原因/案例**：用户在重构期间问的 4 个 UE/C++ 概念问题（MakeUnique 是啥、F 前缀含义、UE_NONCOPYABLE 干嘛、const 位置区别），明确要求"记进 memory 后面回顾"。属于知识盲区落库
- **影响范围**：知识库（C++/UE 学习方向）

### [2026-04-20 15:30] [FIX/PUSH] post_task_hook 同步 skills-repo + 暴露 push 错误 + 手动追推
- **来源项目**：claude-system-cleanup
- **变更内容**：
  1. `post_task_hook.py` `git_sync_repo` 改返回 `(ok, msg)`，push 失败把 stderr tail 暴露出来；不再 `capture_output=True` 裸吞错
  2. `main()` 同步循环改为 `[MEMORY_DIR, SKILLS_DIR]` 双仓推送，失败计入 `result.errors`（pre-commit 模式会阻止 commit）
  3. 加 `skills-repo/.gitignore` 忽略 `__pycache__`，`git rm --cached` 清掉历史 pyc
  4. 手动 `git pull --rebase` global-memory（17 个 auto-fix commit 落后 1 远端 commit `f8a5af9`，远端只加新文件 → 干净 rebase）→ push 成功
  5. 手动 commit + push skills-repo（marker 模式 sync_index、update_stats 边界修、A 独有 hooks/session_report/smoke_test/stage_lib 全量 cp）
- **原因/案例**：上一轮检查发现 global-memory ahead 17 commits 没人推、skills-repo 7 个文件未提交。根因 `post_task_hook.git_sync_repo` 用 `capture_output=True` 静默吞 push 错误（远端有新 commit 一直 reject 但 hook 报 ✅）
- **影响范围**：全局基础设施（自动同步链路 + 两个核心仓库实际推送）
- **验证**：global-memory `9185328` / skills-repo `d779aaa` 均 push 成功；下次 Stop hook 触发若再失败会在 result.errors 里直接报出来

### [2026-04-20 14:50] [FIX] update_stats.py 修边界 + sync_index 加自愈 + 新 feedback
- **来源项目**：claude-system-cleanup（D:/ClaudeTasks/active/claude-system-cleanup/）
- **变更内容**：
  1. `update_stats.py` 正则边界加入 `\n<!-- AUTO-INDEX:END`，不再吞 marker（这是导致 marker 累积 bug 的根因）
  2. `sync_index.py` legacy-migrate 路径增加 strip 孤儿 marker 的防御逻辑（即使别处出问题也能自愈）
  3. 新建 `feedback/feedback_infra_ops_windows.md`：3 条铁律（PowerShell 建 junction / 删 hook 引用目录原子化 / marker-aware 工具链）
- **原因/案例**：上一条 CHANGELOG 后发现 MEMORY.md 累积了 7 个 AUTO_BEGIN marker，0 个 END。根因是 update_stats 的正则贪心吞 END，sync_index 误入 legacy-migrate 反复加 BEGIN
- **影响范围**：全局基础设施（记忆维护脚本工具链一致性）
- **验证**：BEGIN=1, END=1；3 个自定义区块仍在；A/B 通过 junction 自动一致

### [2026-04-20 14:20] [FIX/REFACTOR] sync_index.py 改 marker 模式 + 批次 3 收尾
- **来源项目**：claude-system-cleanup（D:/ClaudeTasks/active/claude-system-cleanup/）
- **变更内容**：
  1. `skills-repo/_bootstrap/scripts/sync_index.py` 重写为 `<!-- AUTO-INDEX:BEGIN/END -->` marker 模式：只重建 markers 之间，区块外的 📌/🏗️/📜 自定义章节不再被覆写；首次运行带 legacy-migrate
  2. MEMORY.md 恢复 📜 复盘记录区块；自动区用 markers 包裹
  3. A/B scripts 双轨合并：9 个分化 .py 全部保留 B（auto-fix 维护版本）；A 独有 session_report.py + smoke_test.py + 整个 hooks/ 目录 cp 入 `skills-repo/_bootstrap/scripts/`；A 整目录备份到 `~/.claude/_backups/scripts_20260420/`
  4. `~/.claude/scripts` 改为 directory junction → `~/.claude/skills-repo/_bootstrap/scripts`（PowerShell `New-Item -ItemType Junction` 建立，git bash `cmd //c mklink` 报"无效语法"踩坑）
  5. 用户在过程中改 settings.json 把 6 处 hook 路径直指 `skills-repo/...`（删 A 后 hook 链路断裂导致工具被 PreToolUse 阻塞，需手动解锁）
- **原因/案例**：HANDOFF.md「新发现 P0」要求修 sync_index 否则 MEM-11 持续被破坏；批次 3 是 SPEC 收尾批次
- **影响范围**：全局基础设施（脚本路径、hook 行为、记忆索引算法）
- **验证**：MEM-11 PASS；verify_all = 10 PASS / 4 WARNING / 0 ERROR

### [2026-04-20 13:30] [REWRITE] MEMORY.md + NEW knowledge/docs/INDEX.md
- **来源项目**：claude-system-cleanup（D:/ClaudeTasks/active/claude-system-cleanup/）
- **变更内容**：
  1. 重建 MEMORY.md：补全 30+ 漂移文件的索引；新增「📌 系统规则与索引」「🏗️ 项目文档」「📜 复盘记录」三个区块
  2. 新建 knowledge/docs/INDEX.md：30 篇深度文档分 6 组索引（MEMORY.md 不再一一列出）
  3. 改 verify_memory.py MEM-11：递归白名单制（黑名单 = 系统/运维文件 + 子目录），docs/ 走 INDEX.md 校验；A/B 两套同步
- **原因/案例**：REVIEW-2026-04-20-1220.md 发现 MEMORY.md 索引声称 49/50 实际 64+，30+ 文件未索引；MEM-11 检测漏 docs/test-reports/retrospectives/ 等子目录
- **影响范围**：影响所有项目（全局记忆入口 + 全局健康检查脚本）
- **遗留**：linter/hook 在持续改 MEMORY.md（删 retro 区块、回退统计），见 HANDOFF.md「新发现 P0」

### [2026-04-20 13:30] [MIGRATE] skills/work → skills-repo/work/v1/ + junction
- **来源项目**：claude-system-cleanup
- **变更内容**：
  1. `skills-repo/work/v1/` 新建（完整复制部署位 SKILL.md + scripts/ + templates/）
  2. 备份 `skills/work/` 到 `~/.claude/_backups/skills_work_20260420/`
  3. `skills/work/` 改 directory junction → `skills-repo/work/v1/`
- **原因/案例**：work skill 仅在部署位存在、repo 无源 → 重部署会丢失
- **影响范围**：影响所有项目（/work skill 来源）


## 格式规范

```markdown
### [YYYY-MM-DD HH:MM] [操作类型] [文件路径]
- **来源项目**：[项目名 / 通用]
- **变更内容**：[一句话描述改了什么]
- **原因/案例**：[为什么改，来自什么具体场景]
- **影响范围**：[只影响本项目 / 影响所有项目]
```

操作类型：`CREATE` | `UPDATE` | `DELETE` | `PROMOTE`(从项目级提升为全局规范)

---

## 变更记录

### 2026-04-13 12:00 CREATE knowledge/docs/*.md (6 个文档)
- **来源项目**：通用
- **变更内容**：批量生成 6 个深度知识文档（UE 引擎/C++ 多线程/Prompt 体系/面试追问链/项目话术/Code Review）
- **原因/案例**：离职前最大化利用 token 生成可离线使用的知识资产
- **影响范围**：所有项目


### 2026-04-13 13:00 CREATE knowledge/docs/async-resource-loading-preresearch.md
- **来源项目**：心动引擎中台（预研）
- **变更内容**：多线程资源加载预研文档（692 行，3 方案对比）
- **原因/案例**：入职心动前的技术准备
- **影响范围**：心动项目


### 2026-04-13 13:30 CREATE knowledge/docs/interview-cheatsheet.md
- **来源项目**：通用
- **变更内容**：面试速查卡（118 行，UE 10 模块 + C++ 多线程一句话速记）
- **原因/案例**：从深度文档中提炼的口语化版本
- **影响范围**：所有项目


### 2026-04-13 14:00 CREATE projects/xindong-engine/dev-map.md + task-board.md
- **来源项目**：心动引擎中台
- **变更内容**：项目导航模板和任务板
- **原因/案例**：为入职后的项目上下文做准备
- **影响范围**：心动项目


### 2026-04-13 15:00 UPDATE MEMORY.md
- **来源项目**：通用
- **变更内容**：顶部新增"🔥 当前活跃项目"区块
- **原因/案例**：新 AI 对话不知道当前在做什么项目，需要一个入口锚点
- **影响范围**：所有项目


### 2026-04-13 16:53 CREATE CHANGELOG.md
- **来源项目**：通用
- **变更内容**：记忆变更审计日志，追溯所有历史变更
- **原因/案例**：跑了两个项目后发现无法追踪"谁改了什么记忆、为什么改"
- **影响范围**：所有项目


### 2026-04-13 16:53 CREATE decisions/conventions.md
- **来源项目**：帧同步 v2 + 博客重设计（PROMOTE）
- **变更内容**：12 条跨项目规范，8 条标注 🔒 硬检查
- **原因/案例**：帧同步项目中总结的好实践（SPEC 先行、HANDOFF 必备、namespace 必须有等），需要同步给其他项目
- **影响范围**：所有项目


### 2026-04-13 16:53 UPDATE MEMORY.md
- **来源项目**：通用
- **变更内容**：索引新增 Decisions 和审计区块（conventions.md + CHANGELOG.md）
- **原因/案例**：verify_conventions.py 检查出 MEM-03 WARNING（索引不同步）
- **影响范围**：所有项目


### 2026-04-13 17:05 CREATE scripts/verify_memory.py
- **来源项目**：通用
- **变更内容**：记忆仓库健康检查脚本（13 项自动检查），替代人工/AI 审查
- **原因/案例**：跑了两个项目后记忆格式不一致（docs/ 无 YAML、conventions.md 无 YAML），需要自动化检测
- **影响范围**：所有项目


### 2026-04-13 17:06 UPDATE decisions/conventions.md
- **来源项目**：通用
- **变更内容**：添加 YAML 头部（name/description/type/created/updated/source）
- **原因/案例**：verify_memory.py MEM-03 ERROR 检测到 decisions/ 下文件缺少 YAML 头
- **影响范围**：所有项目


### 2026-04-13 17:22 CREATE scripts/maintain_memory.py
- **来源项目**：通用
- **变更内容**：记忆仓库自动维护脚本（sync-index/update-stats/init-project/close-project/changelog）
- **原因/案例**：verify 系列脚本只检测不修复，需要一个自动修复/维护的脚本
- **影响范围**：所有项目


### 2026-04-13 17:33 UPDATE scripts/*
- **来源项目**：通用
- **变更内容**：拆 maintain_memory.py 为 6 个单一职责脚本(_lib/sync_index/update_stats/init_project/close_project/append_changelog) + 新增 update_readme.py，所有脚本加留档到 ~/.claude/logs/
- **原因/案例**：职责单一原则+错误最小化+运行留档
- **影响范围**：所有项目


### 2026-04-13 18:56 CREATE knowledge/docs/4个搜索文档
- **来源项目**：通用
- **变更内容**：心动情报+面试趋势+UE5异步加载+Harness 2026最新实践
- **原因/案例**：离职前最大化利用token收集外部情报
- **影响范围**：所有项目


### 2026-04-13 19:07 CREATE knowledge/docs/game-physics-reference.md + game-networking-reference.md
- **来源项目**：通用
- **变更内容**：物理模拟(PBD/XPBD/赛车) + 网络同步(帧同步/RUDP/GGPO)技术参考
- **原因/案例**：面试准备 + 帧同步项目技术验证
- **影响范围**：所有项目


### 2026-04-13 19:10 UPDATE knowledge/docs/game-physics-reference.md + game-networking-reference.md
- **来源项目**：通用
- **变更内容**：补充GDC物理演讲/GGST回滚/永劫无间混合同步/Gaffer On Games/网易雷火/事件流同步
- **原因/案例**：用户要求补充更多行业文献和具体游戏方案
- **影响范围**：所有项目


### 2026-04-13 19:18 UPDATE knowledge/docs/game-*-reference.md
- **来源项目**：通用
- **变更内容**：补充GGPO深度架构/GGST/永劫无间/Gaffer7篇/Fix Your Timestep/雷火三部曲/事件流/Catto12场GDC/CCD/Sequential Impulses/Dynamic BVH
- **原因/案例**：用户要求补充更多行业文献
- **影响范围**：所有项目


### 2026-04-13 19:27 UPDATE _bootstrap/CLAUDE.md + agents/*.md
- **来源项目**：通用（双 Agent 审查）
- **变更内容**：修复 15 个审查问题（3🔴+6🟡+6🟢）：工作背景改动态引用、MEMORY_UPDATE格式补齐、个人项目限定为学习、启动协议去重、Skill触发对照表、转交判断、苏格拉底豁免、审查例外、讨论模式、对外沟通约束、CHANGELOG格式内联、代码审查子模式、fixes门槛扩展、compact规则明确、简历场景
- **原因/案例**：5维度审查发现工作背景即将过时(V4)、记忆写入不可预测(U1)、Agent边界模糊(M1)等关键问题
- **影响范围**：所有项目


### 2026-04-13 19:55 UPDATE 系统架构深度优化（6 项）
- **来源项目**：通用（架构审查）
- **变更内容**：
  1. Skill 下沉：workspace-init/multi-search-engine/memory-manager/doc-generator → _archived/
  2. 记忆写入一致性：MEMORY_UPDATE 增加 update/conflict 操作 + 去重/矛盾检测
  3. 深度文档标注为快照，Topic 为准
  4. CHANGELOG 归档：新增 changelog_archive.py 周归档脚本
  5. L2 记忆 A+B 方案：Topic YAML 加 summary + generate_project_context.py 关键词预判注入
  6. MEMORY.md 索引改为 summary 摘要格式 + references 区块
- **原因/案例**：架构审查发现 Skill 膨胀、L2 按需读取不可靠、记忆写入重复/矛盾、CHANGELOG 膨胀、docs 和 Topic 分叉
- **影响范围**：所有项目


### 2026-04-13 21:00 CREATE knowledge/docs/resource-links.md + ue-source-deep-dive.md + cpp-memory-model-lockfree.md
- **来源项目**：通用（WorkBuddy 资料整理）
- **变更内容**：
  1. `resource-links.md` — 48 篇高质量技术文章链接索引（9 大类，每类标 ★）
  2. `ue-source-deep-dive.md` — UE5 八大模块源码级参考（反射/GC/Subsystem/Delegate/TaskGraph/Timer/异步加载/FTimerManager），基于多篇文章交叉验证整合
  3. `cpp-memory-model-lockfree.md` — C++ 内存模型与无锁编程深度参考（6 种 memory_order/Happens-Before/CAS/无锁栈/自旋读写锁+完整代码+性能对比）
- **原因/案例**：用户搜集大量高质量 UE 源码分析和 C++ 深度资料，抓取核心文章后做批判性整合
- **影响范围**：所有项目


### 2026-04-13 21:15 CREATE 4 个战略/方法论文档
- **来源项目**：通用（WorkBuddy 深度分析）
- **变更内容**：career-strategy-2027.md + ai-impact-game-dev.md + learning-methodology.md + onboarding-plan.md
- **原因/案例**：利用深度分析做职业规划/AI 冲击/学习方法/生活优化
- **影响范围**：所有项目


### 2026-04-13 21:22 CREATE knowledge/docs/gdc-must-watch.md
- **来源项目**：通用（WorkBuddy 整理）
- **变更内容**：GDC 必看演讲清单（28 演讲 × 7 方向）
- **影响范围**：所有项目


### 2026-04-14 02:30 CREATE FIXLIST.md（CLI 迁移审计）
- **来源项目**：系统级
- **变更内容**：CLI 适配问题清单（5P0+11P1+4P2），Sonnet 4.6 全量测试 T01-T38 生成
- **影响范围**：所有项目


### 2026-04-14 04:20 CREATE test-reports/ 9 组报告 + final-summary + smoke
- **来源项目**：通用（系统验证）
- **变更内容**：T01-T38 全量测试报告 + 夜间冒烟测试 + 博客音乐播放器复盘
- **影响范围**：通用


### 2026-04-14 09:16 UPDATE MEMORY.md + CHANGELOG.md（merge 冲突解决）
- **来源项目**：通用（WorkBuddy 同步）
- **变更内容**：解决 CLI 端和 WorkBuddy 端的 3 处 git merge 冲突，合并两边内容
- **影响范围**：所有项目


### 2026-04-14 09:35 CREATE interview/resume-versions.md + UPDATE question_bank + system_design
- **来源项目**：通用（Study/ 目录文件清理整合）
- **变更内容**：
  1. `interview/resume-versions.md` — 简历定稿版（引擎版+客户端版+面试钩子策略）
  2. `interview/interview_question_bank.md` — 大规模更新：心动二面完整记录+米哈游 140 题+算法/OS/场景设计
  3. `knowledge/knowledge_system_design.md` — 万能 5 步框架+A 攻击 B 标准答案+项目对应表+练习清单
- **原因/案例**：用户清理 D:/TestContent/Study/ 12 个文件，提取有价值内容沉淀
- **影响范围**：面试全方位


### 2026-04-14 09:45 UPDATE feedback_code_style.md + feedback_output_format.md
- **来源项目**：通用（T01-T38 评估后批量修复）
- **变更内容**：两个 feedback 文件从空壳激活——预填已知偏好（C++ 红线/UE 规范/回答风格/方案对比规则）
- **原因/案例**：T16 暴露 feedback 系统完全空壳，从未有真实纠正记录
- **影响范围**：所有项目


### 2026-04-14 09:54 CREATE agents/guardian-agent.md + UPDATE CLAUDE.md + FIXLIST.md
- **来源项目**：通用（WorkBuddy 系统修复）
- **变更内容**：
  1. 新建 `guardian-agent.md` — 规范守卫 Agent（5 大类检查清单 + 脚本辅助 + PASS/CONDITIONAL/FAIL 判定）
  2. CLAUDE.md 新增「交付前门禁」铁律 — 交付前必须派生 guardian-agent，FAIL 阻断交付
  3. FIXLIST.md 更新已修复进度（13 项已修复）
- **原因/案例**：系统分析发现"脚本全有但没串联"，guardian-agent 是结构性解法
- **影响范围**：所有项目


### 2026-04-14 09:57 UPDATE test-reports/ 合并 + MEMORY.md 索引 + conventions FILE-01
- **来源项目**：通用（系统修复 FIX-02/21/23）
- **变更内容**：
  1. test-reports/ 9 个 group 文件合并为 `all-tests-detail-2026-04-14.md`，文件数 49→41
  2. MEMORY.md 索引更新（test-reports 区块 + 文件计数修正）
  3. conventions.md 新增 FILE-01 静态资源文件名 ASCII 化规范
- **原因/案例**：文件数接近上限 49/50 需清理；博客复盘发现文件名问题需规范化
- **影响范围**：所有项目


### 2026-04-16 14:00 CREATE fixes/fixes_android_apk_build.md + UPDATE task-board.md + MEMORY.md
- **来源项目**：心动引擎中台（火炬之光 Android 打包）
- **变更内容**：
  1. 新建 `fixes/fixes_android_apk_build.md` — Git Bash 环境下 UE4 Android 打包的三个兼容性修复
  2. 更新 `projects/xindong-engine/task-board.md` — 新增 Android APK 打包需求专项记录（进度、卡点、修复记录、关键文件位置）
  3. 更新 MEMORY.md 索引（Fixes 区块新增条目）
- **原因/案例**：首次在本机跑完 Android 打包全流程，沉淀 Git Bash + UE bat 工具链兼容性经验（NoDefaultCurrentDirectoryInExePath / subst / MSYS_NO_PATHCONV）。当前卡在 ShaderCodeLibrary 初始化失败（Global Shader 缺失）
- **影响范围**：心动项目 + 通用 Git Bash 经验



### 2026-04-17 12:15 CREATE decisions/decision_work_mode_workflow.md + skills/work/ 全套 + 改 work-agent.md
- **来源项目**：通用（harness 升级）
- **变更内容**：
  1. 新建 `skills/work/SKILL.md` + `scripts/{load_context,check_doc_status,check_doc_sync}.py` + `templates/workflow.md` — 工作模式统一入口
  2. 新建 `decisions/decision_work_mode_workflow.md` — 架构决策记录（三层文档防线 + 为什么不用 hook/subagent）
  3. 修改 `agents/work-agent.md` — 顶部加「流程入口」章节指向 `/work`，保留所有现有子模式
  4. 修改 `MEMORY.md` Decisions 区块加索引
- **原因/案例**：work-agent 之前是「人格描述」靠自觉走启动协议，会漏文档校验和收尾同步。spec_gate.py 是 PreToolUse 被动拦截，触发时已经在写代码了。统一为 `/work` skill 显式入口 + 三层文档防线（入口主动校验 / spec_gate 兜底 / 收尾追踪）
- **影响范围**：所有项目（替代 work-agent 的隐式启动协议）



### 2026-04-22 UPDATE projects/xindong-engine/task-board.md（Android APK 移入已完成）
- **来源项目**：心动引擎中台
- **变更内容**：
  1. Android APK 打包从「进行中/闪退」迁到「已完成」（2026-04-21 红米 K60 真机跑通）
  2. 当前进行中加入 XDAdaptivePerformance 重构（Phase 1c），关联 baseline-logs 位置
  3. 专项记录中标注 ShaderCodeLibrary 闪退已解决，但**修复手段未沉淀**，标待补
- **原因/案例**：用户告知"手机包已经打成功过了，红米跑通"。task-board 状态严重过期需对齐
- **遗留**：等用户回忆 ShaderCodeLibrary 实际修复路径（是否补 .uproject 插件启用、是否走全量 Cook、还是别的方案），补 `fixes/fixes_shader_code_library_missing.md`

### 2026-04-22 CREATE fixes/fixes_shader_code_library_missing.md
- **来源项目**：心动引擎中台
- **变更内容**：
  1. 新建 `fixes/fixes_shader_code_library_missing.md` — 修复手段：去掉 minimal cook 走全量 cook
  2. 更新 task-board.md 已完成行 + 专项记录闪退段，加 fix 文档链接
- **原因/案例**：用户回忆确认 ShaderCodeLibrary 闪退最终修法（红米 K60 验证通过）。沉淀关键经验：minimal cook 不能用于打可分发 APK，Global Shader 必须全量 cook
- **关联**：项目里另有「插件未启用 → Cook 失败」根因链（fixes_android_apk_build.md / CLI memory fixes_android_build.md），fix 文档里已交叉引用并给出区分方法


### 2026-04-22 ARCHIVE D:/ClaudeTasks/active/memory-system-merge → archived/
- **来源项目**：claude harness 自身
- **变更内容**：
  1. global-memory + skills-repo 单仓合并执行完成（Phase A 备份 / B 杀 daemon / C bootstrap install / D check 全绿）
  2. `~/.claude/{agents,scripts}` 现以 junction 指向 `D:/global-memory/{agents,harness}`；`~/.claude/skills/` 为普通目录含合并后的 skill junction
  3. `settings.json` 8 个 hook 全部改写为 `D:/global-memory/harness/hooks/*.py` 路径
  4. `auto_sync_daemon` 装 Windows Startup（`Startup/auto_sync_startup.vbs`）实现开机自启，弥补此前**无任何自启机制**的盲区（switch.sh "自动重启" 文档误导已确认）
  5. 修复 `~/.claude/CLAUDE.md` 中 `skills-repo/check/v1/SKILL.md` 残留路径 → `skills/check/SKILL.md`
  6. 任务 `memory-system-merge` 三份文档 Status 从 `implementation` 改为 `archived`，从 `project_registry.json` 的 `active_tasks` / `task_paths` 移除，目录从 `active/` 移到 `archived/`（源目录残留空壳，被 Defender/索引器锁住，重启后清）
- **原因/案例**：用户判定合并方案落地、所有 5 项 D 阶段验证通过。归档以释放 active_tasks 槽位
- **影响范围**：所有依赖 `~/.claude/skills`、`~/.claude/scripts`、`~/.claude/agents` 的 skill / hook / 脚本路径——全部通过 junction 透明寻址，外部无需改动
- **遗留**：①`active/memory-system-merge` 空目录待手动 `rmdir`（Windows 文件锁缓存）②`registry.templates_dir` 仍指向 `D:/skills-repo/_bootstrap/templates`，若后续清理 `D:/skills-repo` 需同步改 ③`claude-system-cleanup` 任务存在但未登记 `active_tasks`，按需补
