# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os

# PyInstaller executes the spec via exec(), so __file__ is not guaranteed.
# build_press_layouts_launcher.py already runs PyInstaller with cwd=ROOT,
# so using the current working directory is the safest project root here.
root = Path.cwd().resolve()
icon_path = r"L:\icon.ico"


a = Analysis(
    [str(root / "press_layouts_launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[],
    hiddenimports=["tkinter", "tkinter.ttk"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="press_layouts_launcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if os.path.exists(icon_path) else None,
)
