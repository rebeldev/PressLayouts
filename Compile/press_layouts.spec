# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = []
for package_name in ("PIL", "psycopg", "psycopg2"):
    try:
        hiddenimports += collect_submodules(package_name)
    except Exception:
        pass
hiddenimports += [
    "win32print",
    "win32ui",
    "win32con",
    "win32gui",
    "pythoncom",
    "pywintypes",
]
hiddenimports += ["tkinterdnd2"]

# PDF manifest parsing
for package_name in ("fitz", "pymupdf"):
    try:
        hiddenimports += collect_submodules(package_name)
    except Exception:
        hiddenimports.append(package_name)

icon_path = r"L:\icon.ico"

a = Analysis(
    ["..\press_layouts.py"],
    pathex=[],
    binaries=[],
    datas=collect_data_files("tkinterdnd2"),
    hiddenimports=hiddenimports,
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
    name="press_layouts",
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
    icon=icon_path if __import__('os').path.exists(icon_path) else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="press_layouts",
)
