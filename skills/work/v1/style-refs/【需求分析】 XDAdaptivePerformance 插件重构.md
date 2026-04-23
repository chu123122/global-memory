## 目录

## 1. 业务背景

需要一个插件提供手机底层信息，供业务层做画质选择，从而优化玩家游玩体验

## 2. 插件做什么

XDAdaptivePerformance 是一个**纯信息源插件**：从手机底层采集温度/电池/SoC 状态，输出可信的热档位 enum 给业务层，业务层自己决定如何降画质。

```
手机硬件
   │
   ▼
厂商 SDK（MAGT 联发科 / QAPE 高通 / NSProcessInfo Apple / sysfs 默认安卓）
   │  原始数据
   ▼
XDAdaptivePerformance（采集 + 复验 + DeviceList 命中 + CSV 落盘）
   │  EThermalStatus enum + 委托
   ▼
业务层（收到 Critical 自己调 Scalability 降画质）
```

## 2.1 调用时序图

## 3. SDK 调度现状

### 3.1 启动期：SoC 识别 → 厂商 SDK 选型

启动时按 SoC 厂商分流到对应 Monitor 实现，确定调用SDK类型：

```cpp
// PerfMetricesMonitor.cpp:46-129  按 ro property 探 SoC 厂商
ESoCVendor IPerfMetricsMonitor::QueryDeviceSoCvendor()
{
    // 4 次 __system_property_get：
    //   ro.hardware.chipname / ro.soc.manufacturer
    //   ro.board.platform   / ro.hardware
    // → Qualcomm / MediaTek / Samsung / Huawei / NVIDIA / Apple / OtherAndroid
}
```

|                         |                                       |                                        |
| ----------------------- | ------------------------------------- | -------------------------------------- |
| 探测结果                    | Monitor 实现                            | SDK 来源                                 |
| MediaTek                | FMediaTekPerfMetricsMonitor (~1300 行) | MAGT v3.0（AAR + JNI + 4 个 C++ 头）       |
| Qualcomm                | FQualcommPerfMonitor (~1700 行，半废弃)    | QAPE wrapper v1.3（dlopen .so + AIDL）   |
| Apple                   | FApplePerfMonitor (< 100 行)           | NSProcessInfo.thermalState（iOS 系统 API） |
| 其他安卓 / Huawei / Samsung | FAndroidPerfMetricsMonitor 默认         | sysfs /sys/class/thermal/thermal_zone* |

### 3.2 各 SDK 的初始化时机和鉴权

```cpp
// MediaTekPerfMetricesMonitor.cpp:124-176  MAGT 初始化（启动期同步）
SupportedVersion.value = queryServiceVersion(0);                  // binder 探测
const int32 MajorVersion = FMath::Clamp(SupportedVersion.ver.major * 100, 100, 300);
EMTKResult::EResult InitResult = (EMTKResult::EResult)init(
    MajorVersion, AppCode, FrameRate, RHIThreadID,
    &(rawData[0]), rawData.Num());                                // appLicense 校验
// init 失败 → 整个 MAGT 路径返回 -1 → 业务侧拿到 NotAvailable
```

|       |                                                                     |                                  |
| ----- | ------------------------------------------------------------------- | -------------------------------- |
| SDK   | 鉴权方式                                                                | 失败后果                             |
| MAGT  | init(version, code, fps, tid, appLicense, len) 校验 Keystore          | Debug 包不打 Keystore → 联发科设备返回 -1  |
| QAPE  | dlopen("libsnapdragon_services_qape.qti.so") + connectToQapeService | .so 不存在或服务未启 → 全链路返 NotAvailable |
| Apple | 无鉴权，调用 NSProcessInfo.thermalState 即可                                | —                                |
| 默认安卓  | 无鉴权，open sysfs 文件                                                   | 权限不足（中低端 4 年前机型）→ 返 NotAvailable |

**Confluence 揭示的 Keystore 隐患**：MAGT 鉴权与项目 Keystore 绑定，**Debug/Development 包默认不载入 Keystore**，需手动在 Android Studio 配 Signing Configs。该处会存在坑点。

### 3.3 运行期：调用频率严重重复

3 个 Ticker 各自打 SDK，**SDK 实际调用频率远超应用所需**

|                     |      |                                                 |
| ------------------- | ---- | ----------------------------------------------- |
| 调用方                 | 频率   | 调用 SDK 的方法                                      |
| UI Tick（UMG Widget） | 0.2s | QueryThermalStatus / QueryThermalValue × 多 Type |
| CSV Tick（落盘）        | 1s   | QueryAllMetrics 一次拿 14 字段                       |
| 业务直接 Query          | 不定   | QueryThermalStatus(Default)                     |

实际 SDK 被打 ~6 次/秒，**应该 1 次/秒就够**——3 层缓存互相不知道对方刚拉过数据，每次都重新打 binder。

```cpp
// MediaTekPerfMetricesMonitor.cpp:477  binder IPC 拿一次 PerfReport
EMTKResult::EResult Result = (EMTKResult::EResult)getPerfReport(
    &MTKPerfReport, MTKThreadLoads, 0);   // 跨进程调用，1-50 ms
```

