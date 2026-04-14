---
name: ue5-rendering-pipeline
description: UE5渲染管线RDG/Deferred Shading全景图
type: knowledge-doc
created: 2026-04-13
updated: 2026-04-13
source: 多源整合（知乎/CSDN/UE源码）
---

# UE5 渲染管线全景图：RDG / Deferred Shading

> 快照文档 · 面试+工作双用 · 2026-04-13

---

## 一、一帧的完整流程

```
FDeferredShadingSceneRenderer::Render()
│
├── 1. InitViews()                    // 可见性计算
│   ├── FrustumCull                   // 视锥体剔除
│   ├── OcclusionCull (HZB)           // 遮挡剔除
│   └── CollectMeshDrawCommands       // 收集渲染命令
│
├── 2. DepthPrePass (EarlyZ)          // 深度预渲染
│
├── 3. RenderBasePass()               // ★ GBuffer 填充
│
├── 4. RenderShadowDepths()           // 阴影深度
│   ├── Cascaded Shadow Maps (CSM)
│   └── Virtual Shadow Maps (VSM)     // UE5新增
│
├── 5. RenderLights()                 // ★ 光照计算
│   ├── DirectLighting (延迟着色)
│   └── Tiled/Clustered Deferred
│
├── 6. RenderDiffuseIndirectAndAO()   // 间接光照
│   ├── Lumen GI                      // UE5 全局光照
│   ├── Lumen Reflections
│   └── SSAO / SSGI
│
├── 7. RenderTranslucency()           // 半透明渲染
│
├── 8. PostProcessing                 // 后处理
│   ├── TSR (Temporal Super Resolution)
│   ├── Bloom / Tonemap / DOF
│   └── MotionBlur / LensFlare
│
└── 9. Present (SwapBuffer)           // 提交最终画面
```

---

## 二、RDG（Render Dependency Graph）

### 核心概念

RDG 是 UE5 渲染管线的**编排框架**，替代了 UE4 的 RHI 命令直接提交。

```cpp
// 基本使用模式
FRDGBuilder GraphBuilder(RHICmdList);

// 1. 创建资源（延迟分配，不立即申请显存）
FRDGTextureRef SceneColor = GraphBuilder.CreateTexture(Desc, TEXT("SceneColor"));

// 2. 添加渲染 Pass
GraphBuilder.AddPass(
    RDG_EVENT_NAME("BasePass"), PassParameters, ERDGPassFlags::Raster,
    [](FRHICommandList& RHICmdList) { /* 渲染代码 */ }
);

// 3. 编译 + 执行
GraphBuilder.Execute();
```

### 三阶段执行

```
Setup Phase（录制）
  → 声明 Pass、注册资源依赖
  
Compile Phase（编译）
  → 计算依赖图、确定资源生命周期
  → 自动插入 barrier/layout transition
  → 剔除未被引用的 Pass
  → 分配 Aliased Memory

Execute Phase（执行）
  → 提交 GPU 命令
```

### RDG 优势

| 特性 | 说明 |
|------|------|
| 自动资源生命周期 | 延迟分配/释放，自动内存别名(Aliasing) |
| 自动屏障 | 自动插入资源状态转换(Layout Transition) |
| Pass 剔除 | 未被引用的 Pass 自动移除 |
| 异步计算 | 标记 `ERDGPassFlags::AsyncCompute` 自动调度 |
| 调试 | `vis RDG` 命令可视化依赖图 |

---

## 三、BasePass — GBuffer 填充

### GBuffer 布局（UE5）

| Buffer | 格式 | 内容 |
|--------|------|------|
| **GBufferA** | RGB10A2 | World Normal (xyz) + PerObjectData (a) |
| **GBufferB** | RGBA8 | Metallic (r) + Specular (g) + Roughness (b) + ShadingModelID (a高4位) |
| **GBufferC** | RGBA8 | BaseColor (rgb) + AO (a) |
| **GBufferD** | RGBA8 | Custom Data（Subsurface Color / Clear Coat 等） |
| **GBufferE** | RGBA8 | Precomputed Shadow Factors |
| **GBufferF** | RGBA8 | World Tangent (xyz) + Anisotropy (a) |
| **SceneDepth** | D32F | 深度缓冲 |
| **Velocity** | RG16F | 运动矢量（TAA/TSR 用） |

