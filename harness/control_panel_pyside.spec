# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — control_panel_pyside.exe（设计 §8.2）。

构建：cd "$env:GLOBAL_MEMORY_DIR/harness" && pyinstaller control_panel_pyside.spec
产物：dist/control_panel_pyside.exe（onefile，3-5s 冷启）

关键参数：
  --onefile  通过 EXE() 一次性打包；分发友好但启动慢
  console=False  不弹 cmd 窗口
  hiddenimports  qdarktheme / qtawesome 是动态 import，必须显式登记

如启动 > 5s 难忍，把 EXE() 改为目录形态（去掉 onefile=True 等价改写），
冷启回到 < 2s 但产物变成几百个文件。
"""
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['control_panel_pyside_launch.py'],  # v2.1 R4-a：用顶层 wrapper，避免 __main__.py 相对 import 失败
    pathex=['.'],
    binaries=[],
    datas=collect_data_files('qtawesome'),
    hiddenimports=[
        'qdarktheme',
        'qtawesome',
        'darkdetect',
        # v2.1 子包（保险起见显式登记，避免 onefile 漏收集）
        'control_panel_pyside',
        'control_panel_pyside.main_window',
        'control_panel_pyside.theme',
        'control_panel_pyside.cli_invoke',
        'control_panel_pyside.polling',
        'control_panel_pyside.views',
        'control_panel_pyside.views._base',
        'control_panel_pyside.views.components',
        'control_panel_pyside.views.status',
        'control_panel_pyside.views.changelog',
        'control_panel_pyside.views.tasks',
        'control_panel_pyside.widgets',
        'control_panel_pyside.widgets.doc_sidebar',
        'control_panel_pyside.widgets.debug_dock',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'test', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='control_panel_pyside',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # 不弹 console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
