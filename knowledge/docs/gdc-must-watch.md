# 游戏程序员必看 GDC 演讲清单

> 整理日期：2026-04-13
> 说明：🎯 = 面试高频考点 | 🆓 = GDC Vault 免费 | 🇨🇳 = 有中文翻译/解读
> 用途：面试准备 + 技术学习路线 + 入职技术储备
> 
> **中文资源聚合地**：
> - [Zilize/GDC-Index](https://github.com/Zilize/GDC-Index) — GDC 演讲中英文摘要索引（GPT 翻译）
> - [OTFCG/Awesome-Game-Analysis](https://github.com/OTFCG/Awesome-Game-Analysis) — 游戏技术分析资源库
> - B站搜 "GDC 中文字幕" / "青幻译制" 有大量熟肉

---

## 🟢 入门级（建议先看，打基础）

### 1. 引擎架构

| # | 演讲 | 年份 | 演讲者 | 一句话 | 中文资源 | 标注 |
|:-:|------|:----:|--------|--------|----------|:----:|
| 1 | **Overwatch Gameplay Architecture and Netcode** | 2017 | Timothy Ford (Blizzard) | 守望先锋的 ECS 架构 + 确定性网络同步全景，入门 ECS 和网络的最佳第一课 | [知乎中文解读](https://zhuanlan.zhihu.com/p/654096794) / B站"青幻译制"有中字版 | 🎯🆓🇨🇳 |
| 2 | **Data-Oriented Design and C++** (CppCon 2014) | 2014 | Mike Acton (Insomniac) | DOD 理念宣言——为什么你以为的 OOP "最佳实践"在游戏引擎里全是反模式 | [知乎详细笔记](https://zhuanlan.zhihu.com/p/34425262) / [PDF 幻灯片](https://neil3d.github.io/assets/img/ecs/DOD-Cpp.pdf) | 🎯🇨🇳 |
| 3 | **Pitfalls of Object Oriented Programming** | 2009 | Tony Albrecht (Sony) | OOP 在游戏中的性能陷阱，用缓存友好的数据布局替代继承树 | 原版 PDF 广泛流传，知乎/CSDN 有多篇解读 | 🎯🇨🇳 |

### 2. 物理模拟

| # | 演讲 | 年份 | 演讲者 | 一句话 | 中文资源 | 标注 |
|:-:|------|:----:|--------|--------|----------|:----:|
| 4 | **Building a Physics System, Not Just Individual Features** (Zelda: BotW) | 2017 | 堂田卓宏 (Nintendo) | 旷野之息的物理系统设计哲学——构建系统而非堆砌功能，让物理成为玩法基座 | [NGA 中文搬运](https://ngabbs.com/read.php?tid=39867654) | 🎯🆓🇨🇳 |
| 5 | **Math for Game Programmers: Fast and Funky 1D Nonlinear Transformations** | 2015 | Squirrel Eiserloh | 游戏中无处不在的非线性插值曲线（easing/smoothstep/bias/gain），实用数学入门 | [GDC Vault 免费](https://dev.gdcvault.com/play/1022142/) | 🆓 |
| 6 | **Physics for Game Programmers: Continuous Collision** | 2013 | Erin Catto (Box2D 作者) | Box2D 作者讲连续碰撞检测(CCD)原理，GJK/EPA 算法入门 | GDC Vault 有 slides | 🎯 |

### 3. 网络同步

| # | 演讲 | 年份 | 演讲者 | 一句话 | 中文资源 | 标注 |
|:-:|------|:----:|--------|--------|----------|:----:|
| 7 | **1500 Archers on a 28.8: Network Programming in Age of Empires** | 2001 | Mark Terrano, Paul Bettner | 帧同步的开山之作——帝国时代如何在 28.8K 调制解调器上同步 1500 个单位 | 原文 PDF 广泛流传，中文社区多篇解读 | 🎯🇨🇳 |
| 8 | **I Shot You First: Networking the Gameplay of Halo: Reach** | 2011 | David Aldridge (Bungie) | FPS 网络同步圣经——延迟补偿、插值、命中判定、带宽优化的完整方案 | [GDC Vault 免费](https://gdcvault.com/play/1014346/) | 🎯🆓 |

---

## 🟡 进阶级（有基础后深入某个方向）

### 4. 引擎架构 / 多线程

| # | 演讲 | 年份 | 演讲者 | 一句话 | 中文资源 | 标注 |
|:-:|------|:----:|--------|--------|----------|:----:|
| 9 | **Parallelizing the Naughty Dog Engine Using Fibers** | 2015 | Christian Gyrling (Naughty Dog) | 顽皮狗如何用 Fiber + Job System 将《最后生还者》重制版跑到 60fps，多线程引擎的标杆方案 | [知乎详细笔记](https://zhuanlan.zhihu.com/p/36309461) / [原版 PDF](https://media.gdcvault.com/gdc2015/presentations/Gyrling_Christian_Parallelizing_The_Naughty.pdf) | 🎯🆓🇨🇳 |
| 10 | **Destiny's Multithreaded Rendering Architecture** | 2015 | Natalya Tatarchuk (Bungie) | Destiny 的多线程渲染架构，Task Graph + Frame Graph 的早期实践 | CSDN/知乎有解读文章 | 🎯🇨🇳 |
| 11 | **ECS in Practice: Learnings from 'Alan Wake 2'** (Data-Oriented Programming in AAA) | 2024 | Remedy Entertainment | 《心灵杀手2》的 ECS 实战——3A 游戏中 ECS 的真实落地经验，包括踩过的坑 | [机核中文解读](https://www.gcores.com/articles/193257) | 🎯🇨🇳 |

### 5. 渲染技术

| # | 演讲 | 年份 | 演讲者 | 一句话 | 中文资源 | 标注 |
|:-:|------|:----:|--------|--------|----------|:----:|
| 12 | **Moving Frostbite to Physically Based Rendering** | 2014 | Sébastien Lagarde (EA DICE) | 工业级 PBR 管线迁移指南，从理论到美术工作流一条龙，PBR 入门必读 | [知乎 PBR 白皮书系列引用](https://zhuanlan.zhihu.com/p/53086060) / 原版 PDF 广泛流传 | 🎯🇨🇳 |
| 13 | **Rendering 'God of War Ragnarok'** | 2023 | Stephen McAuley (Santa Monica) | 战神诸神黄昏的渲染管线拆解——SSS/GI/大气散射/植被渲染全覆盖 | [CSDN 笔记](https://blog.csdn.net/ccanan/article/details/132250927) | 🇨🇳 |
| 14 | **The Rendering of DOOM (2016)** | 2016 | Tiago Sousa (id Software) | idTech 6 的 Vulkan 渲染管线，Cluster Forward Shading 的经典实现 | [机核中文解读](https://www.gcores.com/articles/180790) / 多篇知乎解读 | 🎯🇨🇳 |
| 15 | **Decima Engine: Advances in Lighting and AA** (Horizon Zero Dawn) | 2017 | Giliam de Carpentier (Guerrilla) | 地平线引擎的光照和 TAA 方案，Decima 引擎的渲染核心公开 | 知乎有多篇解读 | 🇨🇳 |

### 6. 网络同步（进阶）

| # | 演讲 | 年份 | 演讲者 | 一句话 | 中文资源 | 标注 |
|:-:|------|:----:|--------|--------|----------|:----:|
| 16 | **It IS Rocket Science! The Physics of Rocket League** | 2018 | Jared Cone (Psyonix) | 火箭联盟的物理同步方案——客户端预测 + 物理回滚 + 状态校正的完整流程 | GDC Vault | 🎯 |
| 17 | **Networking for Physics Programmers** | 2015 | Glenn Fiedler | 物理同步圣经——状态同步 vs 确定性帧同步的全面对比，快照插值和 delta 压缩 | [作者博客全文](https://gafferongames.com/) 有中文翻译 | 🎯🇨🇳 |
| 18 | **Fight! Rethinking Netcode in Fighting Games** | 2019 | Michael Stallone | 格斗游戏的回滚网络代码(GGPO)详解——预测+回滚的 lockstep 变种 | GDC Vault | 🎯 |

### 7. 性能优化

| # | 演讲 | 年份 | 演讲者 | 一句话 | 中文资源 | 标注 |
|:-:|------|:----:|--------|--------|----------|:----:|
| 19 | **Performance Optimization, SIMD and Cache Friendliness** (Math for Game Programmers) | 多年 | 多位 | GDC 每年一期的数学+优化系列，覆盖 SIMD/缓存/分支预测/内存布局 | GDC Vault 历年合集 | 🎯 |
| 20 | **The Technical Art of Uncharted 4** | 2017 | Naughty Dog Team | 神秘海域4 的技术美术管线——LOD/流式加载/材质系统/地形渲染 | 知乎有翻译 | 🇨🇳 |

---

## 🔴 高级（有经验后看，战略视野 + 前沿技术）

### 8. 引擎架构（高级）

| # | 演讲 | 年份 | 演讲者 | 一句话 | 中文资源 | 标注 |
|:-:|------|:----:|--------|--------|----------|:----:|
| 21 | **Frame Graph: Extensible Rendering Architecture in Frostbite** | 2017 | Yuriy O'Donnell (EA DICE) | 寒霜引擎的 Frame Graph 架构——现代渲染管线资源管理的范式转变 | 知乎/CSDN 多篇深度解读 | 🎯🇨🇳 |
| 22 | **A Deep Dive into Nanite Virtualized Geometry** | 2021 | Brian Karis (Epic) | UE5 Nanite 虚拟化几何的完整技术拆解——GPU 驱动管线 + 虚拟纹理 + 集群剔除 | 知乎有多篇解读 | 🎯🇨🇳 |
| 23 | **Lumen: Real-Time Global Illumination in UE5** | 2022 | Daniel Wright (Epic) | UE5 Lumen 全局光照方案——混合追踪(SDF + Hardware RT) + 无限反弹 | 知乎有多篇解读 | 🎯🇨🇳 |

### 9. 物理模拟（高级）

| # | 演讲 | 年份 | 演讲者 | 一句话 | 中文资源 | 标注 |
|:-:|------|:----:|--------|--------|----------|:----:|
| 24 | **Tunes of the Kingdom: Evolving Physics and Sounds for Zelda: TotK** | 2024 | 堂田卓宏, 高山貴裕, 長田潤也 (Nintendo) | 王国之泪的物理驱动世界——全物理引擎驱动 + "倒转乾坤"物理实现 + 声音物理联动 | [B站中文翻译](https://www.bilibili.com/read/cv33358973) / [微博详细翻译](https://weibo.com/ttarticle/p/show?id=2309405015768474714378) | 🎯🇨🇳 |
| 25 | **Physical Animation in Star Wars Jedi: Fallen Order** | 2020 | Bartlomiej Waszak (Respawn) | UE4 中的物理动画——光剑物理碰撞 + 角色物理响应 + 布料模拟 | [知乎翻译](https://zhuanlan.zhihu.com/p/683010695) | 🇨🇳 |

### 10. 工具链

| # | 演讲 | 年份 | 演讲者 | 一句话 | 中文资源 | 标注 |
|:-:|------|:----:|--------|--------|----------|:----:|
| 26 | **Creating a Tools Pipeline for 'Horizon: Zero Dawn'** | 2017 | Guerrilla Games | 地平线团队的工具链设计——资产管线/编辑器/协作流程/构建系统 | [知乎读后感](https://zhuanlan.zhihu.com/p/354383557) | 🇨🇳 |
| 27 | **Dialogue Systems in Double Fine Adventures** | 2015 | Double Fine | 关卡编辑器和对话系统的工具设计哲学——让策划能自助的工具才是好工具 | GDC Vault | |
| 28 | **GPU-Driven Rendering Pipelines** | 2015 | Sebastian Aaltonen (Ubisoft) | GPU 驱动管线——间接绘制/GPU 剔除/实例化，现代引擎渲染工具链的基石 | 知乎有解读 | 🎯🇨🇳 |

---

## 📋 面试重点速查表

> 按方向标出面试最高频演讲，建议**至少精读这些**：

| 方向 | 首选演讲 | 面试考什么 |
|------|----------|-----------|
| **ECS / DOD** | #1 守望先锋 + #2 Mike Acton DOD | "ECS 是什么？为什么比 OOP 快？" "什么是缓存友好？" |
| **多线程** | #9 顽皮狗 Fiber + #10 Destiny 多线程渲染 | "Job System 怎么设计？" "Task Graph 是什么？" |
| **网络同步** | #7 帝国时代 + #8 Halo Reach + #17 Glenn Fiedler | "帧同步和状态同步的区别？" "怎么做延迟补偿？" |
| **物理** | #4 旷野之息 + #24 王国之泪 + #6 Erin Catto | "物理引擎怎么设计？" "碰撞检测怎么做？" |
| **渲染** | #12 PBR 迁移 + #14 DOOM + #22 Nanite | "PBR 原理？" "Deferred vs Forward？" "GPU 驱动管线？" |
| **性能优化** | #2 DOD + #3 OOP陷阱 + #28 GPU 驱动管线 | "怎么优化缓存命中率？" "Draw Call 怎么减？" |

---

## 🔗 资源导航

| 资源 | 地址 | 说明 |
|------|------|------|
| **GDC Vault** | https://gdcvault.com/ | 官方视频库，部分免费 |
| **GDC-Index (中英文索引)** | https://github.com/Zilize/GDC-Index | GPT 翻译的中英文摘要 |
| **Awesome-Game-Analysis** | https://github.com/OTFCG/Awesome-Game-Analysis | 游戏技术分析大全 |
| **Awesome-Game-Networking** | https://github.com/MongkonEiadon/Awesome-Game-Networking | 网络同步资源汇总 |
| **Glenn Fiedler 博客** | https://gafferongames.com/ | 网络同步必读系列文章 |
| **Real-Time Rendering** | https://www.realtimerendering.com/blog/tag/gdc/ | 每年 GDC 渲染链接汇总 |
| **B站 "青幻译制"** | B站搜索 | 大量 GDC 中文字幕视频 |

---

## 📌 学习路线建议（8 周计划）

```
Week 1-2 (入门基础)
├── #1 守望先锋 ECS + Netcode        ← ECS+网络一箭双雕
├── #2 Mike Acton DOD                ← 建立数据驱动思维
├── #7 1500 Archers 帝国时代          ← 帧同步入门经典
└── #5 Nonlinear Transformations     ← 游戏数学基础

Week 3-4 (进阶核心)
├── #9 顽皮狗 Fiber Job System       ← 多线程引擎架构 ⭐入职任务直接相关
├── #8 Halo Reach 网络               ← FPS 网络同步最佳实践
├── #12 Frostbite PBR                ← 渲染管线入门
└── #17 Glenn Fiedler 物理网络        ← 帧同步 vs 状态同步

Week 5-6 (方向深入)
├── #4 + #24 塞尔达物理双连           ← 物理系统设计哲学
├── #11 心灵杀手2 ECS 实战           ← 3A 级 ECS 落地
├── #21 Frame Graph                  ← 现代渲染架构
└── #14 DOOM 渲染                    ← 高性能渲染管线

Week 7-8 (前沿 + 查漏补缺)
├── #22 Nanite + #23 Lumen           ← UE5 核心技术
├── #10 Destiny 多线程渲染            ← 渲染多线程架构
├── #16 Rocket League 物理同步        ← 物理回滚实战
└── #26 Horizon 工具链               ← 工具管线设计
```

> 💡 **特别提示**：#9 顽皮狗 Fiber Job System 对入职心动引擎中台的多线程资源加载插件任务**直接相关**，建议精读 + 手写一遍 Fiber 调度器。
