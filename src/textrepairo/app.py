# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Desktop launcher: local server + native window (pywebview), or the default browser."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from . import APP_NAME, COFFEE_URL, DISCORD_URL, DONATE_URL, PORTFOLIO_URL, REPO_URL
from .config import begin_session, end_session
from .server import create_app
from .updater import apply_pending


_EXTERNAL_OK = (REPO_URL, PORTFOLIO_URL, DISCORD_URL, DONATE_URL, COFFEE_URL)


def is_allowed_external(url: str) -> bool:
    """Only our own project links may be opened from the app window."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    for base in _EXTERNAL_OK:
        b = base.rstrip("/")
        if url.rstrip("/") == b or url.startswith(b + "/") or url.startswith(b + "?"):
            return True
    return False


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server:
    def __init__(self, port: int = 0, safe_mode: bool = False, single_use_link: bool = False) -> None:
        self.port = port or _free_port()
        self.app = create_app(port=self.port)
        self.app.state.safe_mode = safe_mode
        self.app.state.single_use_launch = single_use_link
        self.token: str = self.app.state.token
        config = uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="warning",
                                access_log=False)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.app.state.request_exit = self.request_exit
        self.on_exit = lambda: None

    def start(self) -> None:
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                return
            time.sleep(0.1)
        raise RuntimeError("The local server did not start.")

    def request_exit(self) -> None:
        """Called when the app needs to close itself (for example to let the installer run)."""
        self.on_exit()
        self.server.should_exit = True

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.token}"


def _start_session() -> tuple[bool, bool]:
    """(safe_mode, installing_update). Safe mode = the last two sessions ended abnormally."""
    safe = begin_session()
    if not safe and apply_pending():
        end_session()
        return safe, True
    return safe, False


def run_server(port: int = 0, open_browser: bool = True) -> int:
    """Headless/web mode: serve the UI and wait for Ctrl+C."""
    safe, installing = _start_session()
    if installing:
        return 0
    srv = _Server(port, safe)
    srv.start()
    print(f"{APP_NAME} is running. Open this address in your browser:\n  {srv.url}\n"
          "(Only this computer can reach it. Press Ctrl+C to stop.)", flush=True)
    if open_browser:
        webbrowser.open(srv.url)
    try:
        while srv.thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
        end_session()
    return 0


def run_desktop() -> int:
    safe, installing = _start_session()
    if installing:
        return 0
    # In the native window the launch link is used exactly once, so a copy of it (for example from a
    # console log) is useless afterwards. In the browser fallback it stays reusable for a reload.
    try:
        import webview  # type: ignore  # noqa: F401
        native = not _force_browser()
    except Exception:
        native = False
    srv = _Server(safe_mode=safe, single_use_link=native)
    srv.start()
    try:
        import webview  # type: ignore
    except Exception:
        webview = None  # noqa: N806
    if webview is not None and not _force_browser():
        try:
            holder: dict = {}

            class _Api:
                def _pick(self, label: str, pattern: str) -> str | None:
                    win = holder.get("win")
                    if win is None:
                        return None
                    res = win.create_file_dialog(
                        webview.OPEN_DIALOG, file_types=(f"{label} ({pattern})", "All files (*.*)"))
                    return res[0] if res else None

                def pick_file(self) -> str | None:
                    return self._pick("GGUF model", "*.gguf")

                def pick_pack(self) -> str | None:
                    return self._pick("Slang pack", "*.json")

                def open_url(self, url: str) -> bool:
                    if not is_allowed_external(url):
                        return False
                    webbrowser.open(url)
                    return True

            holder["win"] = webview.create_window(
                APP_NAME, srv.url, width=1120, height=780, min_size=(720, 560), js_api=_Api())
            srv.on_exit = lambda: holder["win"].destroy()
            webview.start()
            srv.stop()
            end_session()
            return 0
        except Exception as e:  # noqa: BLE001 - no GUI toolkit available: fall back
            print(f"Native window unavailable ({e}); opening your browser instead.", file=sys.stderr)
    print(f"{APP_NAME} is running at {srv.url}\nClose this window or press Ctrl+C to quit.")
    webbrowser.open(srv.url)
    try:
        while srv.thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
        end_session()
    return 0


def _force_browser() -> bool:
    return os.environ.get("TEXTREPAIRO_BROWSER") == "1"
