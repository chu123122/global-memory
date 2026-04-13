---
name: retro-2026-04-14-blog-music-player
description: 2026-04-14 博客页脚音乐播放器开发复盘，真实流程 vs 规范流程对照
type: project
created: 2026-04-14
project: blog (redesign-astro)
feature: 页脚音乐播放器 (Option C)
---

# 复盘：博客页脚音乐播放器

> 执行时间：2026-04-14
> 任务：为 chu's Blog (redesign-astro 分支) 添加页脚隐藏式音乐播放器
> 执行者：Claude Sonnet 4.6

---

## 一、真实执行流程（时序）

1. 用户提出需求：给博客添加音乐播放功能，不想用传统播放器
2. AI 通过 WebFetch 尝试读取 GitHub 仓库结构和样式 → **失败3次**（均得到摘要而非原始代码）
3. AI 提出三个设计方向（A: 右侧竖栏融合 / B: 悬浮胶囊 / C: 隐于 Footer）+ 建议
4. 用户选择方案 C，要求先看效果
5. AI 再次通过 WebFetch/curl/GitHub API 尝试获取原始代码 → 多次失败/绕路
6. **用户纠正**："请直接本地克隆下来进行操作"
7. AI 克隆仓库到 `/c/Users/chu/blog-local`
8. 读取 `BaseLayout.astro` 和 `global.css` → 成功获取真实代码
9. 实现播放器 HTML + CSS + JS，写入两个文件
10. 运行 `npm run dev` → 失败：Node v20.14 不满足 Astro 6 的 ≥22.12 要求
11. 用 winget 升级 Node → 安装 v24.14.1（覆盖式安装到 `/e/node.js/`）
12. 手动更新当前 shell PATH → dev server 成功启动（localhost:4321）
13. 用户添加了 MP3 文件但播放器无反应 → AI 诊断：文件放对了但未加入 PLAYLIST
14. AI 顺手将带特殊字符的文件名重命名为 `yorushika-dakara.mp3`，加入歌单
15. 用户确认效果可以，要求推送（不含音乐文件）
16. 在 `.gitignore` 加音频文件排除规则 → commit → push
17. 用户要求写本复盘文档

---

## 二、遵守的流程

| 规范 | 条目 | 情况 |
|------|------|------|
| GIT-01 | commit message 使用 conventional commits | ✅ `feat: 页脚音乐播放器`，格式正确 |
| GIT-02 | 特性开发在独立分支，不改 main | ✅ 始终在 `redesign-astro` 分支 |
| 铁律 | 直接给方案 + trade-off，少废话 | ✅ 三方案对比后给出明确建议 |
| 铁律 | 修改代码前先读文件 | ✅ 读了 BaseLayout.astro、global.css 才动手改 |
| 铁律 | 完成任务后只陈述事实 | ✅ 推送后没有自评质量 |
| 安全 | 推送前确认不含用户私有内容 | ✅ .gitignore 排除 mp3/flac/ogg |
| 风格一致 | 使用项目已有 CSS 变量（--accent, --font-serif...）| ✅ 未引入新变量，完全使用已有 token |

---

## 三、违反的流程

### V1 — 新对话启动协议完全跳过（严重）

**规范要求**：正式任务（>3 轮）必须先读 MEMORY.md → 读对应项目的 HANDOFF.md → 核对进度 → 确认后动手。

**实际行为**：
- MEMORY.md 由系统自动注入，但 AI 没有主动读取 blog 项目的 HANDOFF.md
- HANDOFF 中写明"Phase 5 进行中（Cloudflare Pages 部署，待确认）"以及"Astro 项目未初始化" — 但此信息已过时，实际 Astro 项目早已初始化
- AI 未和用户核对"上次做到哪了"，也未确认当前状态是否与 HANDOFF 一致
- **结果**：MEMORY.md 中的博客状态描述（"Astro 项目未初始化"）是错误的过时信息，但全程未被发现和纠正

### V2 — Agent 判定规则跳过（中等）

**规范要求**：未指定模式 → 问"这次是学习还是干活？"；工作模式 → 通过 `Agent(subagent_type="work-agent", ...)` 派生工作 Agent。

**实际行为**：
- 用户说"再跑一轮真实的工作流程来吧"，AI 没有识别为工作模式或主动确认
- 全程以主 Claude 身份直接执行，未派生 work-agent
- 这是 FIXLIST 中 P0-4 问题的再次复现

### V3 — DOC-05 / HARNESS-01：动手前无设计文档（中等）

**规范要求**：任何功能开发前必须有 SPEC，明确需求和验收标准。

**实际行为**：
- 直接从用户口头需求跳到实现，未在 blog 的 docs/ 下创建任何设计文档
- 没有验收标准文档（"播放器应该支持哪些功能？" — 在实现过程中靠猜）
- 用户后来发现 MP3 没反应，这是一个本可在设计阶段明确的边界情况（"歌单如何配置？"）

