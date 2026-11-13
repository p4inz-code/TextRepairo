# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Model registry, downloads and local model files.

Only permissively licensed models (Apache-2.0 / MIT) are listed. Users can import any
GGUF file themselves ("bring your own model") at their own risk.
"""

from __future__ import annotations

import hashlib
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from .config import models_dir


@dataclass(frozen=True)
class ModelSpec:
    id: str
    tier: str
    name: str
    filename: str
    url: str
    size: int  # bytes
    sha256: str
    license: str
    min_ram_gb: float
    description: str
    thinking_hybrid: bool = False  # needs enable_thinking=false in chat template
    source: str = ""


REGISTRY: list[ModelSpec] = [
    ModelSpec(
        id="lite",
        tier="Lite",
        name="Qwen3 1.7B",
        filename="Qwen3-1.7B-Q4_K_M.gguf",
        url="https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf",
        size=1107409472,
        sha256="b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897",
        license="Apache-2.0",
        min_ram_gb=4,
        description="Fastest and smallest. For old laptops. Lower quality on hard text and rare languages.",
        thinking_hybrid=True,
        source="https://huggingface.co/Qwen/Qwen3-1.7B",
    ),
    ModelSpec(
        id="standard",
        tier="Standard",
        name="Qwen3 4B Instruct 2507",
        filename="Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        url="https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        size=2497281120,
        sha256="3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597",
        license="Apache-2.0",
        min_ram_gb=6,
        description="Recommended. Good quality in 100+ languages, runs well on a normal CPU.",
        source="https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507",
    ),
    ModelSpec(
        id="pro",
        tier="Pro",
        name="Qwen3 8B",
        filename="Qwen3-8B-Q4_K_M.gguf",
        url="https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf",
        size=5027783488,
        sha256="d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785",
        license="Apache-2.0",
        min_ram_gb=10,
        description="Best quality. Wants a GPU with 8 GB VRAM or 16 GB RAM.",
        thinking_hybrid=True,
        source="https://huggingface.co/Qwen/Qwen3-8B",
    ),
]

BY_ID = {m.id: m for m in REGISTRY}


class ModelError(RuntimeError):
    pass


def get_spec(model_id: str) -> ModelSpec | None:
    return BY_ID.get(model_id)


def model_path(spec: ModelSpec) -> Path:
    return models_dir() / spec.filename


def is_installed(spec: ModelSpec) -> bool:
    p = model_path(spec)
    return p.is_file() and p.stat().st_size == spec.size


def custom_models() -> list[Path]:
    """GGUF files in the models folder that are not part of the registry."""
    known = {m.filename for m in REGISTRY}
    return sorted(p for p in models_dir().glob("*.gguf") if p.name not in known)


def resolve_model(model_id: str) -> tuple[Path, ModelSpec | None]:
    """Return the file for a model id ("standard", "custom:name.gguf"). Raises ModelError."""
    if model_id.startswith("custom:"):
        p = models_dir() / Path(model_id[len("custom:"):]).name
        if not p.is_file():
            raise ModelError(f"Custom model not found: {p.name}")
        return p, None
    spec = BY_ID.get(model_id)
    if spec is None:
        raise ModelError(f"Unknown model id: {model_id}")
    if not is_installed(spec):
        raise ModelError(f"Model '{spec.name}' is not downloaded yet.")
    return model_path(spec), spec


def sha256_file(path: Path, progress: Callable[[int], None] | None = None) -> str:
    h = hashlib.sha256()
    done = 0
    with open(path, "rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress(done)
    return h.hexdigest()


def download_model(
    spec: ModelSpec,
    progress: Callable[[int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Path:
    """Download with resume support, verify SHA-256, and move into place.

    Blocking. Run it in a worker thread. This is the only place the app talks to
    the internet, and only because the user asked for it.
    """
    dest = model_path(spec)
    if is_installed(spec):
        return dest
    part = dest.with_suffix(dest.suffix + ".part")
    start = part.stat().st_size if part.exists() else 0
    if start > spec.size:
        part.unlink()
        start = 0
    headers = {"User-Agent": "TextRepairo", }
    if start:
        headers["Range"] = f"bytes={start}-"
    req = urllib.request.Request(spec.url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 416 and start == spec.size:  # already complete
            resp = None
        else:
            raise ModelError(f"Download failed: HTTP {e.code}") from e
    except (urllib.error.URLError, OSError) as e:
        raise ModelError(f"Download failed (are you online?): {e}") from e

    if resp is not None:
        if start and getattr(resp, "status", 200) != 206:
            start = 0  # server ignored Range; restart
        mode = "ab" if start else "wb"
        done = start
        try:
            with open(part, mode) as out:
                while True:
                    if cancel and cancel():
                        raise ModelError("Download cancelled.")
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, spec.size)
        except (urllib.error.URLError, OSError) as e:
            raise ModelError(f"Download interrupted (it can be resumed): {e}") from e
        finally:
            resp.close()

    if part.stat().st_size != spec.size:
        raise ModelError("Downloaded file has the wrong size. Retry to resume.")
    if sha256_file(part) != spec.sha256:
        part.unlink(missing_ok=True)
        raise ModelError("Checksum mismatch: the download was corrupted and was deleted. Retry.")
    part.replace(dest)
    return dest


def import_model(src: str | Path) -> Path:
    """Copy a user-supplied .gguf file into the models folder."""
    src = Path(src).expanduser()
    if not src.is_file():
        raise ModelError(f"File not found: {src}")
    if src.suffix.lower() != ".gguf":
        raise ModelError("Only .gguf model files can be imported.")
    with open(src, "rb") as f:
        if f.read(4) != b"GGUF":
            raise ModelError("This file is not a valid GGUF model.")
    dest = models_dir() / src.name
    if dest.resolve() != src.resolve():
        shutil.copy2(src, dest)
    return dest


def remove_model(model_id: str) -> None:
    if model_id.startswith("custom:"):
        p = models_dir() / Path(model_id[len("custom:"):]).name
    else:
        spec = BY_ID.get(model_id)
        if spec is None:
            raise ModelError(f"Unknown model id: {model_id}")
        p = model_path(spec)
        p.with_suffix(p.suffix + ".part").unlink(missing_ok=True)
    p.unlink(missing_ok=True)


def recommend(ram_gb: float, vram_gb: float) -> str:
    """Pick a default tier for the hardware."""
    if vram_gb >= 7 or ram_gb >= 24:
        return "pro" if (vram_gb >= 7) else "standard"
    if ram_gb >= 6:
        return "standard"
    return "lite"


def list_models() -> Iterator[dict]:
    for m in REGISTRY:
        part = model_path(m).with_suffix(model_path(m).suffix + ".part")
        yield {
            "id": m.id,
            "tier": m.tier,
            "name": m.name,
            "size": m.size,
            "license": m.license,
            "description": m.description,
            "installed": is_installed(m),
            "partial": part.stat().st_size if part.exists() else 0,
            "min_ram_gb": m.min_ram_gb,
            "source": m.source,
        }
    for p in custom_models():
        yield {
            "id": f"custom:{p.name}",
            "tier": "Custom",
            "name": p.name,
            "size": p.stat().st_size,
            "license": "unknown (imported by you)",
            "description": "Imported model file. Check its license yourself.",
            "installed": True,
            "partial": 0,
            "min_ram_gb": 0,
            "source": "",
        }
