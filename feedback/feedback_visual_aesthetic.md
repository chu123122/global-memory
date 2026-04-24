---
name: 视觉美学偏好（个人工具/项目通用）
description: 个人偏好的视觉调性、调色板、设计原则。在做任何 UI / 主题 / 文档样式时优先按此调
type: feedback
created: 2026-04-24
updated: 2026-04-24
source: control-panel-v2-pyside 主题定制 + 博客 redesign-astro 同源
---

# 视觉美学偏好

## 核心定位：「花と嵐」日式文学性极简（不是普通日式极简）

**关键差别**：
- 普通日式极简 = **少 = 美**（断舍离、Muji 性冷淡、Apple SF Pro）
- 我的偏好 = **少之中藏多**（村上春树式：表面寡言、内里情感稠密）

设计宣言（来自博客 AI_CONTEXT.md）：「克制但不寡淡，细节暗藏在缝隙里」

## 三件铁律（迁到任何项目都先抓这三件）

### 1. 底色不要纯白
- ❌ `#ffffff` / `#fafafa`（冷白）
- ✅ `#faf8f5`（暖偏黄白，纸质感）
- ✅ `#f9f6f0`（更黄一些）
- 深色场景 ❌ `#000000` / `#101827`（冷黑）
- 深色场景 ✅ `#241e18` / `#2c2418`（暖近黑，warm ink）

### 2. 强调色用降饱和的暖色
- ❌ 蓝（普通的 #0F3D5E navy）/ 绿（#087443）/ 红（#B42318）
- ✅ 克制赤 `#c47b6b`（主强调色）
- ✅ 灰青 `#7b9bb5`（次要 / 信息蓝）
- ✅ 灰绿 `#8baa7d`（成功 / 完成）
- ✅ 赭 `#c8a165`（警示 / 土色）

按钮硬编码色用 hover 系：
- 危险 #B42318 → `#a86b5e`
- 警示 #D97706 → `#b89368`
- 成功 #087443 → `#7d9572`
- 主动作 #0F3D5E → `#6f8ba1`

### 3. 加 1-2 个隐藏式细节
不是每个角落都要塞东西，**奖励停留的人**：
- 状态栏角落的低透明度耳语（如 control-panel-v2-pyside 的 `春の花びらが風に散る`，18% / hover 42%）
- hover 才显的二级文字
- 极慢的元素动画（飘落、淡入）
- 装饰性的竖排日文（`writing-mode: vertical-rl` + 8% 透明度）

**反面教材**：第一眼信息密度高、用色饱和、纯色块对比 —— 显得"产品级"但缺少呼吸。

## 字体偏好

**衬线（标题 / 文学性元素）**：
```css
"Shippori Mincho", "Zen Old Mincho", "Noto Serif SC",
"Source Han Serif SC", "宋体", serif
```

**无衬线（正文）**：
```css
"Noto Sans SC", "Source Han Sans SC", "Microsoft YaHei UI", sans-serif
```

**等宽（终端 / 代码）**：
```css
"Cascadia Mono", "JetBrains Mono", monospace
```

## 调色板速查（control-panel-v2-pyside 实战）

```python
HANAARASHI = {
    "bg_base": "#faf8f5",        # 暖白·纸感
    "bg_card": "#f3ede4",        # 卡片底
    "bg_card_hover": "#ebe2d4",
    "bg_input": "#fffdf9",       # 输入区·更白一点
    "ink_primary": "#2c2418",    # 暖近黑（拒绝 #000）
    "ink_secondary": "#6b5d4f",  # 暖灰
    "ink_muted": "#9a8c7a",      # 灰土
    "accent_aka": "#c47b6b",     # 克制赤·主强调色
    "accent_blue": "#7b9bb5",    # 灰青
    "accent_green": "#8baa7d",   # 灰绿
    "accent_earth": "#c8a165",   # 赭
    "border": "#e0d6c4",
    "border_strong": "#c4b9a6",
}
```

## 参考来源
- 博客：https://github.com/chu123122/blog redesign-astro 分支
- 文学：村上春树、ヨルシカ / n-buna
- 游戏：Hollow Knight 泪城

## 适用场景
- 个人 GUI 工具（control-panel 系列、个人 dashboard）
- 个人博客 / 文档站
- 简历 / portfolio 类产品
- **不适用**：团队协作产品（Slack/Linear 那种高密度信息流）、需要 DevOps 即时警报的工具（红色就该是 #B42318，不能美化）

## 反例提醒
当语义 > 美学时，**功能信号优先**：
- 报错弹窗的"取消"按钮该红就红，不要为了美学换暖色
- 终端的 stderr 流就该黄/红高对比，不能 #c8a165 这种低饱和
- 主控面板的"危险"操作（如 bootstrap reinstall）按钮可以降饱和但不能完全去除色相区分
