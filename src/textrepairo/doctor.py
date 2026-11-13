# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Built-in Doctor: checks that everything TextRepairo needs is in place.

Used by Settings -> Doctor in the app and by `textrepairo doctor`. The text report it produces
contains no user text, and home-folder paths are replaced so it is safe to paste into a bug report.
"""

from __future__ import annotations

import json
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Callable

from . import APP_NAME, __version__
from . import history, packs
from . import models as models_mod
from .config import (data_dir, data_mode, load_settings, portable_state, settings_path, updates_dir)
from .hardware import Hardware, detect
from .runtime import choose_backend, find_runtime, installed_backends, platform_key

OK, WARN, FAIL, INFO = "ok", "warn", "fail", "info"


def _row(cid: str, label: str, status: str, detail: str, fix: str | None = None) -> dict:
    return {"id": cid, "label": label, "status": status, "detail": detail, "fix": fix}


def _llama_version(binary: Path) -> str:
    flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
    try:
        out = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=15,
                             creationflags=flags)
        text = (out.stdout + out.stderr).strip().splitlines()
        return next((ln for ln in reversed(text) if "version" in ln.lower()), text[-1] if text else "")
    except (OSError, subprocess.SubprocessError):
        return ""


def _loopback_only(port: int) -> tuple[bool, str]:
    """The server must answer on 127.0.0.1 but not on this computer's other addresses."""
    try:
        addrs = {a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    except OSError:
        addrs = set()
    for ip in sorted(addrs - {"127.0.0.1"}):
        with socket.socket() as s:
            s.settimeout(1.0)
            if s.connect_ex((ip, port)) == 0:
                return False, f"The local server answers on {ip}. It should only listen on 127.0.0.1."
    return True, "The local server only listens on 127.0.0.1."


def _webview2() -> tuple[str, str]:
    if sys.platform != "win32":
        return INFO, "Not needed on this system."
    try:
        import winreg
        guid = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
        for root, sub in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node" + guid[8:]),
                          (winreg.HKEY_LOCAL_MACHINE, guid), (winreg.HKEY_CURRENT_USER, guid)):
            try:
                with winreg.OpenKey(root, sub) as k:
                    return OK, f"WebView2 runtime {winreg.QueryValueEx(k, 'pv')[0]}"
            except OSError:
                continue
        return WARN, "WebView2 runtime not found. The app will open in your browser instead."
    except ImportError:
        return INFO, "Could not check."


