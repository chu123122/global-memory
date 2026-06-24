# 【设计文档】XDAdaptivePerformance 插件重构

## 1. 阶段划分

重构分 3 个阶段执行:

| 阶段       | 内容                                            | 目的               | 本期?  |
| -------- | --------------------------------------------- | ---------------- | ---- |
| **阶段 1** | 初始化子线程化 + StartupModule 拆 4 块 + 黑名单 return 恢复 | 解决性能问题 + 让职责独立可测 | ✅    |
| 阶段 2     | 插件架构重构，函数实现重构（如有需要）                           | 解决可维护性           | ❌ 后续 |
| 阶段 3     | 重写测试体系(三层架构 + Spec + Mock)                    | 自动化回归            | ❌ 后续 |

> 注: 这里第一个阶段也尽可能保持良好的风格和测试，但是不做架构和测试大的变动，独立确保每一个阶段都可以跑通没问题。

---

## 2. 阶段 1:初始化子线程化(本期目标)

### 2.1 解决的核心问题

> 当前初始化在 StartupModule 内部一次性触发所有耗时高的 init,
> 没有任何明确的「初始化完成」时点,
> 业务侧只能通过「反复 Query 看返回是不是 NotAvailable」来猜测是否就绪。

衍生症状:

- 启动期主线程被 50-200ms 重 init 阻塞
- 卡顿位置不可预测(取决于哪条 Tick / Query 最先碰到 Monitor 单例)
- MAGT init 失败 vs 设备不支持 vs Keystore 没配 → 业务全部看到 NotAvailable, 无法区分

### 2.2 当前初始化链路

```
[T0  PreDefault] StartupModule()                       【显式】
                 ├─ 设备查询/打日志/诊断
                 ├─ 条件注册 CSV Sampler Ticker
                 ├─ CVar 回调 / Console Command 注册
                 └─ 条件创建 UMG Widget
                     └─ Widget::NativeConstruct()      【UE 回调】
                         └─ UMonitorData::Get() 首次  → UMonitorData 单例初始化

[T1  运行期第1帧] 任意 Query/Tick 先触发                【懒初始化】
                 └─ IPerfMetricsMonitor::GetPerfMetricsMonitor()
                     ├─ QueryDeviceSoCvendor (5+ system property)
                     ├─ TryInitMAGTService() / TryInitQualcommPerfMonitor()
                     │   └─ binder 探测 + Keystore 校验 / dlopen + AIDL connect
                     ├─ new FXxxPerfMonitor()
                     │   └─ 构造内部:再次 init / 缓存初始化 / 文件路径准备
                     └─ LoadConfigFromProjectSettings(Skin_Temp)
                         └─ 读 DeviceProfiler.ini 阈值

[T?  业务调用]    StartThermalMonitoring()             【业务显式】
                 └─ 注册 ThermalCheckDelegate Ticker

[T?  QA 调试]    StartThermalMonitoringTest()          【console 触发】
                 └─ 注册 ThermalZoneLog Ticker(屏幕橙字)

[T?  CSV 开关]   SetCSVLogging 1                       【console 触发】
                 └─ EnsureCSVWriter() + 重新 AddTicker
```

### 2.3 哪些 init 真的耗时

按耗时排序(估算, 实际需真机用 `SCOPE_CYCLE_COUNTER` 实测):

| init                                       | 触发位置                            | 干啥                                      | 估算耗时          |
| ------------------------------------------ | ------------------------------- | --------------------------------------- | ------------- |
| **`TryInitMAGTService`**                   | `PerfMetricesMonitor.cpp:172`   | binder 通信 + Keystore appLicense 校验      | **30-100 ms** |
| **`new FMediaTekPerfMetricsMonitor`**      | `PerfMetricesMonitor.cpp:175`   | 构造内 `init()` + 缓存初始化 + 字段填充             | **20-50 ms**  |
| `QueryDeviceSoCvendor`                     | `PerfMetricesMonitor.cpp:150`   | GPU brand + 5 个 `__system_property_get` | ~10 ms        |
| `LoadConfigFromProjectSettings(Skin_Temp)` | `PerfMetricesMonitor.cpp:195`   | 读 DeviceProfiler.ini 阈值                 | ~5 ms         |
| `LoadStatusFromIniSection`(黑名单)            | `XDAdaptivePerformance.cpp:196` | 读同一 ini 看设备是否拉黑                         | ~2 ms         |
| `EnsureCSVWriter`                          | StartupModule line 234          | new `UCSVWriter` + `AddToRoot`          | <1 ms         |
| `UMonitorData::Get` 首次                     | UMG Widget NativeConstruct      | UObject 单例首次创建                          | <1 ms         |
| `CreateWidget<UAdaptivePerformanceWidget>` | StartupModule line 340          | UMG Widget 实例化 + 子 Widget 链             | ~10 ms        |

