---
name: ue5-engine-startup-modules
description: UE5引擎启动流程与模块系统深度参考
type: knowledge-doc
created: 2026-04-13
updated: 2026-04-13
source: 多源整合（知乎/CSDN/UE源码）
---

# UE5 引擎启动流程与模块系统

> 快照文档 · 面试+工作双用 · 2026-04-13

---

## 一、主干流程

```cpp
int32 GuardedMain(const TCHAR* CmdLine) {
    FEngineLoop GEngineLoop;
    GEngineLoop.PreInit(CmdLine);  // 第一阶段：预初始化（最复杂）
    GEngineLoop.Init();             // 第二阶段：正式初始化
    while (!IsEngineExitRequested())
        GEngineLoop.Tick();         // 第三阶段：主循环
    GEngineLoop.Exit();             // 第四阶段：退出
}
```

---

## 二、PreInit — 预初始化（最复杂）

```
FEngineLoop::PreInit()
│
├── 1. 命令行参数解析
├── 2. 平台初始化 (FPlatformMisc::PlatformPreInit)
├── 3. 日志系统初始化
├── 4. 文件系统初始化
├── 5. TaskGraph 系统启动
├── 6. 内存分配器初始化 (GMalloc → Binned2)
│
├── 7. ★ 核心模块加载
│   ├── LoadCoreModules()
│   │   ├── "CoreUObject"        ← UObject 系统基础
│   │   ├── "Networking"
│   │   └── "Messaging"
│   │
│   ├── LoadPreInitModules()
│   │   ├── "Engine"             ← 引擎核心
│   │   ├── "Renderer"           ← 渲染器
│   │   ├── "AnimGraphRuntime"   ← 动画
│   │   └── "Slate" / "UMG"     ← UI
│   │
│   └── LoadStartupCoreModules()
│       └── "SlateRHIRenderer" 等
│
├── 8. RHI 初始化（选择 D3D12/Vulkan）
├── 9. Shader 编译系统
├── 10. Asset Registry
├── 11. 插件系统加载（遍历 .uplugin）
│
├── 12. ★ LoadStartupModules()
│   └── PreDefault / Default 阶段模块
│       → 每个模块调用 StartupModule()
│
└── 13. GUObjectArray / UObject 系统引导
```

---

## 三、Init — 正式初始化

```
FEngineLoop::Init()
│
├── 1. 创建 GEngine 实例
│   ├── Editor → UUnrealEdEngine
│   ├── Game  → UGameEngine
│   └── Server → UGameEngine (无渲染)
│
├── 2. GEngine->Init()
│   ├── 初始化 GameViewportClient
│   ├── 初始化 GameInstance
│   ├── 创建 LocalPlayer
│   └── 加载默认地图 (LoadMap)
│
├── 3. GEngine->Start()
│   └── GameInstance->StartGameInstance()
│
└── 4. LoadStartupModules() 剩余的 PostDefault 阶段模块
```

---

## 四、Tick — 主循环（每帧）

```
FEngineLoop::Tick()
│
├── 1. 帧计时更新
├── 2. TaskGraph 处理待执行任务
├── 3. FTSTicker::GetCoreTicker().Tick()
│
├── 4. ★ GEngine->Tick()
│   ├── World->Tick()
│   │   ├── Actor::Tick()
│   │   ├── Component::TickComponent()
│   │   ├── Physics Simulation
│   │   └── Timer Manager
│   │
│   ├── NetDriver Tick（网络）
│   └── Slate Tick（UI）
│
├── 5. 渲染帧提交
│   ├── Scene Rendering
│   └── RHI Command Flush
│
├── 6. Present (SwapBuffer)
├── 7. FrameEndSync
└── 8. GC（条件触发）
```

---

## 五、模块加载顺序 ELoadingPhase

```cpp
enum class ELoadingPhase : uint8 {
    EarliestPossible,      // 最早
    PostConfigInit,        // 配置初始化后
    PostSplashScreen,      // 启动画面后
    PreEarlyLoadingScreen,
    PreLoadingScreen,
    PreDefault,            // Default 之前
    Default,               // ★ 默认（大部分模块）
    PostDefault,           // Default 之后
    PostEngineInit,        // 引擎初始化完成后
    None,                  // 不自动加载
};
```

### 加载时间线

