# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Optional update check and self-update (modelled on kinoz).

The only network request this module makes is a plain GET to the GitHub releases API for this
project (and, if an update exists, the download of the release asset). No user id, no text, no
system information is sent. The User-Agent is `TextRepairo/<version>`.

Downloads are installed only when their SHA-256 matches the `SHA256SUMS.txt` published with the
release. A SHA-256 from the same release page proves the file arrived intact, not who published it
(see SECURITY.md).

Windows installer builds can install themselves. macOS, Linux and the portable zip only tell the
user and open the release page.

Testing: `TEXTREPAIRO_TEST_UPDATE_API=http://127.0.0.1:<port>/releases/latest` points the check at a
local fake release server. It is honoured only for loopback addresses.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Callable

import httpx

from . import REPO, __version__
from .config import Settings, load_settings, portable_state, save_settings, updates_dir
from .errors import AppError

API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
MAX_UPDATE_BYTES = 600 * 1024 * 1024  # the installer is about 130 MB; refuse anything absurd
CHECK_INTERVAL_S = 24 * 3600
STARTUP_DELAY_S = 8.0

_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")


class UpdateError(AppError, RuntimeError):
    pass


def _test_api() -> str | None:
    url = os.environ.get("TEXTREPAIRO_TEST_UPDATE_API", "")
    if not url:
        return None
    p = urllib.parse.urlparse(url)
    return url if p.scheme == "http" and p.hostname == "127.0.0.1" else None


def api_url() -> str:
    return _test_api() or API_URL


def parse_version(tag: str) -> tuple[int, int, int] | None:
    m = _VERSION.search(tag or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def is_newer(latest: str, current: str = __version__) -> bool:
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def install_kind() -> str:
    """installer = can update itself | portable | manual (macOS, Linux, from source)."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return "manual"
    if portable_state()[0]:
        return "portable"
    exe_dir = Path(sys.executable).resolve().parent
    return "installer" if list(exe_dir.glob("unins*.exe")) else "portable"


def _url_ok(url: str) -> bool:
    if _test_api():
        p = urllib.parse.urlparse(url)
        return p.scheme == "http" and p.hostname == "127.0.0.1"
    return url.startswith(DOWNLOAD_PREFIX)


def parse_sums(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            out[parts[1].lstrip("*").strip()] = parts[0].lower()
    return out


def check(timeout: float = 10.0) -> dict:
    """Ask GitHub for the latest release. Returns a dict describing it (blocking)."""
    headers = {"User-Agent": f"TextRepairo/{__version__}", "Accept": "application/vnd.github+json"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as c:
            r = c.get(api_url(), headers=headers)
            if r.status_code == 404:
                return {"available": False, "current": __version__, "latest": __version__,
                        "kind": install_kind()}
            r.raise_for_status()
            rel = r.json()
            tag = str(rel.get("tag_name", ""))
            latest = ".".join(map(str, parse_version(tag) or (0, 0, 0)))
            info: dict = {"available": is_newer(latest), "current": __version__, "latest": latest,
                          "page_url": str(rel.get("html_url") or f"https://github.com/{REPO}/releases/latest"),
                          "notes": str(rel.get("body") or "")[:1500], "kind": install_kind(),
                          "asset": None, "asset_url": None, "sha256": None}
            if not info["available"]:
                return info
            assets = {a.get("name"): a.get("browser_download_url") for a in rel.get("assets", [])}
            want = f"TextRepairo-Setup-{latest}.exe"
            sums_url = assets.get("SHA256SUMS.txt")
            if info["kind"] == "installer" and want in assets and sums_url and _url_ok(
                    assets[want]) and _url_ok(sums_url):
                sums = parse_sums(c.get(sums_url, headers=headers).text)
                if want in sums:
                    info.update(asset=want, asset_url=assets[want], sha256=sums[want])
            if not info["asset"]:
                info["kind"] = "manual"  # no verified installer: just point to the release page
            return info
    except (httpx.HTTPError, ValueError) as e:
        raise UpdateError(f"Could not check for updates: {e}") from e


def should_check_now(settings: Settings, now: float | None = None) -> bool:
    now = now if now is not None else time.time()
    return settings.update_mode != "off" and now - settings.last_update_check >= CHECK_INTERVAL_S


def record_check(settings: Settings | None = None) -> None:
    s = settings or load_settings()
    s.last_update_check = time.time()
    save_settings(s)


def sha256_file(path: Path, progress: Callable[[int, int], None] | None = None) -> str:
    h = hashlib.sha256()
    total = path.stat().st_size
    done = 0
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    return h.hexdigest()


def download(info: dict, progress: Callable[[int, int], None] | None = None,
             cancel: Callable[[], bool] | None = None) -> Path:
    """Download the verified installer. Deletes the file and raises if the checksum is wrong."""
    if not info.get("asset_url") or not info.get("sha256") or not _url_ok(info["asset_url"]):
        raise UpdateError("This update cannot be installed automatically.")
    name = re.sub(r"[^\w.\-]", "_", info["asset"])
    dest = updates_dir() / name
    part = dest.with_suffix(dest.suffix + ".part")
    h = hashlib.sha256()
    try:
        with httpx.stream("GET", info["asset_url"], follow_redirects=True, timeout=60.0,
                          headers={"User-Agent": f"TextRepairo/{__version__}"}) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or 0)
            done = 0
            with open(part, "wb") as out:
                for chunk in r.iter_bytes(1024 * 256):
                    if cancel and cancel():
                        raise UpdateError("Download cancelled.")
                    if done + len(chunk) > MAX_UPDATE_BYTES:
                        raise UpdateError("The update is larger than expected, so it was not installed.")
                    out.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total or done)
    except (httpx.HTTPError, OSError) as e:
        part.unlink(missing_ok=True)
        raise UpdateError(f"Download failed: {e}") from e
    except UpdateError:
        part.unlink(missing_ok=True)
        raise
    if h.hexdigest() != info["sha256"]:
        part.unlink(missing_ok=True)
        raise UpdateError("The downloaded file does not match its published checksum, so it was "
                          "deleted and nothing was installed.")
    part.replace(dest)
    return dest


def remember_pending(info: dict, path: Path) -> None:
    s = load_settings()
    s.pending_update = {"version": info["latest"], "path": str(path), "sha256": info["sha256"]}
    save_settings(s)


def clear_pending() -> None:
    s = load_settings()
    if s.pending_update:
        s.pending_update = {}
        save_settings(s)


def launch_installer(path: Path) -> None:
    """Start the Inno Setup installer silently; it closes and restarts the app by itself."""
    if sys.platform != "win32":
        raise UpdateError("Automatic install is only available on Windows installer builds.")
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                      "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"], creationflags=flags,
                     close_fds=True)


def apply_pending() -> bool:
    """At startup: if the user chose 'Later' last time, verify and install now. True = installing."""
    s = load_settings()
    p = s.pending_update or {}
    if not p or s.update_mode == "off" or install_kind() != "installer":
        return False
    path = Path(p.get("path", ""))
    try:
        if not path.is_file() or path.parent != updates_dir() or sha256_file(path) != p.get("sha256"):
            raise UpdateError("pending update failed verification")
        if not is_newer(p.get("version", "0.0.0")):
            raise UpdateError("pending update is not newer")
        clear_pending()
        launch_installer(path)
        return True
    except (UpdateError, OSError):
        clear_pending()
        path.unlink(missing_ok=True) if path.parent == updates_dir() else None
        return False