`FMediaTekPerfMetricsMonitor` 的`构造`和 `TryInitMAGTService` 性能消耗占大头。

### 2.4 哪些能塞子线程,哪些必须留主线程

**必须留主线程**(UE API 限制):

| 必须主线程的事                                   | 原因                      |
| ----------------------------------------- | ----------------------- |
| `FTicker::AddTicker`                      | UE Ticker 必须主线程注册       |
| `IConsoleManager::RegisterConsoleCommand` | Console 系统主线程           |
| `CreateWidget<UUserWidget>`               | UObject 创建必须 GameThread |
| `LoadObject<>` (找 WBP)                    | 资源加载主线程                 |

**能塞子线程**: SoC 探测 + SDK init + ini 阈值加载(整段 50-200 ms 的那一坨)。

⚠️ **待验证假设**(实施前必须先验):

- MAGT V3 的 binder/JNI 在非 GameThread 上调用是否安全?

- `XDAdaptivePerformance.cpp:213` 有注释「if call GetPerfMetricsMonitor() here will disable MAGTV2 GPU_Services」这里可能存在问题
  
  (已确定，`FMediaTekPerfMetricsMonitor::TryInitMAGTService()` 中会调用 `GRenderingThread->GetThreadID()`, 在子线程内部第一件事不能立刻打 MAGT init，得先等 RHI ready）

如果 MAGT 必须主线程, 退化方案: 子线程只跑 SoC 探测和 ini 加载, SDK init 仍回 GameThread(收益缩小但风险可控)。

### 2.5 改造后链路

```
GameThread:
  ├─[T0  StartupModule 精简 ~30 行]
  │   ├─ DeviceProfileGate.Check                  ~5ms (当前检查黑名单为了测试跳过了)
  │   ├─ AddTicker(CSV) → 内部 if(!IsMonitorReady) skip
  │   ├─ 注册 Console Cmd
  │   ├─ 条件 CreateWidget(UMG)
  │   └─ Async(EAsyncExecution::Thread, InitMonitor)  ← 丢子线程
  │
  ├─[T1  正常游戏逻辑]                          ▲
  │                                              │ 主线程零阻塞
  ├─[T2  第一帧 Tick]                            │
  │   └─ if (!IsMonitorReady) return; ─────────► │ Ticker 空转
  │                                              │
  ├─[T?  收到 OnMonitorReady Broadcast]          │
  │   ├─ Ticker 开始正常工作                       │
  │   └─ 业务侧拿到「SDK 就绪」信号                  │
  │                                              │
  └─[T3  稳态运行]                                │
                                                 │
WorkerThread:                                    │
  └─[T0+延迟  Async 任务启动]                     │
      ├─ QueryDeviceSoCvendor              ~10ms │
      ├─ TryInitMAGTService                ~30-100ms
      ├─ new FMediaTekPerfMetricsMonitor   ~20-50ms
      └─ LoadConfigFromProjectSettings     ~5ms
              │
              ▼
      AsyncTask(GameThread, [&]{
          bMonitorReady = true;            // atomic
          OnMonitorReady.Broadcast();      // 业务订阅
      });
```

**改造收益**: 启动期主线程 0 ms 阻塞 + 卡顿位置可预测 + 业务可订阅就绪事件。

### 2.6 配套必做的 3 件事

> init 放子线程需要一起做的 3 件事情

```
塞子线程  =  最大头(消除主线程阻塞)
        +
        ├─ 改单例为线程安全 (atomic flag / std::call_once)
        │   └─ 不然两条线程同时 GetMonitor 会 new 两次
        │
        ├─ 加 OnMonitorReady 委托 + IsMonitorReady() 查询
        │   └─ 业务有「准备好了」信号可订阅 （目前实现方案没有这种，需要判断一下是否需要添加）
        │
        ├─ 所有 Ticker lambda + BPLib 入口加 IsReady 守护
        │   └─ Ready 之前 Query 返回 NotAvailable, 不去访问 nullptr
```

### 2.7 子线程实现方案

> 这里只列高层结论(选型 / 风险 / 退化 / 灰度), 具体接口、代码骨架、内存序、Shutdown 回收细节见配套 `DESIGN.md`。

#### 方案选型: `Async(EAsyncExecution::Thread)` + `TFuture<FInitContext>`

UE 4.26 子线程 API 对比:

| 方案                                      | 占池子?   | 评价                       |
| --------------------------------------- | ------ | ------------------------ |
| **`Async(EAsyncExecution::Thread)`**    | 否, 独立线程 | ✅ **本期选用**(写法最简, 跑完即销毁) |
| `Async(EAsyncExecution::TaskGraph)`     | 是      | ❌ 30-100ms 占 worker 不合适  |
| `FRunnable` + `FRunnableThread::Create` | 否      | ❌ 杀鸡用牛刀, 启动期一次性任务不需要长生命周期 |
| `FAsyncTask` + `FQueuedThreadPool`      | 是      | ❌ 同 TaskGraph 占池         |

#### 风险

- **启动时机: 必须等 RHI Ready**, `MediaTekPerfMetricesMonitor.cpp:134` 约束
  
  ```cpp
  int32 RHIThreadID = GRHIThreadId != 0 ? GRHIThreadId : GRenderingThread->GetThreadID();
  ```
  
  PreDefault 阶段 `GRHIThreadId == 0` 且 `GRenderingThread` 可能未创建 → 解引用拿无效 ID。**解法**: 子线程通过 `FCoreDelegates::OnPostEngineInit` 钩子推迟启动。
  
   > 现方案靠「懒加载到第一次 Query」——代价是首次 Query 那一帧 30-100ms 卡顿, 且卡顿位置随机(谁先碰到谁中招)
   > 新方案靠「OnPostEngineInit 主动起异步任务」——主线程零阻塞, 业务侧用 OnMonitorReady 委托接收就绪事件

- **回调必须回 GameThread**, `OnMonitorReady.Broadcast()` 蓝图侧期望主线程, 且单例指针赋值不能让业务读到中间状态
    ```cpp
    AsyncTask(ENamedThreads::GameThread, [...]{ /* 写 Monitor + Broadcast */ });
    ```
  
  Monitor 指针 + Ready flag 用 `std::atomic` + acquire/release, 避免读端看到「flag=true 但 Monitor=nullptr」的中间态。

- **Shutdown 时子线程未结束 → 野指针崩**, 场景: 用户秒退 / Editor PIE 停止时, binder 还卡在返回路上, 模块对象已析构
  
  ```cpp
  // 双保险:weak ptr + WaitFor
  InitToken.Reset();                                          // weak 立即失效
  InitFuture.WaitFor(FTimespan::FromMilliseconds(200));       // 兜底等收尾
  ```

#### 退化方案(MAGT 子线程不安全的兜底)

实施前必须真机验证 MAGT V3 binder client stub 在非 GameThread 是否安全。如果不安全按级别退化:

| 级别        | 子线程跑                       | GameThread 跑                           |
| --------- | -------------------------- | -------------------------------------- |
| L1 完整     | SoC + MAGT init + 构造 + ini | 仅装配                                    |
| **L2 退化** | SoC + ini                  | MAGT init + 构造, 但延后到 PostEngineInit 后单帧 |
| L3 完全回滚   | —                          | 全部(`xdperf.UseAsyncInit=0`)            |

L2 至少能消除 PreDefault 阻塞, 把卡顿位置从「随机某帧」收敛到「RHI ready 后第一帧」——可预测。

#### 灰度开关

`CVar xdperf.UseAsyncInit`(`ECVF_ReadOnly`, 启动期决定):

- `1`(默认) = Async 子线程
- `0` = 退回主线程同步初始化(L3 回滚)

### 2.8 StartupModule 函数拆解

> StartupModule 函数是初始化的主要入口，所有 init 逻辑都从这里出发，为了更好理清整个初始化流程，让每个职责变成「可独立创建、可独立测试、可独立替换」的对象，这里也一并重构。

#### 当前 StartupModule 的 7 个职责(line 183-398)

1. 黑名单判断(`FCustomThermalThresholds::LoadStatusFromIniSection`)
2. SDK 选型 + Monitor 单例创建(懒加载, 实际在第一次 Tick/Query 时触发)
3. CSV Sampler 注册(`AddTicker` + lambda)
4. CVar 回调挂接(`SetOnChangedCallback`)
5. Console Command 注册(`SetCSVLogging` / `SetUMGUIVisibility`)
6. UI 初始化(`CreateWidget<UAdaptivePerformanceWidget>` + Slate 死分支)
7. Thermal Debug Reporter(`StartThermalMonitoringTest` 屏幕橙字)

#### 拆出 4 个独立对象

| 拆出对象                    | 接管职责                                | 可独立测试                       |
| ----------------------- | ----------------------------------- | --------------------------- |
| `FDeviceProfileGate`    | 黑名单判断 + 设备识别 + 异步 InitMonitor 任务挂载点 | ✅                           |
| `FCSVSamplerService`    | CSV Ticker + CVar 回调 + IsReady 守护   | ✅(Mock IPerfMetricsMonitor) |
| `FXDPerfConsole`        | 所有 Console Command                  | ✅                           |
| `FThermalDebugReporter` | StartThermalMonitoringTest 浮窗       | —                           |

#### 主函数瘦身后

```cpp
void StartupModule() override {
    DeviceGate = MakeUnique<FDeviceProfileGate>();
    if (!DeviceGate->ShouldEnable()) return;          // 黑名单 return 

    DeviceGate->LaunchAsyncInit();                    // 子线程跑 SDK init

    CSVSampler = MakeUnique<FCSVSamplerService>();    // 内部 Ticker 自带 IsReady 守护
    Console    = MakeUnique<FXDPerfConsole>();
#if !UE_BUILD_SHIPPING
    DebugUI    = MakeUnique<FThermalDebugReporter>();
#endif
    if (bUseUmg) { /* CreateWidget */ }
}
```

主函数从 216 行收敛到 ~30 行, 每个对象有独立头/源文件、独立生命周期、独立可测。

### 2.9 阶段 1 验收标准

| #   | 验收项              | 标准                                                            | 验证方法            |
| --- | ---------------- | ------------------------------------------------------------- | --------------- |
| V1  | 启动期主线程时长         | StartupModule 主线程占用 ≤ 10 ms(不含异步部分)                           | UE Insights 抓启动 |
| V2  | 业务契约             | 5 公开 API + `GetModule()` + `OnThermalStatusChanged` 签名 0 改动   | grep + diff     |
| V3  | 单例线程安全           | 并发 Get 不出现两次 new(`std::atomic<bool>` flag 或 `std::call_once`) | 单元测试或人工压测       |
| V4  | Ready 信号         | `IsMonitorReady()` 准确反映 init 状态; 业务可订阅 `OnMonitorReady`       | 真机走查            |
| V5  | 黑名单 return       | `NotAvailable` 设备 StartupModule 早返回, 不启动子线程 init              | 走查 + 日志         |
| V6  | StartupModule 拆解 | 主函数 ≤ 30 行; 4 个独立类各自 SRP; 每类独立头/源文件                           | 走查              |
| V7  | 行为不回归            | 真机 CSV 列内容/值与重构前一致                                            | diff CSV        |
| V8  | 编译               | Android ARM64 / Win64 编译通过无新增警告                               | CI              |

> 这里测试，在考虑简单先写一下，保证更好的跑通。

### 2.10 风险与回滚

| 风险                                     | 概率  | 影响  | 缓解                                                       |
| -------------------------------------- | --- | --- | -------------------------------------------------------- |
| MAGT init 在子线程上有未知坑                    | 中   | 高   | 真机先验; 失败则退化为「只把 SoC 探测和 ini 加载放子线程, SDK init 留主线程」       |
| 业务首次 Query 落在 Ready 之前, 拿到 NotAvailable | 中   | 中   | 业务侧改为订阅 `OnMonitorReady`; 或临时做「首次 Query 阻塞等 InitFuture」兜底 |
| 单例改造意外破坏 `GetModule()` 行为              | 低   | 中   | 保留静态门面接口, 只动内部实现                                          |

**灰度开关**: `CVar xdperf.UseAsyncInit`(默认 1, 改 0 = 退回主线程同步初始化)
**回滚 tag**: `pre-refactor-stage1-2026-04-XX`

---

## 3. 阶段 2:插件整体大规模架构重构(初步方案，具体等阶段 1 完成后再分析)

### 3.1 阶段定位

> 阶段 1 解决「启动卡顿」和「职责拆分到对象级别」。
> 阶段 2 负责重构整个插件和可能需要修改的具体实现。

### 3.2 阶段 2 工作清单

| 类别              | 项                                                                                     | 动机                                             |
| --------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------- |
| **ABI 隔离**      | Public 头 Pimpl 化(MAGT/QAPE 头从 Public 移到 Private)                                      | 业务侧 include 时被传染第三方 SDK 头, SDK 升级影响下游          |
| **目录重组**        | `Private/Platform/` 子目录(MTK / QC / Apple / Android sysfs 各成文件夹)                       | 当前平台 cpp 平铺, 职责边界模糊                            |
| **校验独立**        | `Private/Validation/` 抽出 `FThermalValidator` + `FDeviceListLoader`                    | 当前复验逻辑裸跑在 MediaTekPerfMetricesMonitor 中, 无法独立测试 |
| **CSV 收敛**      | `Private/CSV/` 3 套写盘合 1 套 + 抽 `CSVPathResolver`                                       | CSVWriter.cpp:91/136/208 三处完整复制                |
| **UI 双体系收敛**    | 删 Slate 死路径(`SPerformanceWidget` 整套 + `bUseSlateUI` 死开关); 9 UMG Widget 重名收敛           | 双体系无意义共存, 命名重复                                  |
| **第二单例去重**      | `UMonitorData` 与 `IPerfMetricsMonitor` 数据完全重叠, UI 改为直接读 Monitor                       | 双缓存一致性问题                                       |
| **拼写改名**        | `Metrices` → `Metrics`(文件 + 类名), 保留 stub 头转发                                          | ABI 影响, 需协调业务侧发版                                |
| **Log 规范**      | 6 个 Category 收敛到 `LogTemp`(Shipping 约束) + 字符串前缀锚点 + emoji 删除                          | 251 处 UE_LOG 跨 6 Category, Shipping 仅支持 LogTemp |
| **接口冗余**        | `IPerfMetricsMonitor` 24 虚函数 + 8 个 `XDAdaptivePerformance::Get*` 静态门面去冗余              | 重复包装, 职责模糊                                      |
| **Build.cs 整理** | Public/Private 依赖分组、加注释、PLATFORM_ANDROID guard 补全                                     | 当前零分组, jni.h 在 Win 编译曾报错                        |
| **P2 顺手清理**     | 死代码(`InitUnitTest` / `TestQuery.h` / `*.uplugin.bak` / QEGA 30 行注释块) + 编码统一(GBK→UTF-8) | 详见现状分析                                         |

---

## 4. 阶段 3:测试体系重写(初步方案，具体等阶段 1 完成后再分析)

### 4.1 现状

- `InitUnitTest()` 零调用 → 死函数
- `StartThermalMonitoringTest()` 是人肉看屏幕的浮窗, 无任何自动断言
- 下游 5+ 系统依赖这份数据, 但**无任何回归测试**

### 4.2 三层测试架构(预案)

| 层            | 验证什么                                                 | 工具                         | 频率      |
| ------------ | ---------------------------------------------------- | -------------------------- | ------- |
| **L1 单元/逻辑** | Mock `IPerfMetricsMonitor` + Spec 跑决策树/复验状态机/CSV 格式  | UE Automation Spec(PC 编辑器) | 每次提交 CI |
| **L2 集成冒烟**  | 真机 Console Command 跑 SDK 接通 / 5 API 返回非 NotAvailable | 真机 + adb                   | 每次出包前   |
| **L3 验收**    | QA 现有流程(APK + obb + 录像 + 看屏幕橙字)                      | 人工                         | 版本验收    |

L3 是当前既有流程, 本次重构不改动; L1/L2 是新增。

---