```
时间 ───────────────────────────────────────────────►

[Platform Init]
  ├── CoreUObject ───── (UObject 系统)
  ├── Core ───────────── (核心工具)
  ├── Networking ─────── (网络基础)

[RHI Init]
  ├── RenderCore ─────── (渲染核心)
  ├── RHI ────────────── (渲染硬件接口)
  ├── D3D12RHI ───────── (图形 API)

[PreInit Modules]
  ├── SlateCore ──────── (UI 核心)
  ├── Engine ─────────── (引擎核心)
  ├── Renderer ───────── (渲染器)
  ├── AnimGraphRuntime ── (动画)

[Default]  ★ 大部分插件/游戏模块
  ├── 各 Plugin 模块
  ├── 项目 Game 模块

[PostEngineInit]
  └── Editor 相关模块
```

---

## 六、StartupModule / ShutdownModule

### 模块加载链路

```
模块 .dll 被加载
  └── FModuleManager::LoadModule("Name")
        └── 调用模块导出的 InitializeModule()
              └── 创建 IModuleInterface 实例
                    └── IModuleInterface::StartupModule()
                          └── 模块自定义初始化
```

### 示例

```cpp
class FMyGameModule : public IModuleInterface {
public:
    virtual void StartupModule() override {
        // 注册自定义资产类型
        // 注册 Console 命令
        // 初始化第三方 SDK
        // 注册 Slate 样式扩展（Editor 模块）
    }
    
    virtual void ShutdownModule() override {
        // 反注册、清理资源
    }
};

IMPLEMENT_MODULE(FMyGameModule, MyGame)
```

---

## 七、UClass 注册与 CDO 构建时机

```
模块加载 → static 变量自动注册 → 收集到全局数组
  │
  ▼
引擎初始化 → Z_Construct_UClass_XXX()
  │
  ├── 创建 UClass 对象
  ├── 注册 FProperty（属性元数据）
  ├── 注册 UFunction（函数元数据）
  │
  └── 创建 CDO（Class Default Object）
        └── NewObject<T>(GetTransientPackage(), Class)
              └── 走完整的 StaticConstructObject 流程
              └── ⚠️ 调用 T 的构造函数
                    → 构造函数中不应有游戏逻辑
```

**为什么构造函数不应包含游戏逻辑**：
1. CDO 在引擎启动时创建，此时 World 可能不存在
2. CDO 不是实际游戏对象，SpawnActor/访问 World 会崩
3. 游戏逻辑放在 `BeginPlay()` 或 `PostInitProperties()`

---

## 八、Plugin 配置

### .uplugin 文件

```json
{
    "FileVersion": 3,
    "FriendlyName": "My Plugin",
    "Modules": [
        {
            "Name": "MyPlugin",
            "Type": "Runtime",          // Runtime / Editor / Developer
            "LoadingPhase": "Default"   // ★ 控制加载时机
        },
        {
            "Name": "MyPluginEditor",
            "Type": "Editor",
            "LoadingPhase": "PostEngineInit"
        }
    ],
    "Plugins": [
        {
            "Name": "SomeOtherPlugin",
            "Enabled": true              // 模块依赖
        }
    ]
}
```

### Module 依赖（Build.cs）

```csharp
public class MyPlugin : ModuleRules {
    public MyPlugin(ReadOnlyTargetRules Target) : base(Target) {
        PublicDependencyModuleNames.AddRange(new string[] {
            "Core", "CoreUObject", "Engine"  // 公共依赖
        });
        PrivateDependencyModuleNames.AddRange(new string[] {
            "Slate", "SlateCore"             // 私有依赖
        });
    }
}
```

---

## 九、面试要点

### Q: UE5 引擎启动的大致流程？
> "四个阶段：PreInit（最复杂，加载核心模块、初始化 RHI、加载插件、注册 UClass）→ Init（创建 GEngine、加载默认地图）→ Tick（每帧循环：World Tick → 渲染提交 → Present）→ Exit。"

### Q: 模块加载顺序怎么控制？
> ".uplugin 中的 LoadingPhase 字段控制，从 EarliestPossible 到 PostEngineInit 共 9 个阶段。大部分模块在 Default 阶段加载，需要引擎完全初始化后才能用的放 PostEngineInit。"

### Q: 为什么 UObject 构造函数不能有游戏逻辑？
> "因为 CDO 在引擎启动时就通过相同的构造函数创建了。CDO 创建时 World 可能不存在，SpawnActor、访问 GameInstance 等操作会崩。游戏逻辑应放在 BeginPlay 或 PostInitProperties。"

---

## 参考资料

- [UE5引擎运行流程：从main到BeginPlay](https://zhuanlan.zhihu.com/p/577433224)（★ 极佳）
- [设置UE插件的加载时机](https://zhuanlan.zhihu.com/p/459984810)
- UE 源码: `LaunchEngineLoop.cpp`, `ModuleManager.cpp`
