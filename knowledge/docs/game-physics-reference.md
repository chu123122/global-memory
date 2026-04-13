# 游戏物理模拟技术参考

> 搜索日期：2026-04-13
> 核心来源：PBD/XPBD 学术论文总结、赛车物理实践指南、JoltPhysics/Bevy XPBD 源码分析
> 用途：面试准备 + 个人项目技术储备

---

## 一、PBD vs XPBD vs 传统力学

| | **传统方法** | **PBD** | **XPBD** |
|---|---|---|---|
| 核心思路 | 力→加速度→速度→位置 | 直接修正位置满足约束 | PBD + 柔度矩阵 |
| 稳定性 | 依赖时间步长 | 无条件稳定 | 无条件稳定 |
| 物理精度 | 高 | 低（迭代次数影响刚度） | 中（解耦了刚度与迭代） |
| 速度 | 慢（需小步长） | 快 | 快 |
| 适用场景 | 科学仿真 | 游戏（布料/软体/流体） | 游戏（刚体/软体/通用） |

### PBD 核心算法（你的项目用的）

```
for each time step:
    1. 预测位置：p* = p + v*dt + g*dt²
    2. 生成碰撞约束
    3. 迭代 N 次：
        for each constraint C:
            Δp = -C(p) / |∇C|² * ∇C    （约束投影）
            p* += Δp * w/(w_total)      （质量加权）
    4. 更新速度：v = (p* - p) / dt
    5. 更新位置：p = p*
```

### XPBD 的关键改进

**PBD 的核心问题**：刚度和迭代次数耦合——迭代越多越"硬"，这不物理。

**XPBD 解决方案**：引入柔度矩阵 α̃ = α/dt²

```
Δλ = -(C + α̃·λ) / (∇C·M⁻¹·∇Cᵀ + α̃)
Δx = M⁻¹·∇Cᵀ·Δλ
```

- α = 0 → 完全刚性
- α > 0 → 柔性（弹簧效果）
- 刚度由 α 控制，与迭代次数解耦

### 你的帧同步项目中的物理 vs PBD

你的 `SimulationWorld.cs` 用的是**简化 PBD**：
- 位置预测 → 碰撞检测 → 位置修正 → 速度更新
- 碰撞响应用了重叠分离 + 弹性碰撞
- **没有约束迭代**（只做一次修正）——对简单场景够用

**面试话术**：
> "我的帧同步物理引擎采用了简化的 PBD 思路——先预测位置，检测碰撞后直接修正重叠并交换动量。因为场景简单（10 个实体左右），单次修正就够用。如果实体量上去或需要关节/堆叠，会改用完整的 PBD 迭代求解或 XPBD。"

---

## 二、碰撞检测体系

### 宽相（Broad Phase）

| 方法 | 复杂度 | 适用 |
|------|--------|------|
| 暴力遍历 | O(n²) | n < 100 |
| 空间哈希 | O(n) 均摊 | 均匀分布场景 |
| BVH（AABB 树） | O(n log n) | 通用，动态场景 |
| Sort & Sweep | O(n log n) | 高帧率、少移动 |

### 窄相（Narrow Phase）

| 方法 | 适用形状 | 特点 |
|------|---------|------|
| 圆/球 vs 圆/球 | 圆形 | 最快，你的项目用的就是这个 |
| AABB vs AABB | 矩形 | 简单高效 |
| SAT（分离轴定理） | 凸多边形 | 通用凸形 |
| GJK + EPA | 任意凸形 | 工业标准（PhysX/Havok/Jolt） |

### Speculative CCD（推测性连续碰撞检测）

传统问题：高速物体穿越薄墙（tunneling）

```
传统 CCD：二分搜索 TOI（撞击时间）→ 精确但昂贵
Speculative CCD：膨胀 AABB = 原 AABB + velocity × dt
                → 提前检测潜在碰撞 → 限制速度不超过距离/dt
```

**优点**：简单、快速、和 PBD 天然兼容
**缺点**：可能限制速度导致"鬼墙"效应

---

## 三、赛车物理（面试重点）

