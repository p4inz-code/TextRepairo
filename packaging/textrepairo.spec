# PyInstaller spec: one folder with a windowed app (TextRepairo) and a console CLI (textrepairo).
# Build with: python scripts/build_app.py
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "src"))
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

datas = [(str(ROOT / "src" / "textrepairo" / "web"), "textrepairo/web")]
runtime = ROOT / "packaging" / "runtime"
if runtime.is_dir():
    datas.append((str(runtime), "runtime"))

binaries, hiddenimports = [], ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
                               "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on"]
try:  # the native window is optional (Linux builds open the browser instead)
    wd, wb, wh = collect_all("webview")
    datas += wd
    binaries += wb
    hiddenimports += wh
except Exception:
    pass

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy", "PIL", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

icon = str(ROOT / "packaging" / ("icon.ico" if IS_WIN else "icon.icns" if IS_MAC else "icon.png"))

gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="TextRepairo", console=False, icon=icon,
          upx=False)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="textrepairo-cli", console=True, icon=icon,
          upx=False)

coll = COLLECT(gui, cli, a.binaries, a.datas, name="TextRepairo", upx=False)

if IS_MAC:
    from textrepairo import __version__ as _v  # noqa: E402
    app = BUNDLE(
        coll, name="TextRepairo.app", icon=icon, bundle_identifier="io.github.p4inz-code.textrepairo",
        version=_v,
        info_plist={"CFBundleShortVersionString": _v, "NSHighResolutionCapable": True,
                    "LSApplicationCategoryType": "public.app-category.productivity"},
    )