def run_checks(port: int | None = None, engine_running: bool | None = None,
               hw: Hardware | None = None) -> list[dict]:
    """Quick checks (no heavy work). Model hashing and the engine test are separate actions."""
    rows: list[dict] = []
    s = load_settings()
    hw = hw or detect()
    rows.append(_row("version", "App", INFO,
                     f"{APP_NAME} {__version__} on {platform.system()} {platform.release()} "
                     f"({platform_key()}), {'packaged app' if getattr(sys, 'frozen', False) else 'from source'}"))
    d = data_dir()
    try:
        probe = d / ".doctor-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        note = portable_state()[1]
        rows.append(_row("data", "Data folder", WARN if note else OK,
                         f"{d} ({data_mode()} mode)" + (f". {note}" if note else "")))
    except OSError as e:
        rows.append(_row("data", "Data folder", FAIL, f"Cannot write to {d}: {e}"))
    free = shutil.disk_usage(d).free / 1e9
    rows.append(_row("disk", "Free disk space", FAIL if free < 1 else WARN if free < 5 else OK,
                     f"{free:,.1f} GB free where your data lives"))
    rows.append(_row("hardware", "This computer", INFO,
                     f"{hw.ram_gb} GB RAM, {hw.cpu_threads} threads, GPU: "
                     f"{hw.gpu_name or 'none'} ({hw.vram_gb} GB)"))

    backend = choose_backend(s.backend, hw)
    binary = find_runtime(backend) or find_runtime("cpu")
    if binary:
        ver = _llama_version(binary)
        rows.append(_row("runtime", "Text engine (llama.cpp)", OK,
                         f"{binary.parent.name}{'; ' + ver if ver else ''}. Installed: "
                         f"{', '.join(installed_backends()) or 'bundled'}"))
    else:
        rows.append(_row("runtime", "Text engine (llama.cpp)", FAIL,
                         "Not installed. Open Settings to download it.", "runtime"))

    try:
        path, spec = models_mod.resolve_model(s.model_id)
        size = path.stat().st_size
        if spec and size != spec.size:
            rows.append(_row("model", "Language model", WARN,
                             f"{spec.name}: file size differs from the expected size. Run 'Verify model'.",
                             "model"))
        else:
            rows.append(_row("model", "Language model", OK,
                             f"{spec.name if spec else path.name} ({size / 1e9:.2f} GB)"))
    except models_mod.ModelError as e:
        rows.append(_row("model", "Language model", FAIL, str(e), "model"))

    if port:
        ok, msg = _loopback_only(port)
        rows.append(_row("loopback", "Network exposure", OK if ok else FAIL, msg))
    if engine_running is not None:
        rows.append(_row("engine", "Engine process", INFO, "running" if engine_running else "stopped (starts when needed)"))

    try:
        raw = settings_path().read_text(encoding="utf-8") if settings_path().exists() else "{}"
        json.loads(raw)
        rows.append(_row("settings", "Settings file", OK, "Readable."))
    except (OSError, ValueError):
        rows.append(_row("settings", "Settings file", FAIL, "settings.json is damaged.", "reset_settings"))

    try:
        integ = history.integrity()
        rows.append(_row("history", "History", OK if integ == "ok" else FAIL,
                         f"{history.count()} saved result(s), integrity {integ}"
                         + ("" if s.history_enabled else ". History is switched off")
                         + (". Private mode is on" if s.private_mode else ""),
                         None if integ == "ok" else "clear_history"))
    except Exception as e:  # noqa: BLE001
        rows.append(_row("history", "History", FAIL, f"Cannot read history: {e}", "clear_history"))

    loaded = packs.list_packs()
    user_files = list((data_dir() / "packs").glob("*.json"))
    skipped = len(user_files) - sum(1 for p in loaded if p["source"] == "user")
    rows.append(_row("packs", "Slang packs", WARN if skipped else OK,
                     f"{len(loaded)} loaded ({sum(p['entries'] for p in loaded)} entries)"
                     + (f"; {skipped} invalid pack file(s) were skipped" if skipped else "")))

    status, detail = _webview2()
    rows.append(_row("webview2", "Window engine", status, detail))
    rows.append(_row("updates", "Updates", INFO, {
        "automatic": "Automatic: checks GitHub once a day.",
        "notify": "Notify me: checks GitHub once a day.",
        "off": "Off: never contacts the network on its own."}.get(s.update_mode, s.update_mode)))
    cache = sum(f.stat().st_size for f in updates_dir().glob("*") if f.is_file())
    if cache:
        rows.append(_row("cache", "Downloaded updates", INFO, f"{cache / 1e6:.0f} MB kept", "clear_cache"))
    return rows


def verify_model(model_id: str, progress: Callable[[int, int], None] | None = None) -> dict:
    """Hash the model file (real byte progress) and compare with the published SHA-256."""
    import hashlib
    path, spec = models_mod.resolve_model(model_id)
    total = path.stat().st_size
    h = hashlib.sha256()
    done = 0
    with open(path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    digest = h.hexdigest()
    if spec is None:
        return {"ok": True, "known": False, "sha256": digest,
                "message": "Custom model: there is no published checksum to compare with."}
    ok = digest == spec.sha256.lower()
    return {"ok": ok, "known": True, "sha256": digest,
            "message": "The model file matches its published checksum." if ok else
            "The model file does NOT match its published checksum. Download it again."}


def reset_settings() -> None:
    p = settings_path()
    if p.exists():
        p.unlink()


def clear_cache() -> None:
    for f in updates_dir().glob("*"):
        if f.is_file():
            f.unlink()


def report_text(rows: list[dict]) -> str:
    """Plain-text report with no user text and with home/data paths replaced."""
    home = str(Path.home())
    lines = [f"{APP_NAME} {__version__} doctor report"]
    for r in rows:
        detail = str(r["detail"]).replace(str(data_dir()), "<data>").replace(home, "~")
        lines.append(f"[{r['status'].upper():4}] {r['label']}: {detail}")
    return "\n".join(lines)