### 3.4 平台实现严重不均

|          |       |         |                                                                         |
| -------- | ----- | ------- | ----------------------------------------------------------------------- |
| 平台       | 行数    | 状态      | 备注                                                                      |
| MediaTek | ~1300 | ✅ 真干活   | MAGT 全功能接入                                                              |
| Qualcomm | ~1700 | ⚠️ 半废弃  | QAPE 大段被注释（QualcommPerfMonitor.cpp:917-938 QEGA 30 行注释块），保留壳但不重新激活      |
| Apple    | < 100 | ✅ 设计上极简 | 仅 NSProcessInfo.thermalState，不补 IOKit（业务侧无 iOS 优化需求）                    |
| 默认安卓     | ~700  | ✅ 兜底    | sysfs 关键字匹配（华为 shell_frame/shell_front/shell_back 取最大值，Redmi/OPPO skin） |

### 3.5 调度问题汇总

启动期：

- SoC 识别 4 次 __system_property_get + DeviceList ini 解析 + SDK 鉴权（MAGT Keystore 校验 / QAPE dlopen + connect）**全在 GameThread 同步阻塞**

- MAGT 鉴权失败时业务首次 Query 拿到 NotAvailable，不易区分"设备不支持"还是"Keystore 没配"

运行期：

- 3 层缓存重复打 SDK 6 次/秒

- 单帧 binder IPC 1-50 ms 累加进 GameThread

## 4. 为什么要重构

### 4.1 主线程被吃（P0，影响玩家）

整条采集链跑在 GameThread：

- **调度** FTicker::GetCoreTicker() 必然 GameThread 派发

- **采集** sysfs / JNI 同步阻塞 / Binder IPC 全主线程

- **落盘** CSV 同步写盘在主线程

```cpp
// XDAdaptivePerformance.cpp:236  CSV 落盘 Ticker 注册
CSVWriterTickDelegateHandle = FTicker::GetCoreTicker().AddTicker(
    FTickerDelegate::CreateLambda([this](float DeltaTime) { ... }), interval);

// CSVWriter.cpp:91-92  同步 IO 写盘
Archive = IFileManager::Get().CreateFileWriter(*FilePath, FILEWRITE_Append);
Archive->Seek(...); Archive->Serialize(...); Archive->FlushCache(); Archive->Close();
```

CSV Tick 单帧 3-10 ms（极端 70 ms），吃掉 60fps 帧预算 20-60%。

**注：本次只修复"启动初始化阶段"放子线程**

### 4.2 单例非线程安全（P0）

裸指针 + 无锁惰性初始化 + UMonitorData 单例。跑多线程会出现问题。

```cpp
// PerfMetricesMonitor.cpp:130  全局裸指针 + 无锁判空
static IPerfMetricsMonitor* PerfMetricsMonitor = nullptr;

IPerfMetricsMonitor* IPerfMetricsMonitor::GetPerfMetricsMonitor()
{
    if (PerfMetricsMonitor == nullptr) {            // 并发首调可能 new 两次
        switch (QueryDeviceSoCvendor()) {
            case ESoCVendor::MediaTek:
                PerfMetricsMonitor = new FMediaTekPerfMetricsMonitor();  // 裸 new
                break;
            // ...
        }
    }
    return PerfMetricsMonitor;
}
```

第二个单例：MonitorData.h:93 UMonitorData::Get()，与 IPerfMetricsMonitor 数据完全重叠。

### 4.3 测试缺位（P1）

- QualcommPerfMonitor.cpp:855 InitUnitTest() 函数零调用，是死代码

- XDAdaptivePerformance.cpp:688 StartThermalMonitoringTest() 是人肉看屏幕的浮窗，无任何自动断言

```cpp
// XDAdaptivePerformance.cpp:688  所谓的"测试"——实际是 Debug 浮窗
ThermalCheckDelegateHandle = FTicker::GetCoreTicker().AddTicker(
    FTickerDelegate::CreateLambda([this](float DeltaTime) {
        ThermalStatus = QueryThermalStatus(EThermalType::Default);
        // ... 查 5 种温度
        UE_LOG(LogXDADPF, Log, TEXT("..."));
        GEngine->AddOnScreenDebugMessage(-1, 5.f, FColor::Orange, ...);  // 屏幕橙字
        return true;
    }), Settings->QueryFrequency);
```

### 4.4 架构糟糕（P1）

- **StartupModule 216 行大函数**——XDAdaptivePerformance.cpp:183-398：设备识别 / CSV Sampler / CVar 回调 / Console / UMG / Slate 死代码 / Thermal Debug 全堆一个函数

- **平台实现不均**：MediaTek ~1300 行，Qualcomm 1700 行半废弃（QAPE 大段被注释），Apple 仅 NSProcessInfo.thermalState

- **Public ABI 泄漏第三方 SDK**：业务层 include 时被传染 MAGT/QAPE 头

- **UI 双体系**：UMG + Slate 11 个 Widget（9 UMG + 2 Slate 死代码），命名重复

