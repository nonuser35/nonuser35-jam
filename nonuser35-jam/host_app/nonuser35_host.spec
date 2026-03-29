# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules


ROOT = Path.cwd()
HOST_APP_DIR = ROOT / "host_app"
ICON_FILE = HOST_APP_DIR / "app_icon.ico"

hiddenimports = []
hiddenimports += collect_submodules("flask")
hiddenimports += collect_submodules("flask_cors")
hiddenimports += collect_submodules("googleapiclient")
hiddenimports += collect_submodules("spotipy")
hiddenimports += collect_submodules("ytmusicapi")
hiddenimports += collect_submodules("wikipedia")
hiddenimports += collect_submodules("bs4")
hiddenimports += collect_submodules("deep_translator")
hiddenimports += collect_submodules("selenium")
hiddenimports += collect_submodules("webdriver_manager")
hiddenimports += collect_submodules("playwright")

datas = [
]

if (ROOT / "projeto").exists():
    datas.append((str(ROOT / "projeto"), "projeto"))
if (ROOT / "host_app" / "app_icon.png").exists():
    datas.append((str(ROOT / "host_app" / "app_icon.png"), "host_app"))
if (ROOT / "host_app" / "app_icon.ico").exists():
    datas.append((str(ROOT / "host_app" / "app_icon.ico"), "host_app"))


a = Analysis(
    [str(HOST_APP_DIR / "launcher.py")],
    pathex=[str(ROOT), str(ROOT / "projeto")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "matplotlib",
        "spacy",
        "onnxruntime",
        "tensorflow",
        "tensorboard",
        "sympy",
        "pandas",
        "sklearn",
        "scipy",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NONUSER35 JAM",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON_FILE) if ICON_FILE.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="NONUSER35 JAM Host",
)
