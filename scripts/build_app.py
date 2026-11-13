"""Build the standalone app with PyInstaller.

    python scripts/build_app.py            # bundles the CPU (or Metal) llama.cpp engine
    python scripts/build_app.py --no-runtime   # smaller build; the app downloads the engine

Output: dist/TextRepairo (folder) and, on macOS, dist/TextRepairo.app
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def fetch_runtime() -> None:
    """Download the llama.cpp build for this platform into packaging/runtime."""
    from textrepairo import runtime

    key = runtime.platform_key()
    backend = "metal" if key == "macos-arm64" else "cpu"
    if not runtime.asset_names(backend, key):
        print(f"No bundled engine for {key}; the app will download it on first run.")
        return
    dest = ROOT / "packaging" / "runtime"
    if dest.exists():
        shutil.rmtree(dest)
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["TEXTREPAIRO_HOME"] = tmp
        binary = runtime.download_runtime(backend, progress=None)
        src = runtime.backend_dir(backend)
        shutil.copytree(src, dest)
        print(f"Bundled engine: {binary.name} ({backend}) from llama.cpp {runtime.LLAMA_CPP_TAG}")
    os.environ.pop("TEXTREPAIRO_HOME", None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-runtime", action="store_true")
    args = ap.parse_args()
    runtime_dir = ROOT / "packaging" / "runtime"
    if args.no_runtime:
        shutil.rmtree(runtime_dir, ignore_errors=True)
    elif not runtime_dir.exists():
        fetch_runtime()
    for d in ("build", "dist"):
        shutil.rmtree(ROOT / d, ignore_errors=True)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"),
           str(ROOT / "packaging" / "textrepairo.spec")]
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