- **3 层缓存抢资源**：UI Tick 0.2s + CSV Tick 1s + 直接 Query 各自调 SDK，实际 SDK 调用 6 次/秒（应 1 次）

### 4.5 代码不干净（P2）

- 未调用代码（死代码）：
  
  - XDAdaptivePerformance.h:91 bUseSlateUI 死开关
  
  - XDAdaptivePerformance.cpp:381-388 Slate 死分支
  
  - QualcommPerfMonitor.cpp:855 InitUnitTest() 死函数
  
  - TestQuery.h 2 字节空文件 / *.uplugin.bak
  
  - QualcommPerfMonitor.cpp:917-938 QEGA 30 行注释块
  
  - **黑名单** return **被注释**（问题，下面单列）

- 中文注释 GBK/UTF-8 编码混杂

- 函数对重复（CSVWriter.cpp:91/136/208 3 套 CSV 写完整复制）

- Build.cs Public/Private 列表零分组

- PLATFORM_ANDROID guard 缺失（jni.h 在 Win 编译报错）

- 251 个 UE_LOG 跨 6 个 Category（但 Shipping 仅支持 LogTemp）

**黑名单 return 被注释**

```cpp
//XDAdaptivePerformance.cpp:199：
EThermalValidationStatus Status = FCustomThermalThresholds::LoadStatusFromIniSection(*SectionName);
if (Status == EThermalValidationStatus::NotAvailable) {
    UE_LOG(LogXDADPF, Warning, TEXT("device blacklisted, skip"));
    // return;   ⚠️ 被注释 — NotAvailable 设备本应早返回，现在继续跑
}
```

DeviceList 标 NotAvailable 的设备按逻辑应该直接返回，这里return被注释了。

## 5. 重构内容

**初始化放到子线程，把代码理顺，把测试补上**。

|                                     |                                                                              |
| ----------------------------------- | ---------------------------------------------------------------------------- |
| 项                                   | 说明                                                                           |
| 启动初始化挪子线程                           | Async(EAsyncExecution::Thread) + TFuture<FInitResult>                        |
| StartupModule 拆解大函数                 | DeviceProfileGate / CSVSamplerService / XDPerfConsole / ThermalDebugReporter |
| 单例线程安全                              | Meyers Singleton，保留 GetModule() 静态门面                                         |
| UI 收敛                               | 删 Slate 死路径，9 Widget 重名收敛                                                    |
| 未调用代码清理                             | 含黑名单 return 恢复                                                               |
| 拼写 / 编码 / 函数对去重 / Build.cs / Log 规范 | Log 按 Shipping LogTemp 约束统一                                                  |
| 重写测试                                | Mock+ UE Automation Spec（确保逻辑正确） 真机冒烟 console command （确保SDK在真机上可以跑通）        |

## 6. 对外 API

业务侧调用入口分两层：

### 6.1 C++ 接口（XDAdaptivePerformance.h）

```cpp
// XDAdaptivePerformance.h:23-67
class XDADAPTIVEPERFORMANCE_API FXDAdaptivePerformanceModule : public IModuleInterface
{
public:
    static FXDAdaptivePerformanceModule* GetModule();              // line 31

    void StartThermalMonitoring();                                 // line 62
    void StopThermalMonitoring();                                  // line 63

    FOnThermalStatusChanged OnThermalStatusChanged;                // line 67
};

// 委托声明（line 20）
DECLARE_MULTICAST_DELEGATE_OneParam(FOnThermalStatusChanged, EThermalStatus);
```

QueryThermalStatus / QueryThermalValue 在 PerfMetricesMonitor.h:546-550 接口上：

`virtual EThermalStatus QueryThermalStatus(EThermalType Type) = 0; virtual EThermalStatus QueryThermalStatusDataCollection(EThermalType Type) = 0; virtual float          QueryThermalValue(EThermalType Type) = 0;`

### 6.2 蓝图接口（XDAdaptivePerformanceBPLibrary.h）

蓝图侧通过 UXDAdaptivePerformanceBPLibrary 静态函数调用，本质是 C++ 接口的转发：

`// XDAdaptivePerformanceBPLibrary.h:111-144 UFUNCTION(Category = "XDAdaptivePerformance") static EThermalStatus QueryThermalStatus(EThermalType Type = EThermalType::Default);  UFUNCTION(Category = "XDAdaptivePerformance") static EThermalStatus QueryThermalStatusDataCollection(EThermalType Type = EThermalType::Default);  UFUNCTION(BlueprintCallable, Category = "XDAdaptivePerformance|Debug") static void StartThermalMonitoring();c  UFUNCTION(BlueprintCallable, Category = "XDAdaptivePerformance|Debug") static void StopThermalMonitoring();  UFUNCTION(Category = "XDAdaptivePerformance") static float QueryThermalValue(EThermalType Type = EThermalType::Battery_Temp);`

另有 GPU/CPU/Battery Metrics 的 BlueprintPure 函数 ~25 个（line 28-97），用于 UI 监控。
