# 技术资料链接存档

> 搜索验证日期：2026-04-13
> 用途：UE 引擎源码 + C++ 深度 + 帧同步的高质量参考资料索引
> 每类标注 ★ 的为最佳入口文章

---

## 一、UE5 UObject 反射系统

| # | 资料 | 链接 | 特点 |
|---|------|------|------|
| ★ | UE5 UObject源码分析-类型系统与反射（一） | https://zhuanlan.zhihu.com/p/26340380938 | 系列起点，从 UObjectBase 讲起 |
| | UE5 UObject源码分析-反射（四） | https://zhuanlan.zhihu.com/p/26725639107 | generated.h 详解 |
| | UE5 UObject源码分析-GENERATED_BODY（二） | https://zhuanlan.zhihu.com/p/26347356751 | .gen.cpp 分析 |
| ★ | 【UE 反射】原理与使用（CSDN） | https://blog.csdn.net/hhw_hhw/article/details/139287867 | 极详细，enum/struct/class 三种反射完整源码 |
| | UE5 反射源码分析（博客园） | https://www.cnblogs.com/orance03/p/19031997 | 基于 UE5.5 |
| | UE5反射系统分析generated.h | https://zhuanlan.zhihu.com/p/1917308961947882522 | 2025-06 最新 |
| | UE4 UObject概览及反射系统（腾讯云） | https://cloud.tencent.com/developer/article/2071208 | 腾讯内部分享 |

## 二、UE5 Subsystem 子系统

| # | 资料 | 链接 | 特点 |
|---|------|------|------|
| ★ | UE4/5 Subsystem底层源码分析（知乎） | https://zhuanlan.zhihu.com/p/620143233 | 五种详解+生命周期图 |
| ★ | UE Subsystem详解（CSDN） | https://blog.csdn.net/djlycit/article/details/138213027 | 超长源码级，完整链路 |
| | UE4-SubSystem源码分析 | https://blog.csdn.net/zzZZ20150101/article/details/114837249 | 适合初学 |

## 三、UE5 资源管理 & 异步加载

| # | 资料 | 链接 | 特点 |
|---|------|------|------|
| ★ | UE4 FStreamableManager源码剖析（知乎） | https://zhuanlan.zhihu.com/p/426917233 | 顶级，完整流程图+类图 |
| ★ | UE4 FStreamableManager源码剖析（腾讯云） | https://cloud.tencent.com/developer/article/1897029 | 更完整版，含卸载/GC/引用计数 |
| | 理解游戏中的序列化：从概念到UE5实现 | https://zhuanlan.zhihu.com/p/2756361343 | ImportMap/ExportMap/FLinkerLoad |
| | 虚幻引擎序列化和反序列化原理机制源码解析 | https://zhuanlan.zhihu.com/p/633870177 | 腾讯IEG工程师原创 |
| | 引擎架构剖析——资源加载解析（四） | https://zhuanlan.zhihu.com/p/650150313 | Lyra项目实战 |
| | UE4异步加载流程分析-RequestAsyncLoad | https://zhuanlan.zhihu.com/p/610842673 | 完整链路 |

## 四、UE5 GC 垃圾回收

| # | 资料 | 链接 | 特点 |
|---|------|------|------|
| ★ | 【原创】UE基础—Garbage Collection（知乎） | https://zhuanlan.zhihu.com/p/1897381647193716477 | 最佳GC教程，伪实现→真实现 |
| | UE5垃圾回收GC源码分析 | https://zhuanlan.zhihu.com/p/24323386056 | 2025-02，UE5版本 |
| | 【UE4】垃圾回收源码剖析 | https://zhuanlan.zhihu.com/p/2026408287160088129 | 2天前发布 |
| | UE5 GC系统浏览 | https://www.jianshu.com/p/8891937dab22 | 简洁快速版 |
| | UE5：垃圾回收系统文摘 | https://zhuanlan.zhihu.com/p/690534663 | 精炼总结 |

## 五、UE5 Delegate 代理系统

