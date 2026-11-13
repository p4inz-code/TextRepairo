# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Paths and persistent user settings."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_data_dir

from . import APP_NAME

MAX_TEXT_CHARS = 10_000  # hard cap for one repair (client and server both enforce it)
HISTORY_LIMIT = 100  # newest entries kept; older ones are permanently deleted


def _exe_dir() -> Path | None:
    """Folder of the running app when frozen (AppImage: the folder holding the .AppImage)."""
    if not getattr(sys, "frozen", False):
        return None
    appimage = os.environ.get("APPIMAGE")
    return Path(appimage).resolve().parent if appimage else Path(sys.executable).resolve().parent


def _writable_dir(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def portable_state() -> tuple[bool, str]:
    """(portable_active, note). Portable = a `portable.flag` file sits next to the app."""
    exe = _exe_dir()
    if exe is None or not (exe / "portable.flag").exists():
        return False, ""
    if _writable_dir(exe / "data"):
        return True, ""
    return False, ("portable.flag was found, but the folder is read-only, so the normal data "
                   "folder is used instead.")


def data_mode() -> str:
    """custom (TEXTREPAIRO_HOME) | portable | installed"""
    if os.environ.get("TEXTREPAIRO_HOME"):
        return "custom"
    return "portable" if portable_state()[0] else "installed"


def data_dir() -> Path:
    """Folder for models, runtimes, history and settings. Override with TEXTREPAIRO_HOME."""
    override = os.environ.get("TEXTREPAIRO_HOME")
    if override:
        base = Path(override)
    else:
        active, _ = portable_state()
        base = (_exe_dir() / "data") if active and _exe_dir() else Path(
            user_data_dir(APP_NAME, appauthor=False))
    base.mkdir(parents=True, exist_ok=True)
    return base


def models_dir() -> Path:
    p = data_dir() / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def runtime_dir() -> Path:
    p = data_dir() / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def packs_dir() -> Path:
    """Folder where users can drop their own slang/context packs (.json)."""
    p = data_dir() / "packs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def updates_dir() -> Path:
    p = data_dir() / "updates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def bundled_runtime_dir() -> Path | None:
    """Runtime shipped inside a frozen (PyInstaller) build, if present."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = Path(base) / "runtime"
        if p.is_dir():
            return p
    dev = Path(__file__).resolve().parents[2] / "packaging" / "runtime"
    if dev.is_dir():
        return dev
    return None


def web_dir() -> Path:
    return Path(__file__).resolve().parent / "web"


def bundled_data_dir() -> Path:
    """Read-only data shipped with the app (slang packs, notices)."""
    return Path(__file__).resolve().parent / "data"


@dataclass
class Settings:
    model_id: str = "standard"  # id from the model registry, or "custom:<filename>"
    backend: str = "auto"  # auto | cpu | vulkan | cuda | metal
    context_size: int = 4096
    threads: int = 0  # 0 = let llama.cpp decide
    gpu_layers: int = -1  # -1 = all layers when a GPU backend is active
    default_mode: str = "fix"
    default_formality: str = "normal"  # normal | advanced | extreme
    theme: str = "system"  # system | light | dark
    keep_engine_loaded: bool = True
    history_enabled: bool = True
    private_mode: bool = False  # while on, nothing is written to history
    forget_on_exit: bool = False
    update_mode: str = "automatic"  # automatic | notify | off
    last_update_check: float = 0.0
    pending_update: dict = field(default_factory=dict)  # {"version","path","sha256"} when "Later"
    unclean_exits: int = 0
    extra: dict = field(default_factory=dict)


_lock = threading.Lock()


def settings_path() -> Path:
    return data_dir() / "settings.json"


def load_settings() -> Settings:
    path = settings_path()
    s = Settings()
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for k, v in raw.items():
                if hasattr(s, k):
                    setattr(s, k, v)
        except (OSError, ValueError):
            pass
    if s.default_mode == "formal":  # v0.1 name, now "professional"
        s.default_mode = "professional"
    return s


def save_settings(s: Settings) -> None:
    with _lock:
        tmp = settings_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")
        tmp.replace(settings_path())


# ---------------------------------------------------------------- session / safe mode

def _lock_path() -> Path:
    return data_dir() / "session.lock"


def begin_session() -> bool:
    """Mark a session as started. Returns True when the previous one ended badly twice (safe mode)."""
    lock = _lock_path()
    s = load_settings()
    if lock.exists():
        s.unclean_exits += 1
    else:
        s.unclean_exits = 0
    save_settings(s)
    lock.write_text(str(time.time()), encoding="utf-8")
    return s.unclean_exits >= 2


def end_session() -> None:
    try:
        _lock_path().unlink()
    except OSError:
        pass
    s = load_settings()
    if s.unclean_exits:
        s.unclean_exits = 0
        save_settings(s)
