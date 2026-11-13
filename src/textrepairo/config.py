"""Paths and persistent user settings."""

from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_data_dir

from . import APP_NAME


def data_dir() -> Path:
    """Folder for models, runtimes and settings. Override with TEXTREPAIRO_HOME."""
    override = os.environ.get("TEXTREPAIRO_HOME")
    base = Path(override) if override else Path(user_data_dir(APP_NAME, appauthor=False))
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


@dataclass
class Settings:
    model_id: str = "standard"  # id from the model registry, or "custom:<filename>"
    backend: str = "auto"  # auto | cpu | vulkan | cuda | metal
    context_size: int = 4096
    threads: int = 0  # 0 = let llama.cpp decide
    gpu_layers: int = -1  # -1 = all layers when a GPU backend is active
    default_mode: str = "fix"
    theme: str = "system"  # system | light | dark
    keep_engine_loaded: bool = True
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
    return s


def save_settings(s: Settings) -> None:
    with _lock:
        tmp = settings_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")
        tmp.replace(settings_path())
