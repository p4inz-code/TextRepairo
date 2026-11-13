"""Desktop launcher: local server + native window (pywebview), or the default browser."""

from __future__ import annotations

import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from . import APP_NAME
from .server import create_app


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server:
    def __init__(self, port: int = 0) -> None:
        self.port = port or _free_port()
        self.app = create_app()
        self.token: str = self.app.state.token
        config = uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="warning",
                                access_log=False)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self) -> None:
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                return
            time.sleep(0.1)
        raise RuntimeError("The local server did not start.")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.token}"


def run_server(port: int = 0, open_browser: bool = True) -> int:
    """Headless/web mode: serve the UI and wait for Ctrl+C."""
    srv = _Server(port)
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
    return 0


def run_desktop() -> int:
    srv = _Server()
    srv.start()
    try:
        import webview  # type: ignore
    except Exception:
        webview = None  # noqa: N806
    if webview is not None and not _force_browser():
        try:
            holder: dict = {}

            class _Api:
                def pick_file(self) -> str | None:
                    win = holder.get("win")
                    if win is None:
                        return None
                    res = win.create_file_dialog(
                        webview.OPEN_DIALOG, file_types=("GGUF model (*.gguf)", "All files (*.*)"))
                    return res[0] if res else None

            holder["win"] = webview.create_window(
                APP_NAME, srv.url, width=1120, height=780, min_size=(720, 560), js_api=_Api())
            webview.start()
            srv.stop()
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
    return 0


def _force_browser() -> bool:
    import os
    return os.environ.get("TEXTREPAIRO_BROWSER") == "1"