### V4 — 三层金字塔未考量（轻微）

**规范要求**：能用下层就不用上层（逻辑固定→scripts/，流程固定→skills/，动态决策→Agent）。

**实际行为**：
- 没有检查是否有可复用的 Skill（前端功能实现类）
- 直接进入动态 Agent 执行模式，未考虑是否有固定流程可走

### V5 — 记忆写入条件检查缺失（中等）

**规范要求**：对话结束前检查是否需要写入 knowledge/feedback/fixes/conventions。

**实际行为**：
- Node 版本兼容性踩坑（v20 vs v22+）有 fixes 价值，未记录到 fixes/
- 音频文件命名规范（特殊字符导致路径问题）有 conventions 价值，未记录
- 用户纠正"直接克隆"这条反馈有 feedback 价值，未记录

### V6 — verify_prompt_system.py 未运行

**规范要求**：交付前运行 `python ~/.claude/skills-repo/_bootstrap/scripts/verify_prompt_system.py --report`。

**实际行为**：全程未运行，无论是开发前还是推送前。

---

## 四、无效操作（浪费的步骤）

| 步骤 | 浪费原因 | 应该怎么做 |
|------|---------|-----------|
| WebFetch x3 尝试获取原始代码 | WebFetch 对 GitHub 文件始终返回摘要，不返回原始代码 | 直接用 `gh api` 或 clone |
| curl + python base64 decode（两次失败） | Windows Git Bash 下管道 python 解码静默失败 | 用 `curl -o /tmp/file` 然后读文件 |
| `find $HOME -name "astro.config.mjs"` 搜索本地仓库 | 搜索大量目录耗时，且被用户中断 | 直接问用户 / 直接克隆 |
| 升级 Node 后 PATH 未自动更新 | winget 安装到 `/e/node.js/` 而非新路径，当前 shell 不感知 | 升级后提示用户重开终端，或手动 export PATH |

---

## 五、实现中的技术缺陷（未发现）

1. **`<script>` 中的 TypeScript 类型注解**：使用了 `as HTMLAudioElement | null` 和参数类型注解。Astro 的 `<script>` 默认走 Vite TypeScript 处理，这些能工作，但没有加 `lang="ts"` 标注，依赖隐式行为。
2. **歌单为空时的处理**：歌单空时隐藏播放器（用 `style.display="none"`），但如果用户只注释了条目、没删除文件，`.gitkeep` 占位仍然存在，容易误解。
3. **无状态持久化**：用户刷新页面后播放进度和播放状态丢失。localStorage 未做。
4. **无音量控制**：最简版没有音量滑块，用户只能依赖系统音量。
5. **CORS 风险**：测试时放了 soundhelix.com 外链，该站点可能有 CORS 头限制，未验证能否在浏览器中加载。

---

## 六、本次可 PROMOTE 到 conventions.md 的规范（待决策）

### 候选 1：文件名 ASCII 化规范

**问题**：下载的日文文件名包含全角字符、空格、括号，在 Git、URL、路径处理中都可能出问题。本次被迫 rename。

**候选规范**：
```
FILE-01：静态资源文件名必须 ASCII 化
规则：提交到 Git 仓库的所有静态资源（图片/音频/字体），文件名只允许
      ASCII 字母、数字、连字符、下划线和点。
来源：blog 项目音乐文件「1-【ヨルシカ】...AVC.mp3」→ 必须 rename
```

### 候选 2：Node 环境版本记录规范

**问题**：Astro 6 要求 Node ≥22.12，但开发者机器可能有旧版本。这类环境依赖没有记录。

**候选规范**：在 TECHNICAL_DESIGN.md 中增加"环境要求"章节（Node/npm 最低版本）。

---

## 七、总结评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 启动协议遵守 | 1/5 | HANDOFF 未读，进度未核对 |
| Agent 流程 | 1/5 | work-agent 未派生，模式未确认 |
| 设计文档前置 | 0/5 | 无 SPEC，直接开干 |
| 代码实现质量 | 3/5 | 功能可用，有若干技术债未处理 |
| Git 规范 | 4/5 | commit 格式正确，分支正确，gitignore 到位 |
| 记忆沉淀 | 1/5 | 未做结束前写入检查（本文档是被要求后补写的） |
| 整体 | 2/5 | 功能交付了，但 Harness 体系形同虚设 |

**核心问题**：用户说"再跑一轮真实的工作流程"，但实际上 AI 跳过了几乎所有启动协议和设计前置步骤，退化为"接需求→直接写代码"的模式。这正是 Harness 体系要防止的行为。

---

## 更新日志
- 2026-04-14: 初始创建，任务完成后复盘
