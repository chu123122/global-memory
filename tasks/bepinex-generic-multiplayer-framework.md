# 通用 Unity 单机游戏联机 Mod 框架构想

> 类型：探索/技术预研
> 创建：2026-05-13
> 来源：分析 Krokosha666/cas-unk-krokosha-multiplayer-coop 架构后引申
> Status: discussion

## 1. 背景

分析了给 2D 生存沙盒游戏 "Casualties: Unknown" 做的联机 coop mod (`Krokosha666/cas-unk-krokosha-multiplayer-coop`)，拆出了它的做法后，讨论能否把 **BepInEx + Harmony + Mono 反射** 组合做成一套通用框架，给任意 Unity 单机游戏快速上联机。

## 2. 现有 mod 架构（参考实现）

```
[Casualties: Unknown 单机 Unity 游戏]
          ↓ 运行时注入
         BepInEx（Unity mod 加载器）
          ↓ 加载
    KrokoshaCasualtiesMP.dll（主 mod）
    ├── LiteNetLib.dll          ← UDP 传输
    ├── Steamworks.NET.dll      ← Steam 大厅/Relay
    ├── opus.dll                ← 语音
    └── Harmony （IL 运行时钩子）
         ├── Body_Start_MultiplayerPatch
         ├── LoadGame_MultiplayerPatch
         ├── SaveGame_MultiplayerPatch
         ├── GunScript_Fire_MultiplayerPatch
         └── ...约 30 个 Patch
```

**关键事实**：
- 模型：Client-Server（服务器权威），不做客户端预测
- 同步：NetObjectRegistry + NetBody + 分频更新（SUpdate/SlowUpdate/VerySlowUpdate）
- 传输：LiteNetLib UDP，默认端口 7790
- 匹配：Steamworks Lobby（可绕过，`--ksmulti-nosteam` 走 IP 直连）
- 每个 Patch 都是手写的，针对特定游戏方法的 IL 指令修改

## 3. 核心问题：能不能通用化

### 3.1 能自动化的部分

| 层 | 自动化方案 | 可行性 |
|---|---|---|
| 传输层 | LiteNetLib 封装（连接/断开/序列化） | 100%，纯复用 |
| 大厅/匹配 | Steamworks Lobby + IP 直连双通道 | 100%，纯复用 |
| 字段同步 | Mono 反射遍历 GameObject 上带标记的字段，脏标记 + 序列化广播 | **有条件可行** |
| 对象生命周期 | Hook `GameObject.Instantiate` / `Destroy`，自动注册到 NetObjectRegistry | 中等 |

### 3.2 必须手写的部分

| 层 | 原因 | 例子 |
|---|---|---|
| 事件型交互 | 不能只同步字段——开枪是一个 `Fire()` 方法调用，内部创建子弹 prefab、播放音效，这些不是字段值 | `GunScript.Fire()`、`Keypad.Minigame()` |
| 服务器授权判定 | 什么操作要通过服务器验证、什么本地执行——依赖游戏业务语义 | `serverdeny_lockpick`、`serverdeny_bandage` |
| 引用/嵌套结构 | `Inventory: List<Item>` 里 Item 又引用 Body 对象——序列化引用地址在客户端是野指针 | 需要手写 resolve 逻辑 |
| 物理/AI 归属 | 谁负责跑 PhysX？AI 决策在哪侧？——没通用答案 |

**估比：传输+同步层可复用 80%，每游戏业务层 20% 手写。**

## 4. 分阶段路线

### Phase 1：传输层框架（可直接复用）

把 LiteNetLib + Steamworks + 基础连接/断开/大厅打包成独立 BepInEx 插件：
- `NetworkManager`：startHost / startServer / connectClient / disconnect
- `ServerBrowser` UI（Steam 大厅 + IP 直连）
- 控制台命令注册
- **目标**：这个阶段不碰游戏逻辑，只提供网络能力

### Phase 2：反射同步层（半自动）

- YAML/JSON 配置文件声明同步白名单：
  ```yaml
  sync_classes:
    Body:
      fields: [position, rotation, health, isSleeping]
      frequency: fast  # SUpdate
    Inventory:
      fields: [items, slots]
      frequency: slow  # SlowUpdate
  ```
- 运行时反射 + 脏标记自动收集
- `NetIdentity` 组件：Harmony hook `Instantiate`/`Destroy` 自动注册对象
- Hook `Rigidbody.position` setter → 自动同步 Transform

### Phase 3：事件系统（配置化，但不完全自动化）

- 定义 `[RpcClientToServer]` / `[RpcServerToClient]` 属性标记
- 业务方法用 Harmony 注入发包逻辑
- 仍然需要手写：哪些方法是 RPC、参数如何序列化

## 5. 已知不可解的限制

| 限制 | 原因 | 影响 |
|---|---|---|
| 客户端预测加不进去 | 原游戏没设计 snapshot/恢复机制，IL2CPP 下全字段反射序列化每帧成本无法承受 | 快节奏对战类游戏不可用 |
| 确定性回滚加不进去 | PhysX 不确定 + `Time.deltaTime` 依赖帧率 + `Random` 种子独立 | 只能在开发阶段设计 |
| IL2CPP 兼容 | Mono 反射在 IL2CPP 下受限更严（AOT 剪裁），需要额外处理 | 移动端游戏适配成本高 |
| 对象引用解析 | 反射拿到的引用在另一侧不存在的根本问题——需要设计 ID 映射层 | 涉及嵌套结构的游戏更麻烦 |

## 6. 延迟容忍度

实际经验：100ms 延迟下 2 人合作沙盒游戏基本无感。原因：
- 合作打 AI（不是对抗），100ms 操作延迟不影响体验
- 大部分操作（拾取/建造/移动）不需要帧级精确
- 感知延迟取决于 **操作密度 × 精确度要求**

快节奏对抗游戏不可用——必须原生支持预测。

## 7. 下一步

- [ ] 从 Krokosha666 mod 中提取传输层最小实现，抽成独立 BepInEx 模板插件
- [ ] 验证反射抓取 GameObject 字段的性能（目标：< 1ms / GameObject @ 60fps）
- [ ] 选一个简单 Unity 单机 demo 作为适配实验
- [ ] 评估 IL2CPP 兼容性方案（harmony + il2cpp 兼容补丁）
