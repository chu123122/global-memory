---
name: ue5-network-replication
description: UE5网络同步Replication体系深度参考
type: knowledge-doc
created: 2026-04-13
updated: 2026-04-13
source: 多源整合（CSDN/知乎/UE文档）
---

# UE5 网络同步 Replication 体系

> 快照文档 · 面试+工作双用 · 2026-04-13

---

## 一、三层网络架构

```
┌──────────────────────────────────────────────┐
│ NetDriver (UNetDriver)                        │
│  ← 网络驱动层：管理所有连接，处理收发包        │
│  ├── UIpNetDriver (UDP)                       │
│  └── UWebSocketNetDriver (WebSocket)          │
│                                               │
│  ┌────────────────────────────────────────┐   │
│  │ NetConnection (UNetConnection)          │   │
│  │  ← 连接层：一个客户端 = 一个 Connection │   │
│  │  ├── 拥有 PlayerController              │   │
│  │  ├── 管理多个 Channel                   │   │
│  │  └── 处理可靠性/排序/分包               │   │
│  │                                         │   │
│  │  ┌──────────────────────────────────┐   │   │
│  │  │ Channel (UChannel)               │   │   │
│  │  │  ← 通道层：每种数据走不同通道     │   │   │
│  │  │  ├── ControlChannel (连接握手)    │   │   │
│  │  │  ├── ActorChannel (Actor 同步)   │   │   │
│  │  │  ├── VoiceChannel (语音)         │   │   │
│  │  │  └── ...                         │   │   │
│  │  └──────────────────────────────────┘   │   │
│  └────────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

---

## 二、Actor Replication 完整流程

### ServerReplicateActors 调用链

```
UNetDriver::TickFlush()                 // 每帧 Tick
  │
  └── UNetDriver::ServerReplicateActors()
        │
        ├── 1. 构建 ConsiderList          // 收集所有需要同步的 Actor
        │     └── bReplicates == true?
        │         + bNetLoadOnClient?
        │         + NetUpdateFrequency?
        │
        ├── 2. 对每个 NetConnection:
        │     ├── 2a. PrioritizeActors()   // 按优先级排序
        │     │     ├── 距离优先级
        │     │     ├── 是否 Owner
        │     │     ├── 上次同步时间
        │     │     └── NetPriority 属性
        │     │
        │     ├── 2b. ProcessPrioritizedActors()
        │     │     ├── 找到/创建 ActorChannel
        │     │     └── UActorChannel::ReplicateActor()
        │     │           ├── 属性同步：比对脏属性 → 序列化差量
        │     │           └── 子对象同步：ReplicatedComponents
        │     │
        │     └── 2c. 带宽限制检查
        │           └── 超出带宽 → 低优先级 Actor 延迟到下帧
```

### 属性同步流程

```
Server 端:
  Actor 属性变化 → 标记 Dirty
  → ServerReplicateActors 时比对 Shadow State
  → 只发送变化的属性（差量序列化）
  → 通过 ActorChannel 发送给 Client

Client 端:
  收到属性数据 → 反序列化 → 设置到本地 Actor
  → 触发 OnRep_XXX() 回调（如果有）
```

---

## 三、属性同步 vs RPC

### 属性同步（UPROPERTY Replicated）

```cpp
// 声明
UPROPERTY(Replicated)
float Health;

UPROPERTY(ReplicatedUsing = OnRep_Health)
float Health;

// 注册
void AMyActor::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(AMyActor, Health);
    // 条件复制：只同步给 Owner
    DOREPLIFETIME_CONDITION(AMyActor, SecretData, COND_OwnerOnly);
}

// OnRep 回调（Client 收到新值后触发）
void AMyActor::OnRep_Health()
{
    UpdateHealthBar();
}
```

### RPC（远程过程调用）

| 类型 | 方向 | 执行位置 | 用途 |
|------|------|---------|------|
| `Server` | Client → Server | 仅 Server | 客户端请求（攻击、移动指令） |
| `Client` | Server → Client | 仅 Owner Client | 服务器通知特定客户端 |
| `NetMulticast` | Server → All | 所有客户端 | 广播（爆炸特效、全局消息） |

```cpp
// Server RPC：客户端调用，服务器执行
UFUNCTION(Server, Reliable)
void ServerFire(FVector Direction);

// Client RPC：服务器调用，客户端执行
UFUNCTION(Client, Unreliable)
void ClientPlayHitEffect(FVector Location);

// Multicast：服务器调用，所有客户端执行
UFUNCTION(NetMulticast, Unreliable)
void MulticastPlayExplosion(FVector Location);
```

### 何时用属性同步 vs RPC

| 场景 | 推荐 | 原因 |
|------|------|------|
| 持续变化的状态（HP、位置） | 属性同步 | 新加入的客户端也能收到最新值 |
| 一次性事件（开枪、爆炸） | RPC | 不需要持久状态 |
| 客户端输入 | Server RPC | 安全：服务器验证 |
| 服务器通知 | Client/Multicast RPC | 时效性强 |

---

## 四、与帧同步项目的对比（面试用）

| 维度 | UE 状态同步 | 你的帧同步项目 |
|------|------------|--------------|
| **核心思想** | 同步**状态**（位置、HP 等） | 同步**输入**（操作指令） |
| **带宽** | 与 Actor 数量成正比 | 与玩家数量成正比（远小于 Actor 数） |
| **确定性** | 不要求（各端算各端的） | **必须确定性**（浮点、随机数、帧率） |
| **回滚** | CharacterMovement 预测回滚 | **你的 v2 实现**：快照+预测回滚 |
| **适用** | MMO、大世界（Actor 多但精度要求低） | 格斗/RTS/MOBA（Actor 少但精度要求高） |
| **延迟感** | 插值平滑（100-200ms 可接受） | 回滚掩盖（<100ms 体验好） |
| **反作弊** | 服务器权威（天然） | 需要额外验证（权威服务器或 Hash 校验） |

**面试话术**：
> "我的帧同步项目用输入同步 + 预测回滚，核心优势是带宽低——只传玩家操作不传世界状态。但代价是必须保证确定性。UE 的状态同步正好反过来——不要求确定性但带宽和 Actor 数量成正比。我的项目中 RUDP 层保证可靠传输，回滚引擎做 snapshot/rollback，这和 UE CharacterMovement 的客户端预测思路类似，都是'先本地执行，收到服务器结果后校正'。"

---

## 五、CharacterMovement 网络预测机制

```
Client                              Server
  │                                    │
  ├── 本地模拟移动 ────────────────────►│── 收到输入 → 执行移动
  │   └── 保存 PendingMove               │   └── 发回权威位置
  │                                    │
  │◄──── 收到权威位置 ─────────────────│
  │   └── 比较本地位置 vs 权威位置       │
  │       ├── 差距 < 阈值 → 接受        │
  │       └── 差距 > 阈值 → 纠正        │
  │           ├── Snap 到权威位置        │
  │           └── 重新模拟所有 Pending   │
  │               Moves（回滚重播）      │
```

---

## 参考资料

- [UE5 Replication详解](https://zhuanlan.zhihu.com/p/578480318)
- [Actor同步调用链源码](https://www.cnblogs.com/chenxuanzuo/p/18647429)
- [UE5 DS服务器与网络同步](https://blog.csdn.net/qq_39108291/article/details/119619482)
- [UNetConnection初始化源码](https://zhuanlan.zhihu.com/p/494674422)
- [UE5网络同步机制详解](https://blog.csdn.net/m0_45371381/article/details/147131022)
