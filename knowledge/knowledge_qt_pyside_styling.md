---
description: Qt/PySide6 样式系统盲区
priority: medium
status: active
trigger:
  keywords:
    - tool:qt
    - concept:style
    - concept:polish
    - tool:pyside
  tags:
    - ui
    - infra
  stages:
    - implementation
last_updated: 2026-05-20
---

---
name: Qt/PySide6 样式系统盲区
description: Qt QSS（Qt Style Sheet）的优先级、palette() 引用、setProperty 角色样式、setStyleSheet 内联 vs app-wide 等坑 —— PySide6 桌面开发踩过即记
type: knowledge
created: 2026-04-24
updated: 2026-04-24
source: control-panel-v2-pyside 任务实战
---

# Qt/PySide6 样式系统盲区

## 1. setStyleSheet 优先级：内联 > app-wide（最常踩）

**问题**：在 widget 上调 `widget.setStyleSheet(...)` 会**覆盖** `QApplication.setStyleSheet()` 设置的 app-wide QSS，对该 widget（含 child 通过继承）生效。

**踩坑实例**（control-panel-v2-pyside Phase 5+）：
- `views/overview.py` 等用 `QFrame.setStyleSheet("#section-card { background: rgba(255,255,255,0.04); ... }")` 给卡片底色
- 想加「花と嵐」主题时，theme.py 的 `app.setStyleSheet(_hanaarashi_qss())` 里也写了 `QFrame#section-card { background: #f3ede4; }`
- **结果：内联完全覆盖 app QSS，主题切换无效**

**修法**：
- 内联 setStyleSheet 只用于"这个 widget 跟主题无关、永远要这样显示"的情况（如调试输出 dock 的等宽字体）
- 跨主题的样式必须放 app-wide QSS，且 widget 端**只 setObjectName，不 setStyleSheet**
- 8 个 view 的 _section() helper 全部清掉内联样式后主题才生效

## 2. palette() 函数：跨主题颜色引用

QSS 里 `color: palette(mid)` 这种写法是 Qt 专有扩展，会解析为当前 QPalette 的对应 ColorRole。**主题切换时自动跟随，不用每次手改颜色**。

常用 role：
| role | 用途 | 浅色主题典型值 | 深色主题典型值 |
|---|---|---|---|
| `palette(window)` | 窗口背景 | #f0f0f0 | #2c2c2c |
| `palette(text)` | 主文字 | #000 | #fff |
| `palette(mid)` | 次要文字（muted） | 中灰 | 亮灰 |
| `palette(highlight)` | 选中色 | 系统蓝 | 系统蓝 |
| `palette(highlighted-text)` | 选中文字色 | 白 | 白 |
| `palette(alternate-base)` | 表格交替行 / 卡片底 | 浅灰 | 略深灰 |
| `palette(midlight)` | hover / 悬停 | 浅灰白 | 中深灰 |

踩坑实例：原代码用 `color: #cccccc;` 给 muted 文字 → 在 light 主题白底上完全看不见。改 `color: palette(mid);` 跨主题都对。

## 3. setProperty + QSS 选择器：角色化样式

QSS 支持基于 widget property 的选择器：`QPushButton[role="danger"] { ... }`。运行时通过 `widget.setProperty("role", "danger")` 切换，**比 setStyleSheet 更"声明式"**。

**注意**：setProperty 之后样式不会自动重算，必须手动触发重 polish：

```python
widget.setProperty("role", "warning")
widget.style().unpolish(widget)
widget.style().polish(widget)
```

control-panel-v2-pyside `_DecisionView.set_decision()` 用了这个模式给 headline/next 区按 ok/info/warning/error 染色，比维护 `widget.setStyleSheet(...)` 切换字符串清爽。

## 4. qdarktheme（pyqtdarktheme-fork）的 setStyleSheet 行为

`qdarktheme.setup_theme(name)` 内部调 `QApplication.setStyleSheet(<完整一套 QSS>)`。

**陷阱**：随后再调 `app.setStyleSheet(my_qss)` 会**整个替换掉** qdarktheme 的样式 —— 所有 widget 默认样式（ComboBox 下拉、CheckBox、Slider）全没。

**正确做法：append 不 replace**：
```python
qdarktheme.setup_theme("light")
base = app.styleSheet()
app.setStyleSheet(base + my_extra_qss)
```

## 5. qtawesome 字体图标：颜色不会随主题反色

`qta.icon("fa5s.sync")` 在创建时就锁定 palette 当前色（默认黑色）。运行时切主题后，已挂载的图标不会自动重绘。

**正确做法**：自定义 ThemeManager 发 `theme_changed(str)` 信号，订阅方在槽里重建：
```python
@Slot(str)
def _refresh_icons(self, theme):
    for btn, name in self._icon_buttons:
        btn.setIcon(qta.icon(name))
```

或主动指定颜色 `qta.icon("fa5s.sync", color="#dddddd")`。

## 6. QApplication 必须先于 widget 创建

老坑但仍要记：所有 QWidget 都需要 `QApplication` 实例存在才能构造，否则段错误（Windows 下表现为悄悄退出）。在 entry script 顶上：
```python
app = QApplication(sys.argv)
# ... 然后才 import / 构造 widget
```

`pytest` / 单测里跑 widget 测试需要 `QApplication.instance() or QApplication(sys.argv)`。

## 7. QThreadPool 关闭竞态：emit 后 RuntimeError

QRunnable 在 app.quit 后仍可能完成 → 调 `signals.finished.emit(...)` 时 signal source 已被 GC → `RuntimeError: Signal source has been deleted`。

**修法**：emit 包 try/except：
```python
try:
    self._signals.finished.emit(result)
except RuntimeError:
    pass  # 关闭竞态，安全丢弃
```

## 8. QTextEdit 渲染 Markdown

`QTextEdit.setMarkdown(text)`（PySide6 6.x+）原生支持 GFM —— 比拼装 HTML 简单。比 `setPlainText` 体验好 N 个数量级（标题/列表/代码块/表格自动渲染），却很少有人知道。