### 核心公式

**Pacejka 魔术公式**（轮胎力学）：
```
F(κ) = D · sin(C · arctan(B·κ - E·(B·κ - arctan(B·κ))))
  B = 刚度系数（初始斜率）
  C = 形状系数（曲线形态）
  D = 峰值（最大摩擦力）
  E = 曲率系数（峰值附近形状）
```

**滑移率**（纵向，加速/制动）：
```
κ = (ω·R - V_x) / max(V_x, ω·R)
```

**侧偏角**（横向，转弯）：
```
α = arctan(V_y / |V_x|)
```

**组合滑移约束**（摩擦力椭圆）：
```
(F_x / F_x_max)² + (F_y / F_y_max)² ≤ 1
```

### 悬挂系统

```
F_suspension = -k_s · x - c_d · ẋ
  k_s: 弹簧刚度 (20,000~80,000 N/m)
  x:   压缩量
  c_d: 阻尼系数（压缩 < 回弹，不对称）
```

游戏中最常用：**射线投射悬挂**
- 从车身向下发射射线
- 射线长度 = 弹簧自然长度 + 最大行程 + 轮半径
- 命中 → 算压缩量 → 算弹簧力 → 施加到车身

### 重量转移（面试常问）

```
纵向：ΔW = (m · a_x · h_cg) / L    （加速→后轮载荷↑，制动→前轮载荷↑）
横向：ΔW = (m · a_y · h_cg) / T    （左转→右侧载荷↑）
```

**面试话术**：
> "赛车物理的核心是轮胎力学。我用 Pacejka 魔术公式建模纵向和横向摩擦力，通过摩擦力椭圆处理组合滑移。悬挂用射线投射+弹簧-阻尼模型。关键的物理现象是重量转移——加速时后轮载荷增加导致更大牵引力，制动时前轮载荷增加所以前轮制动力更有效。整个系统在 240Hz 的固定步长下更新以保证数值稳定。"

### 关键调参范围

| 参数 | 典型值 | 影响 |
|------|--------|------|
| 车辆质量 | 1200~1800 kg | 惯性 |
| 重心高度 | 0.3~0.5 m | 侧倾 |
| 弹簧刚度 | 20k~80k N/m | 悬挂软硬 |
| 峰值滑移率 | 0.06~0.12 | 牵引响应 |
| 峰值侧偏角 | 6°~12° | 转向响应 |
| 空气阻力系数 | 0.25~0.45 | 极速 |
| 物理更新频率 | 120~360 Hz | 数值稳定性 |

---

## 四、物理引擎对比

| 引擎 | 开源 | 刚体 | 软体 | 适用 |
|------|:----:|:----:|:----:|------|
| **PhysX** (Nvidia) | ✅ 5.x | ✅ | ⚠️ | UE 默认，通用 |
| **Havok** | ❌ | ✅ | ✅ | AAA 游戏 |
| **Jolt** | ✅ | ✅ | ✅(XPBD) | 新兴，Horizon 用 |
| **Bullet** | ✅ | ✅ | ✅ | 经典，Blender 用 |
| **Bevy XPBD** | ✅ | ✅ | ✅ | Rust/ECS 生态 |
| **Box2D** | ✅ | ✅(2D) | ❌ | 2D 游戏 |

### Jolt 的软体方案（XPBD）

JoltPhysics 的软体系统采用 XPBD：
- 每个顶点是一个粒子，通过距离约束+体积约束连接
- 碰撞检测：soft vertex vs rigid body
- 用 SoftBodyMotionProperties 管理所有粒子
- 支持多核并行（线程安全的 broad phase）

---

## 五、面试高频题

### Q: PBD 和传统物理引擎有什么区别？
> "传统方法是力→加速度→速度→位置，PBD 跳过力的计算，直接修正位置满足约束。优点是无条件稳定、步长大也不爆炸。缺点是刚度和迭代次数耦合，XPBD 解决了这个问题。"

### Q: 你的物理碰撞检测怎么做的？
> "宽相用暴力遍历因为实体少（<20），窄相用圆形碰撞检测。碰撞响应用 PBD 式的位置修正——先分离重叠，再交换动量。如果要支持复杂形状会改用 GJK+EPA。"

