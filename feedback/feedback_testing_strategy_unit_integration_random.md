# Feedback: 单元测试、集成测试和随机测试应该怎么写

## 背景

在 XDAdaptivePerformance 热状态查询重构里，讨论到一个问题：当前随机测试看起来跑了很多组合，但实际很少发现问题。这里需要明确一点：随机测试本身不是问题，问题通常出在测试定义、oracle 和覆盖目标上。

随机测试是一种测试方法，不是测试层级。它可以用于单元测试，也可以用于集成测试。是否是集成测试，取决于它有没有接真实边界和真实组件协作，而不是取决于输入是不是随机。

## 对随机测试的判断

CS61B 里提到的随机测试强在“随机操作序列 + 正确参考实现”。也就是说，被测实现和 oracle 是两个不同来源：

- 一个是复杂实现。
- 一个是简单但正确的实现。
- 随机操作同时打到两边。
- 只要结果不一致，就输出 seed 或操作序列，方便复现。

如果随机测试只是把生产逻辑在测试里重写一遍，然后随机喂参数，本质上更像“随机 smoke test”。它能发现明显崩溃、明显分支遗漏，但很难发现设计逻辑本身的问题。

对于热状态 resolver 这类有限状态决策逻辑，随机测试不是第一选择。它的输入空间主要是枚举组合：

- Status 是否可用。
- Status 来源层级。
- Temp 是否可用。
- Temp 来源层级。
- 温度是否合法。
- 阈值是否可用。
- Status 与温度换算状态是否一致。
- 状态差值是否大于等于 2。
- Type 是 Default、Explicit 还是指定温度类型。

这类逻辑更适合先写决策表穷举测试，再用随机测试做补充。

## 单元测试应该怎么写

单元测试应优先验证纯策略和有限状态组合，不依赖真实 SDK、真实 sysfs、真实配置文件。

对热状态查询这类逻辑，单元测试应该覆盖决策表，而不是只测几个样例：

- Status 不可用，Temp 不可用，返回 NotAvailable。
- Status 不可用，Temp 可用，阈值可用，返回温度换算状态。
- Status 不可用，Temp 可用，阈值不可用，返回 NotAvailable。
- Status 可用，同层 Temp 不可用，返回 Status。
- Status 可用，同层 Temp 可用，阈值不可用，返回 Status。
- Status 可用，同层 Temp 可用，状态一致，返回该状态。
- Status 可用，同层 Temp 可用，状态差值小于 2，返回 Status。
- Status 可用，同层 Temp 可用，状态差值大于等于 2，返回温度换算状态。
- Status 可用，异层 Temp 可用，不做跨层可信度校验，返回 Status。

Provider 契约测试要断言调用路径，而不只是最终状态：

- Qualcomm Status 可用，Vendor Temp 不可用，Android Temp 可用时，不应该查 Android Temp。
- Qualcomm Status 不可用，Vendor Temp 不可用，Android Temp 可用时，可以 fallback Android Temp。
- MediaTek 要有和 Qualcomm 对称的测试。
- Android Status 和 Android Temp 同属 OS 层，可以做可信度校验。
- Apple 只有 OS Status，没有 Temp 时，应返回 Status。

单元测试里如果保留随机测试，应该改成模型测试：

- 随机生成完整场景。
- 用独立 spec model 计算 expected。
- 不直接复刻生产实现。
- 失败时输出 seed、Type、Status/Temp 是否可用、Layer、温度值、阈值、expected path、actual path。

## 集成测试应该怎么写

集成测试不应该承担所有逻辑组合穷举。它应该验证真实边界是否接通，以及模块之间的协作是否符合预期。

对 XDAdaptivePerformance 热状态链路，集成测试更适合覆盖：

- BPLibrary 到 Monitor 到统一 resolver 的真实调用链。
- DeviceProfiler.ini 阈值是否被真实读取和消费。
- DeviceList.ini / 动态策略开关是否影响实际路径。
- ThermalTrace 日志是否输出正确字段。
- dataLayer、requiredLayer、source、read、status 是否能反映真实路径。
- vendor fallback 到 OS 的路径是否在日志和结果上都符合预期。

集成测试可以用 mock provider 或测试 provider，但应该尽量接真实配置读取和真实模块入口。真机测试再覆盖真实 SDK、真实 sysfs、真实 ROM 权限、真实厂商返回值。

## 实践原则

- 有限状态决策逻辑：先写决策表单元测试。
- Provider 行为：写契约测试，断言调用路径和副作用。
- 随机测试：只在有独立 oracle 或复杂状态序列时使用。
- 集成测试：验证真实边界和真实链路，不做全组合穷举。
- E2E / 真机测试：少量关键机型定期跑，验证真实设备差异，不替代单元测试。

## 对当前 XDAP 测试的结论

当前随机测试有一定 smoke 价值，但不是主要正确性保障。它之前没能发现硬件 Status 被 OS Temp 校验的问题，核心原因是：

- 随机输入没有充分覆盖来源层级组合。
- 测试只看最终状态，没断言调用路径。
- expected 逻辑和生产逻辑过于接近。
- 没有独立 spec model。

后续优化方向应该是：

- 用决策表补齐 resolver 单元测试。
- 用 ProviderPolicy 补齐 Qualcomm / MediaTek / Android / Apple 的路径断言。
- 集成测试补 ThermalTrace 字段断言。
- 随机测试保留，但改成带 seed 和独立模型的 property-based 测试。