| # | 资料 | 链接 | 特点 |
|---|------|------|------|
| ★ | 虚幻引擎Delegate委托实现原理与源码分析 | https://zhuanlan.zhihu.com/p/452566044 | 最佳，单播/多播/动态/Payload全覆盖 |
| ★ | UE5 C++委托多播委托（CSDN） | https://blog.csdn.net/qq_40120946/article/details/135402133 | 超详细，含继承关系图+7步流程 |
| | UE5浅析委托原理 | https://blog.csdn.net/qq_52269550/article/details/145559694 | 2025年简洁入门 |

## 六、UE5 多线程 & TaskGraph

| # | 资料 | 链接 | 特点 |
|---|------|------|------|
| ★ | TaskGraph、AsyncTask多线程开发指南（知乎） | https://zhuanlan.zhihu.com/p/463272214 | 渲染线程源码+TaskGraph原理 |
| | UE5 多线程之TaskGraph（知乎） | https://zhuanlan.zhihu.com/p/4993171865 | 三种多线程方式源码 |
| | UE4多线程源码浅析1-FRunnable（CSDN系列） | https://blog.csdn.net/m0_53295313/article/details/134804169 | 系列三篇 |
| | UE4多线程渲染源码详解（CSDN系列3） | https://blog.csdn.net/m0_53295313/article/details/135561101 | 渲染命令入队+执行 |

## 七、UE5 FTimerManager 定时器

| # | 资料 | 链接 | 特点 |
|---|------|------|------|
| ★ | UE4 FTimerManager源码剖析（知乎） | https://zhuanlan.zhihu.com/p/447710527 | **三面原题标准答案** |
| | UE5定时器系统深度解析 | http://set.baidu.com/view/9fda39e9511810a6f524ccbff121dd36a32dc489.html | 含实现细节 |
| | FTimerManager源码阅读 | https://zhuanlan.zhihu.com/p/654379426 | 精炼版 |
| | UE4三种Tick方式详解 | https://zhuanlan.zhihu.com/p/68346320 | Timer/TickFunction/Tickable对比 |

## 八、C++ 内存模型 & 无锁编程

| # | 资料 | 链接 | 特点 |
|---|------|------|------|
| ★ | C++多线程内存模型Memory Order详解（知乎） | https://zhuanlan.zhihu.com/p/27278393419 | 最佳入门 |
| ★ | 从内存模型到无锁编程（腾讯云） | https://cloud.tencent.com/developer/article/2498245 | 极完整，含无锁栈/读写锁/CAS+性能测试 |
| | 深入理解C++11原子操作（华为云） | https://bbs.huaweicloud.com/blogs/455837 | 无锁队列 MSQueue |
| | C/C++11中的lock-free技术 | https://zhuanlan.zhihu.com/p/696975436 | atomic_thread_fence |
| | 从互斥锁到无锁编程的转变 | https://zhuanlan.zhihu.com/p/677231916 | 概览 |
| | 内存乱序与C++内存模型详解 | https://www.huliujia.com/blog/f85f72a3b3e3018ffe9c9d3c15dda0f5db079859/ | CPU 视角 |

## 九、帧同步 & 预测回滚

| # | 资料 | 链接 | 特点 |
|---|------|------|------|
| | 帧同步-预测回滚（知乎） | https://zhuanlan.zhihu.com/p/82900667 | 二进制流还原到View层重建 |
| | Unity3D帧同步详解（知乎） | https://zhuanlan.zhihu.com/p/638433974 | 原理+预测+回滚完整 |
| | 关于帧同步的想法-预测和回退 | https://zhuanlan.zhihu.com/p/657629533 | 含定点数/随机数/物理确定性 |
| | StarCraft Mobile帧同步预测回滚实战 | https://my.oschina.net/emacs_7989147/blog/19392705 | 2026-03 最新 |
| | UE4网络架构深度讨论 | https://imgtec.eetrend.com/blog/2020/100060206.html | UE 视角 |

---

*共 9 大类，48 篇高质量文章。★ 标记为每类最佳入口。*