### Q: 赛车物理的关键是什么？
> "轮胎。用 Pacejka 魔术公式建模滑移率→纵向力、侧偏角→横向力，组合滑移用摩擦力椭圆约束。悬挂用射线投射+弹簧阻尼。重量转移是关键物理现象——加速时后轮载荷↑制动时前轮载荷↑。"

### Q: 如何保证物理确定性（帧同步需要）？
> "三点：①固定步长（不用 deltaTime）；②定点数或确保浮点运算顺序一致；③碰撞检测按 EntityId 排序而非内存地址。我的项目用 EntityId 排序解决了跨客户端碰撞顺序不一致的问题。"

---

## 七、Erin Catto GDC 演讲全集（Box2D 之父）

Erin Catto 从 2005 到 2019 年在 GDC 发表了 12 场物理演讲，覆盖了实时物理引擎的完整技术栈：

### 按主题分类

| 主题 | 年份 | 核心内容 | 面试价值 |
|------|:----:|---------|:--------:|
| **Iterative Dynamics** | 2005 | Box2D 理论基础，迭代求解刚体动力学 | ⭐⭐⭐⭐⭐ |
| **Sequential Impulses** | 2006 | Box2D 核心算法——顺序脉冲求解器 | ⭐⭐⭐⭐⭐ |
| **Contact Manifolds** | 2007 | 碰撞接触点/接触面的生成与管理 | ⭐⭐⭐⭐ |
| **Numerical Integration** | 2009 | 欧拉法/Verlet/RK4 等积分方法 | ⭐⭐⭐⭐ |
| **Modeling and Solving Constraints** | 2009 | 约束系统的数学建模与求解 | ⭐⭐⭐⭐⭐ |
| **Computing Distance (GJK)** | 2010 | GJK 算法——凸形状最小距离计算 | ⭐⭐⭐⭐⭐ |
| **Soft Constraints** | 2011 | 弹性/柔性约束（弹簧阻尼） | ⭐⭐⭐ |
| **Ragdolls** | 2012 | 布娃娃物理建模 | ⭐⭐⭐ |
| **Continuous Collision** | 2013 | CCD 连续碰撞检测（防穿透） | ⭐⭐⭐⭐⭐ |
| **Understanding Constraints** | 2014 | 约束系统深入理解 + Matlab 源码 | ⭐⭐⭐⭐ |
| **Numerical Methods** | 2015 | 物理模拟数值方法总论 | ⭐⭐⭐ |
| **Dynamic BVH** | 2019 | 动态包围体层次树（宽相碰撞优化） | ⭐⭐⭐⭐⭐ |

### 学习路径建议

```
入门：Iterative Dynamics (2005) → Sequential Impulses (2006)
碰撞：GJK (2010) → Contact Manifolds (2007) → CCD (2013) → Dynamic BVH (2019)
约束：Modeling Constraints (2009) → Understanding Constraints (2014) → Soft Constraints (2011)
数学：Numerical Integration (2009) → Numerical Methods (2015)
```

### 顺序脉冲法（Sequential Impulses）—— Box2D 核心

```
传统方法：建立大矩阵，一次求解所有约束
    → O(n³)，实时不可行

顺序脉冲法：
    for 每次迭代:
        for 每个约束:
            计算约束违反量
            计算修正脉冲
            应用脉冲到关联的两个刚体
    
    → 每次迭代 O(n)，迭代 k 次 = O(kn)
    → 通常 k=4~8 次就收敛
    → Box2D / PhysX / Havok 都用这个思路
```

**面试话术**：
> "Box2D 的核心是顺序脉冲求解器——不建立大矩阵，而是逐个约束迭代求解。每次迭代 O(n)，4-8 次迭代就收敛。PBD 和顺序脉冲的思想类似——都是迭代修正，区别是 PBD 在位置空间修正，顺序脉冲在速度空间修正。"

### CCD 连续碰撞检测（Erin Catto GDC 2013）

