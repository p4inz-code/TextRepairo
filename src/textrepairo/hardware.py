"""Detect RAM, CPU and GPU without extra dependencies."""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass


@dataclass
class Hardware:
    os: str
    arch: str
    cpu_threads: int
    ram_gb: float
    gpu_name: str
    gpu_vendor: str  # nvidia | amd | intel | apple | none
    vram_gb: float

    def to_dict(self) -> dict:
        return asdict(self)


def _ram_gb() -> float:
    try:
        if sys.platform == "win32":
            class MEMSTAT(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            st = MEMSTAT()
            st.dwLength = ctypes.sizeof(MEMSTAT)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))  # type: ignore[attr-defined]
            return st.ullTotalPhys / 1024**3
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            return int(out.stdout.strip()) / 1024**3
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024**2
    except Exception:
        pass
    return 0.0


def _run(cmd: list[str], timeout: int = 8) -> str:
    try:
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=flags)
        return out.stdout if out.returncode == 0 else ""
    except Exception:
        return ""


def _gpu() -> tuple[str, str, float]:
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return "Apple Silicon (Metal)", "apple", 0.0
    if shutil.which("nvidia-smi"):
        out = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        if out.strip():
            name, _, mem = out.splitlines()[0].partition(",")
            try:
                return name.strip(), "nvidia", float(mem.strip()) / 1024
            except ValueError:
                return name.strip(), "nvidia", 0.0
    if sys.platform == "win32":
        out = _run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"])
        for name in out.splitlines():
            n = name.strip()
            low = n.lower()
            if not n or "basic" in low or "iddriver" in low or "virtual" in low:
                continue
            if "amd" in low or "radeon" in low:
                return n, "amd", 0.0
            if "intel" in low:
                return n, "intel", 0.0
    elif sys.platform.startswith("linux"):
        out = _run(["lspci"])
        for line in out.splitlines():
            if "VGA" in line or "3D controller" in line:
                low = line.lower()
                name = line.split(":", 2)[-1].strip()
                if "nvidia" in low:
                    return name, "nvidia", 0.0
                if "amd" in low or "radeon" in low:
                    return name, "amd", 0.0
                if "intel" in low:
                    return name, "intel", 0.0
    return "", "none", 0.0


def detect() -> Hardware:
    name, vendor, vram = _gpu()
    return Hardware(
        os=platform.system(),
        arch=platform.machine(),
        cpu_threads=os.cpu_count() or 1,
        ram_gb=round(_ram_gb(), 1),
        gpu_name=name,
        gpu_vendor=vendor,
        vram_gb=round(vram, 1),
    )
