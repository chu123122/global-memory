---
description: 系统设计表达方法论
priority: medium
status: active
trigger:
  keywords:
    - concept:style
  tags:
    - ui
    - design
  stages:
    - discussion
    - implementation
last_updated: 2026-05-20
---

---
name: knowledge-system-design
description: 系统设计表达方法论+万能框架+练习记录（面试最大短板改进）
summary: "四步法+万能5步框架已定义；含A攻击B完整数据流标准答案；3道真题标准回答已记录"
type: knowledge
created: 2026-04-01
updated: 2026-04-14
source: 学习 Agent + 面试实战复盘
access_count: 2
---

# 系统设计表达方法论

## 诊断：你的问题

```
你做过的系统之间的架构关系，你说不清楚。
你用过数据驱动，但面试时想不起来。
问题不是"不会"，是"检索不到"——脑子里的知识是散装的，没有框架组织。
```

## 面试万能 5 步框架

### Step 1：确认需求范围（10 秒）
"这个箱庭世界大概有哪些核心玩法？单机还是联网？大概多少个系统需要交互？"
→ **不要上来就答——先问清楚边界**

### Step 2：列出核心系统（30 秒）
按优先级拆：角色系统(3C) → 战斗系统 → AI系统 → 交互系统 → 任务系统 → UI → 存档

### Step 3：确定数据架构（1 分钟）
数据驱动：角色属性/技能参数/AI配置从配置表读取，运行时数据存 Component，持久化通过存档序列化

### Step 4：确定交互方式（1 分钟）— **你最弱的地方**

| 交互类型 | 方式 | 例子 |
|---------|------|------|
| 强依赖（必须调用） | 接口+依赖注入 | 战斗系统依赖 ICharacterService 读取角色属性 |
| 通知类（广播） | 事件系统 | 角色死亡→CharacterDeadEvent→UI/任务/AI 各自订阅 |
| 共享数据（多系统读写） | 黑板/共享数据层 | 玩家位置存 GameState，AI 和 UI 都从中读取 |

### Step 5：举一个具体数据流（1 分钟）

## "A 攻击 B" 完整数据流（米哈游原题标准答案）

```
1. 输入层：玩家按攻击键 → InputSystem → AttackCommand(攻击者ID/方向/时间戳)

2. 战斗系统：CombatSystem 收到 Command → 查武器数据(配置表) → 生成攻击判定区域

3. 碰撞检测：PhysicsSystem 碰撞检测 → 找到目标 B → HitResult(被击者ID/命中部位/命中点)

4. 伤害计算：CombatSystem → 读 A 攻击力 + B 防御力 → 计算最终伤害 → DamageEvent

5. 伤害应用：B.HealthComponent 收到 DamageEvent → 扣血 → 血量≤0 → CharacterDeadEvent

6. 表现层（并行）：
   Animation: A 攻击动画 + B 受击动画
   VFX: 命中特效
   Audio: 打击音效
   Camera: 屏幕震动/顿帧(HitStop)
   UI: 飘伤害数字 + 更新血条

7. 网络同步（联网时）：
   客户端先本地预测 → 发 AttackCommand 到服务器 → 服务器验证+权威计算 → 广播 → 客户端校正
```

数据流图：
```
Input → CombatSystem → PhysicsSystem(碰撞)
     → CombatSystem(伤害计算)
     → HealthComponent(扣血)
     → Event广播 → Animation/VFX/Audio/UI/Camera
     → NetworkSystem(同步)
```

## 你的项目如何对应这个框架

| 项目 | 等价的数据流 | 面试怎么说 |
|------|------------|-----------|
| PBD 项目 | Input→FlowField→空间哈希→碰撞检测→PBD求解→速度更新 | "我的物理管线和战斗数据流本质上是一样的——输入→检测→计算→应用→表现" |
| 帧同步 | Input→本地预测→发送服务器→接收确认→追帧/回滚 | "这是网络系统的交互架构——预测+权威+校正" |
| 天美实习 | 事件系统+ECA+模块依赖拆解 | "大型项目用事件解耦系统——发布/订阅模式" |

## 练习清单（画架构图）

- [ ] PBD 项目系统架构图（哪些 System？数据怎么流动？谁依赖谁？）
- [ ] 帧同步项目系统架构图（网络层/逻辑层/渲染层分离+数据流）
- [ ] 天美项目模块依赖关系图（拆解前 vs 拆解后）
- [ ] "A 攻击 B" 数据流图（用 PBD 项目的碰撞→位置修正场景）

## 常见系统设计题

| 题目 | 来源 | 状态 |
|------|------|:---:|
| 设计箱庭世界系统架构 | 米哈游原题 | 标准答案已记录 ↑ |
| A 攻击 B 的完整数据流 | 米哈游追问 | 标准答案已记录 ↑ |
| Timer Manager | 面试实战 | ✅ 答对了 |
| 多线程插件加载 | 心动二面 | ⚠️ 跑题后被引导回来 |

---
## 更新日志
- 2026-04-01: 初始创建
- 2026-04-14: 大规模更新——合并万能5步框架+A攻击B标准答案+项目对应关系+练习清单