```
问题：高速物体在一帧内穿过薄墙（隧道效应）

离散检测：只检查当前帧位置 → 穿墙
连续检测：检查从上一帧到当前帧的整个运动轨迹 → 找到精确碰撞时刻

Catto 的 CCD 方法：
  1. Time of Impact (TOI)：二分法找精确碰撞时刻
  2. Bilateral Advancement：两个物体同时推进
  3. Conservative Advancement：保守推进直到足够接近

实际应用（Diablo 3）：
  - Domino 自研物理引擎
  - 快速移动的布娃娃和弹射物必须用 CCD
  - 不用 CCD → 角色穿墙、弹射物穿过敌人
```

### Dynamic BVH（Erin Catto GDC 2019，守望先锋案例）

```
守望先锋 BlizzardWorld 地图：~9000 个碰撞体
├── 绿色 AABB：静态（地图环境）
├── 蓝色 AABB：运动学（平台、电梯）
└── 红色 AABB：动态（角色、弹射物）

Dynamic BVH 的优势：
├── O(log n) 查询
├── 增量更新（不需要每帧重建）
├── 自然处理动态物体（旋转/移动）
└── 比 Grid / Sort-and-Sweep 更适合异构场景

Box2D v3 用了这个方案替代了之前的 AABB 树。
```

---

## 八、Fix Your Timestep（Gaffer On Games 经典）

### 和物理的关系

| 方案 | 物理 dt | 问题 |
|------|---------|------|
| 固定 dt | `1/60` 硬编码 | 不同帧率下模拟速度不一致 |
| 可变 dt | `frameTime` | 弹簧爆炸、穿墙、非确定性 |
| **累加器+固定步长** | 固定 `0.01s` | ✅ 完美方案 |

### 最终方案（你的 SimulationWorld 就是这个）

```cpp
double accumulator = 0.0;
const double dt = 1.0 / 30.0;  // 你的 TIME_STEP

while (!quit) {
    double frameTime = min(newTime - currentTime, 0.25);  // 防死亡螺旋
    accumulator += frameTime;
    
    while (accumulator >= dt) {
        previousState = currentState;
        SimulateFrame(currentState, input, dt);  // 你的纯函数模拟
        accumulator -= dt;
    }
    
    double alpha = accumulator / dt;
    renderState = lerp(previousState, currentState, alpha);  // 渲染插值
    render(renderState);
}
```

**你的项目对标**：你的 `GameClockManager.LogicUpdate()` 里的 `accumulator` 模式就是 Fix Your Timestep 的实现。

---

## 九、参考文献索引

### 必读（⭐⭐⭐⭐⭐）

| 资源 | 类型 | 内容 |
|------|------|------|
| Box2D Publications (box2d.org) | GDC 幻灯片 | Erin Catto 12 场 GDC 演讲全集 |
| Fix Your Timestep (Gaffer On Games) | 博客 | 固定时间步长的经典方案 |
| XPBD 论文 (Macklin et al. 2016) | 学术 | XPBD 算法原始论文 |
| Game Physics Engine Development (Millington) | 书籍 | 从零搭建物理引擎 |

### 推荐阅读（⭐⭐⭐⭐）

| 资源 | 类型 | 内容 |
|------|------|------|
| Box2D-Lite 源码 | 代码 | Catto 的教学用简化版（~1000 行） |
| Jolt Physics 源码 | 代码 | 现代 C++ 物理引擎，用了 XPBD |
| Bevy XPBD 源码 | 代码 | Rust 实现的 XPBD，文档极好 |
| Allen Chou "Game Physics Series" | 博客 | 物理引擎实现系列 |
| Real-Time Collision Detection (Ericson) | 书籍 | 碰撞检测圣经 |

---
## 更新日志
- 2026-04-13: 初始创建，整合 PBD/XPBD 学术资料 + 赛车物理工程实践 + 面试话术
- 2026-04-13: 补充 Erin Catto 12 场 GDC 演讲索引、顺序脉冲法/CCD/Dynamic BVH 详解、Fix Your Timestep 完整方案、参考文献索引
