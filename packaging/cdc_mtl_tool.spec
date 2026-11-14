# PyInstaller build of the desktop tool: one double-clickable "CDC MTL Tool.exe".
# Build with build_exe.ps1 (it builds the UI first). Bundles the engine, rules/ and the built UI.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "desktop.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "rules"), "rules"),
        (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    ],
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("backend"),
    excludes=["pytest", "tkinter", "httpx"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CDC MTL Tool",
    icon=str(ROOT / "frontend" / "public" / "favicon.ico"),
    console=False,
    upx=False,
    runtime_tmpdir=None,
)
