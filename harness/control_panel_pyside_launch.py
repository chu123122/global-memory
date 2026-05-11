"""PyInstaller 入口 wrapper（v2.1 R4-a 修复）。

为什么不直接让 PyInstaller 打 control_panel_pyside/__main__.py：
  __main__.py 内部用相对 import（`from .main_window import ...`），
  PyInstaller 单文件模式会把入口脚本当顶级模块加载，包上下文丢失，
  报 `ImportError: attempted relative import with no known parent package`。

此 wrapper 走绝对 import，触发 control_panel_pyside 作为 package 完整加载，
内部相对 import 即可正常解析。
"""
from control_panel_pyside.__main__ import main

raise SystemExit(main())
