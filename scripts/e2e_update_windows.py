# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""End-to-end test of the Windows self-update, with real binaries and a local fake release server.

    python scripts/e2e_update_windows.py dist/TextRepairo-Setup-<version>.exe

What it does (nothing leaves this computer, and your real TextRepairo data is not touched):
  1. installs the given Setup.exe silently into a scratch folder (per user, no administrator prompt),
  2. starts a fake "GitHub release" on 127.0.0.1 that offers the same installer as version 9.9.9,
  3. runs the installed app's `serve` with the test update address, then checks, downloads (real byte
     progress), verifies and installs the update through the app's own API,
  4. confirms the installer really replaced the files, and uninstalls everything again.
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, Response


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    setup = Path(sys.argv[1]).resolve()
    payload = setup.read_bytes()
    name = "TextRepairo-Setup-9.9.9.exe"
    scratch = Path(tempfile.mkdtemp(prefix="tr-e2e-"))
    app_dir, data_dir = scratch / "app", scratch / "data"
    data_dir.mkdir()

    print("1. installing silently to", app_dir)
    r = subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER",
                        f"/DIR={app_dir}", f"/LOG={scratch / 'install.log'}"], timeout=300)
    assert r.returncode == 0, f"installer exit code {r.returncode}"
    cli = app_dir / "textrepairo-cli.exe"
    assert cli.is_file() and any(app_dir.glob("unins*.exe")), "installed files missing"
    before = (cli.stat().st_mtime_ns, cli.stat().st_size)

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    sums = f"{hashlib.sha256(payload).hexdigest()}  {name}\n"
    api = FastAPI()

    @api.get("/releases/latest")
    async def latest():
        return {"tag_name": "v9.9.9", "html_url": f"{base}/page", "body": "e2e",
                "assets": [{"name": name, "browser_download_url": f"{base}/dl/{name}"},
                           {"name": "SHA256SUMS.txt", "browser_download_url": f"{base}/dl/SHA256SUMS.txt"}]}

    @api.get("/dl/SHA256SUMS.txt")
    async def sums_route():
        return PlainTextResponse(sums)

    @api.get("/dl/{n}")
    async def dl(n: str):
        return Response(payload, media_type="application/octet-stream")

    server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)

    env = dict(os.environ, TEXTREPAIRO_HOME=str(data_dir),
               TEXTREPAIRO_TEST_UPDATE_API=f"{base}/releases/latest")
    print("2. starting the installed app with the test update address")
    proc = subprocess.Popen([str(cli), "serve", "--no-open"], env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    try:
        url = None
        end = time.time() + 90
        while time.time() < end and not url:
            m = re.search(r"(http://127\.0\.0\.1:\d+/\?t=[\w-]+)", proc.stdout.readline() or "")
            url = m.group(1) if m else None
        assert url, "the app did not start"
        jar = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        op.open(url, timeout=30).read()
        app_base = url.split("/?t=")[0]

        def call(path, body=None):
            req = urllib.request.Request(app_base + path, data=None if body is None else json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"},
                                         method="GET" if body is None else "POST")
            return op.open(req, timeout=120)

        state = json.loads(call("/api/update/state").read())
        assert state["due"] and state["kind"] == "installer", state
        print("3. update state:", {k: state[k] for k in ("mode", "kind", "due", "current")})
        info = json.loads(call("/api/update/check", {}).read())
        assert info["available"] and info["latest"] == "9.9.9" and info["kind"] == "installer", info
        print("   update found:", info["latest"], info["asset"])
        events = [json.loads(b[5:]) for b in call("/api/update/download", {}).read().decode().split("\n\n")
                  if b.startswith("data:")]
        assert events[-1]["event"] == "done", events[-1]
        progress = [e for e in events if e["event"] == "progress"]
        assert progress and progress[-1]["done"] == progress[-1]["total"] == len(payload), "download progress"
        print(f"   downloaded and verified {len(payload) / 1e6:.0f} MB in {len(progress)} progress steps")
        assert json.loads(call("/api/update/state").read())["pending"] is True
        print("4. installing:", json.loads(call("/api/update/install", {}).read()))
        deadline = time.time() + 180
        while time.time() < deadline:
            time.sleep(2)
            try:
                st = cli.stat()
            except OSError:
                continue
            if (st.st_mtime_ns, st.st_size) != before and proc.poll() is not None:
                break
        else:
            raise AssertionError("the installer did not replace the files in time")
        time.sleep(5)  # let the installer finish
        print("5. the installer replaced the files and the old app exited")
        after = subprocess.run([str(cli), "--version"], capture_output=True, text=True, timeout=60).stdout.strip()
        print("   installed version now:", after)
        ok = True
    except AssertionError as e:
        print("E2E FAILED:", e)
        ok = False
    finally:
        if proc.poll() is None:
            proc.terminate()
        server.should_exit = True
        for u in app_dir.glob("unins*.exe"):
            subprocess.run([str(u), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=180)
            break
        time.sleep(3)
    print("E2E OK" if ok else "E2E FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
