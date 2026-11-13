# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""llama.cpp runtime: locate/download the llama-server binary and manage its process.

Reference: https://github.com/ggml-org/llama.cpp (MIT). We run the official prebuilt
`llama-server` as a child process, bound to 127.0.0.1 with a per-launch API key, so
the app never exposes the model to the network.
"""

from __future__ import annotations

import io
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

from .config import Settings, bundled_runtime_dir, runtime_dir
from .errors import AppError
from .hardware import Hardware

# Pinned, tested llama.cpp release. Bump deliberately after testing.
LLAMA_CPP_TAG = "b12360"
RELEASE_URL = "https://github.com/ggml-org/llama.cpp/releases/download/{tag}/{asset}"

BACKENDS = ("cpu", "vulkan", "cuda", "metal")

# SHA-256 of every release asset we download, taken from the GitHub release page for the pinned tag.
# An asset that is not listed here is refused, and a file that does not match is deleted.
ASSET_SHA256: dict[str, str] = {
    "cudart-llama-b12360-bin-ubuntu-cuda-12.8-x64.tar.gz": "be7ec0dba5eac064460b34c02e4010deb14eb8bfba95ae9b508ae4c0a1983b5f",
    "cudart-llama-bin-win-cuda-12.4-x64.zip": "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6",
    "llama-b12360-bin-macos-arm64.tar.gz": "e815561e9621c606388d4538101d56fcf317cdec6ce8f2bbd1bf14f0df29925e",
    "llama-b12360-bin-macos-x64.tar.gz": "ed329ff7f4048dbfbc401909926a6c6f49114fc7cb7860ed9c7976fadcc11a34",
    "llama-b12360-bin-ubuntu-arm64.tar.gz": "a8e2783d74e3e77c4f5e31fbe88e6365c98dffbeb203a1031737121764b62a2a",
    "llama-b12360-bin-ubuntu-cuda-12.8-x64.tar.gz": "1874218dad4a58b5187e01a65de1cdb68218d93a510bca59a976ccb47fafed85",
    "llama-b12360-bin-ubuntu-vulkan-arm64.tar.gz": "e475abf45095ebf3db483c0bfe1a7e258881dee5c1efc8ec767158653bce459c",
    "llama-b12360-bin-ubuntu-vulkan-x64.tar.gz": "2133682fba36e101ec1059ee646287bd1768916d3d0479fa4d6135f40f02e309",
    "llama-b12360-bin-ubuntu-x64.tar.gz": "b60dc211e4ba206bb04bbc9eb06294364c43d0aab8fc308c44a361477466ba4c",
    "llama-b12360-bin-win-cpu-arm64.zip": "269794d34c6d8f5c827f4558442ee28ae07b03a5daf64da8ce112ea477bef4fc",
    "llama-b12360-bin-win-cpu-x64.zip": "eae1726047e0eaa707b1302929d196c999b96c2f243b21aea6e93bcebacc4e17",
    "llama-b12360-bin-win-cuda-12.4-x64.zip": "70c0a244acf39f2f3fd8975a8447884e03fd35f499bf7dc284113845e894c382",
    "llama-b12360-bin-win-vulkan-x64.zip": "42a6f9df608b99c1c83fcaf77284a516e3f167b32a4690f4e4e364c377547055",
}


class RuntimeError_(AppError, RuntimeError):
    pass


def _binary_name() -> str:
    return "llama-server.exe" if sys.platform == "win32" else "llama-server"


def platform_key() -> str:
    machine = platform.machine().lower()
    arm = machine in ("arm64", "aarch64")
    if sys.platform == "win32":
        return "win-arm64" if arm else "win-x64"
    if sys.platform == "darwin":
        return "macos-arm64" if arm else "macos-x64"
    return "linux-arm64" if arm else "linux-x64"


def asset_names(backend: str, key: str | None = None, tag: str = LLAMA_CPP_TAG) -> list[str]:
    """Release asset file names needed for a backend on a platform. Empty = unsupported."""
    key = key or platform_key()
    t = tag
    table: dict[tuple[str, str], list[str]] = {
        ("win-x64", "cpu"): [f"llama-{t}-bin-win-cpu-x64.zip"],
        ("win-x64", "vulkan"): [f"llama-{t}-bin-win-vulkan-x64.zip"],
        ("win-x64", "cuda"): [f"llama-{t}-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip"],
        ("win-arm64", "cpu"): [f"llama-{t}-bin-win-cpu-arm64.zip"],
        ("macos-arm64", "metal"): [f"llama-{t}-bin-macos-arm64.tar.gz"],
        ("macos-arm64", "cpu"): [f"llama-{t}-bin-macos-arm64.tar.gz"],
        ("macos-x64", "cpu"): [f"llama-{t}-bin-macos-x64.tar.gz"],
        ("linux-x64", "cpu"): [f"llama-{t}-bin-ubuntu-x64.tar.gz"],
        ("linux-x64", "vulkan"): [f"llama-{t}-bin-ubuntu-vulkan-x64.tar.gz"],
        ("linux-x64", "cuda"): [f"llama-{t}-bin-ubuntu-cuda-12.8-x64.tar.gz",
                                f"cudart-llama-{t}-bin-ubuntu-cuda-12.8-x64.tar.gz"],
        ("linux-arm64", "cpu"): [f"llama-{t}-bin-ubuntu-arm64.tar.gz"],
        ("linux-arm64", "vulkan"): [f"llama-{t}-bin-ubuntu-vulkan-arm64.tar.gz"],
    }
    return table.get((key, backend), [])


def choose_backend(requested: str, hw: Hardware) -> str:
    """Resolve 'auto' to a concrete backend this machine can use."""
    key = platform_key()
    if requested != "auto":
        return requested if asset_names(requested, key) else "cpu"
    if key.startswith("macos-arm64"):
        return "metal"
    if hw.gpu_vendor in ("nvidia", "amd", "intel") and asset_names("vulkan", key):
        return "vulkan"
    return "cpu"


def backend_dir(backend: str) -> Path:
    return runtime_dir() / f"{LLAMA_CPP_TAG}-{platform_key()}-{backend}"


def _find_binary(root: Path) -> Path | None:
    if not root.exists():
        return None
    for p in root.rglob(_binary_name()):
        if p.is_file():
            return p
    return None


def find_runtime(backend: str) -> Path | None:
    """Path to llama-server for a backend: downloaded copy first, then bundled CPU/Metal."""
    found = _find_binary(backend_dir(backend))
    if found:
        return found
    bundled = bundled_runtime_dir()
    if bundled and backend == ("metal" if platform_key() == "macos-arm64" else "cpu"):
        return _find_binary(bundled)
    return None


def installed_backends() -> list[str]:
    return [b for b in BACKENDS if find_runtime(b)]


def _extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for m in z.infolist():
                target = (dest / m.filename).resolve()
                if not str(target).startswith(str(root)):
                    raise RuntimeError_("Unsafe path in archive.")
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            for m in t.getmembers():
                target = (dest / m.name).resolve()
                if not str(target).startswith(str(root)):
                    raise RuntimeError_("Unsafe path in archive.")
            t.extractall(dest)  # noqa: S202 - members checked above
    binary = _find_binary(dest)
    if binary and sys.platform != "win32":
        for p in binary.parent.iterdir():
            if p.is_file() and (p.suffix in ("", ".so", ".dylib") or ".so." in p.name):
                p.chmod(p.stat().st_mode | 0o755)


def _verify_asset(name: str, archive: Path) -> None:
    """Refuse unknown assets and delete anything whose SHA-256 differs from the pinned value."""
    import hashlib
    expected = ASSET_SHA256.get(name)
    if not expected:
        archive.unlink(missing_ok=True)
        raise RuntimeError_(f"'{name}' is not a known llama.cpp asset for this version, so it was not installed.")
    h = hashlib.sha256()
    with open(archive, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    if h.hexdigest() != expected:
        archive.unlink(missing_ok=True)
        raise RuntimeError_(f"The downloaded engine file '{name}' does not match its published checksum, "
                            "so it was deleted and nothing was installed.")


def download_runtime(
    backend: str,
    progress: Callable[[int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Path:
    """Download and unpack a llama.cpp backend. Blocking; run in a worker thread."""
    names = asset_names(backend)
    if not names:
        raise RuntimeError_(f"Backend '{backend}' is not available on {platform_key()}.")
    existing = find_runtime(backend)
    if existing:
        return existing
    dest = backend_dir(backend)
    with tempfile.TemporaryDirectory() as tmp:
        for name in names:
            url = RELEASE_URL.format(tag=LLAMA_CPP_TAG, asset=name)
            archive = Path(tmp) / name
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "TextRepairo"})
                with urllib.request.urlopen(req, timeout=60) as resp, open(archive, "wb") as out:
                    total = int(resp.headers.get("Content-Length") or 0)
                    done = 0
                    while chunk := resp.read(1024 * 1024):
                        if cancel and cancel():
                            raise RuntimeError_("Download cancelled.")
                        out.write(chunk)
                        done += len(chunk)
                        if progress:
                            progress(done, total)
            except (urllib.error.URLError, OSError) as e:
                shutil.rmtree(dest, ignore_errors=True)
                raise RuntimeError_(f"Runtime download failed (are you online?): {e}") from e
            _verify_asset(name, archive)
            _extract(archive, dest)
    binary = _find_binary(dest)
    if not binary:
        shutil.rmtree(dest, ignore_errors=True)
        raise RuntimeError_("Downloaded runtime does not contain llama-server.")
    return binary


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def default_threads(hw_threads: int) -> int:
    """Use about half the logical cores (max 8) so the machine stays cool and usable."""
    return max(1, min(8, hw_threads // 2))


_job_handle = None


def _die_with_parent() -> None:  # Linux: runs in the child before exec
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").prctl(1, 15)  # PR_SET_PDEATHSIG, SIGTERM
    except Exception:  # noqa: BLE001
        pass


def _kill_on_parent_exit(proc: subprocess.Popen) -> None:
    """Make sure the model server never outlives the app (it holds gigabytes of RAM)."""
    global _job_handle
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                        ("PerJobUserTimeLimit", ctypes.c_longlong), ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD), ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

        class EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        if _job_handle is None:
            k32.CreateJobObjectW.restype = wintypes.HANDLE
            _job_handle = k32.CreateJobObjectW(None, None)
            info = EXTENDED()
            info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            k32.SetInformationJobObject(wintypes.HANDLE(_job_handle), 9, ctypes.byref(info),
                                        ctypes.sizeof(info))
        k32.AssignProcessToJobObject(wintypes.HANDLE(_job_handle), wintypes.HANDLE(int(proc._handle)))  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - best effort only
        pass


@dataclass
class EngineInfo:
    base_url: str
    api_key: str
    backend: str
    model_path: str


class LlamaServer:
    """Owns one llama-server child process."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._info: EngineInfo | None = None
        self._key: tuple | None = None
        self._lock = threading.Lock()
        self._log: list[str] = []

    @property
    def info(self) -> EngineInfo | None:
        return self._info

    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def log_tail(self, n: int = 30) -> str:
        return "\n".join(self._log[-n:])

    def start(self, model_path: Path, backend: str, settings: Settings, hw: Hardware,
              ready_timeout: float = 180.0) -> EngineInfo:
        key = (str(model_path), backend, settings.context_size, settings.threads, settings.gpu_layers)
        with self._lock:
            if self.running() and self._key == key and self._info:
                return self._info
            self._stop_locked()
            binary = find_runtime(backend)
            if binary is None:
                raise RuntimeError_(
                    f"The '{backend}' engine is not installed. Open Settings and install it.")
            port = free_port()
            api_key = secrets.token_urlsafe(24)
            threads = settings.threads or default_threads(hw.cpu_threads)
            cmd = [
                str(binary), "-m", str(model_path),
                "--host", "127.0.0.1", "--port", str(port),
                "--api-key", api_key,
                "-c", str(settings.context_size),
                "-t", str(threads),
                "-np", "1",
                "--no-webui",
                # Small batches make the engine report real "reading your text" progress every
                # 128 tokens. Speed is the same and it keeps CPU bursts short and the PC cooler.
                "-b", "128", "-ub", "128",
            ]
            if backend in ("vulkan", "cuda", "metal"):
                cmd += ["-ngl", "99" if settings.gpu_layers < 0 else str(settings.gpu_layers)]
            else:
                cmd += ["-ngl", "0"]
            kwargs: dict = {}
            if sys.platform == "win32":
                # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS keeps the PC responsive and cool
                kwargs["creationflags"] = 0x08000000 | 0x00004000
            elif sys.platform.startswith("linux"):
                kwargs["preexec_fn"] = _die_with_parent
            self._log = []
            self._proc = subprocess.Popen(
                cmd, cwd=str(binary.parent), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", **kwargs)
            _kill_on_parent_exit(self._proc)
            if sys.platform != "win32":
                try:
                    os.setpriority(os.PRIO_PROCESS, self._proc.pid, 10)
                except (OSError, AttributeError):
                    pass
            threading.Thread(target=self._drain, args=(self._proc,), daemon=True).start()
            base = f"http://127.0.0.1:{port}"
            self._wait_ready(base, api_key, ready_timeout)
            self._info = EngineInfo(base, api_key, backend, str(model_path))
            self._key = key
            return self._info

    def _drain(self, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            self._log.append(line.rstrip())
            if len(self._log) > 400:
                del self._log[:200]

    def _wait_ready(self, base: str, api_key: str, timeout: float) -> None:
        deadline = time.time() + timeout
        headers = {"Authorization": f"Bearer {api_key}"}
        while time.time() < deadline:
            if self._proc is None or self._proc.poll() is not None:
                tail = self.log_tail()
                self._stop_locked()
                raise RuntimeError_("The engine stopped while starting.\n" + tail)
            try:
                r = httpx.get(f"{base}/health", headers=headers, timeout=2.0)
                if r.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.4)
        tail = self.log_tail()
        self._stop_locked()
        raise RuntimeError_("The engine did not become ready in time.\n" + tail)

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def _stop_locked(self) -> None:
        proc, self._proc = self._proc, None
        self._info = None
        self._key = None
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