### ShadingModel 标识

GBufferB.a 高 4 位存储 ShadingModelID：
```
0=Unlit  1=DefaultLit  2=Subsurface  3=PreintegratedSkin
4=ClearCoat  5=SubsurfaceProfile  6=TwoSidedFoliage
7=Hair  8=Cloth  9=Eye  ...
```

---

## 四、光照计算

### 延迟着色公式（简化）

```hlsl
float3 FinalColor = (Diffuse_BRDF + Specular_BRDF) 
                    × LightColor × Attenuation × Shadow;
```

### UE5 核心光照新特性

**Lumen 全局光照**：
```
Software Ray Tracing (SDF/Mesh Card Tracing)
  → Screen Probe → Irradiance Field → 屏幕空间汇聚

Hardware Ray Tracing（可选）
  → RT Pipeline → Denoise → Composite
```

**Virtual Shadow Maps (VSM)**：
```
传统 CSM → 替换为 → 16K 虚拟阴影贴图
  ├── 基于 Nanite 硬件光栅化
  ├── 按需分页（类似虚拟纹理）
  └── 帧间缓存（增量更新）
```

---

## 五、Nanite 和 Lumen 概述

### Nanite（虚拟化几何体）
- **核心**：GPU 驱动的 LOD 选择 + 软件光栅化
- **原理**：将网格预处理为 Cluster 层级结构，运行时按像素密度选择合适的 Cluster 级别
- **效果**：数十亿多边形实时渲染，无需手动 LOD
- **限制**：不支持骨骼网格、不支持 WPO(World Position Offset)

### Lumen（全局光照）
- **核心**：Software + Hardware 混合光线追踪
- **原理**：SDF(Signed Distance Field) 追踪 + Mesh Card 缓存 + Screen Probe 汇聚
- **效果**：动态全局光照和反射，无需预计算光照贴图
- **性能**：比纯硬件光追便宜，但比传统方案贵

---

## 六、面试标准回答（2 分钟版）

> "UE5 渲染管线是延迟着色架构。一帧大致分这几步：
> 
> 首先是**可见性计算**——视锥体剔除和遮挡剔除确定哪些物体需要渲染。
> 
> 然后是 **BasePass**，把所有不透明物体的材质属性写入 GBuffer——包括法线、BaseColor、金属度粗糙度等，UE5 的 GBuffer 有 6 个 RT。
> 
> 接着是**光照计算**——从 GBuffer 读取材质属性，用 PBR BRDF 计算直接光照。阴影方面 UE5 用了 Virtual Shadow Maps 替代传统级联阴影，基于 Nanite 的硬件光栅化。
> 
> 间接光照由 **Lumen** 处理——用 SDF 追踪和 Screen Probe 实现动态 GI，不需要预烘焙。
> 
> 半透明物体单独渲染（前向着色），最后走**后处理**——TSR 时序超分、Bloom、色调映射等。
> 
> 整个管线由 **RDG（Render Dependency Graph）** 编排，自动管理资源生命周期和 GPU 屏障，比 UE4 的直接 RHI 提交更高效。"

---

## 参考资料

- [UE5渲染管线概览](https://zhuanlan.zhihu.com/p/508372052)
- [RDG Shader参数详解](https://zhuanlan.zhihu.com/p/582018283)
- [UE渲染管线源码剖析](https://blog.csdn.net/kuangben2000/article/details/143464516)
- [UE5 Lumen源码解析](https://zhuanlan.zhihu.com/p/517756126)
- [Nanite技术简介](https://zhuanlan.zhihu.com/p/382687738)
