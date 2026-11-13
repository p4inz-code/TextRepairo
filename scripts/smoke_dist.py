"""Smoke-test a built app: start `serve`, fetch the UI and the status API, then stop.

    python scripts/smoke_dist.py dist/TextRepairo/textrepairo-cli[.exe]
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    exe = str(Path(sys.argv[1]).resolve())
    print(subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=120).stdout.strip())
    proc = subprocess.Popen([exe, "serve", "--no-open"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    url = None
    deadline = time.time() + 120
    try:
        while time.time() < deadline and url is None:
            line = proc.stdout.readline()
            if not line:
                break
            m = re.search(r"(http://127\.0\.0\.1:\d+/\?t=[\w-]+)", line)
            if m:
                url = m.group(1)
        if not url:
            print("server did not print a URL")
            return 1
        base, token = url.split("/?t=")
        html = urllib.request.urlopen(base + "/", timeout=20).read().decode()
        assert "TextRepairo" in html, "UI not served"
        for path in ("style.css", "app.js", "icon.svg"):
            urllib.request.urlopen(f"{base}/{path}", timeout=20).read()
        try:
            urllib.request.urlopen(base + "/api/status", timeout=20)
            print("API answered without a token")
            return 1
        except urllib.error.HTTPError as e:
            assert e.code == 401, e.code
        req = urllib.request.Request(base + "/api/status", headers={"X-Token": token})
        st = json.loads(urllib.request.urlopen(req, timeout=60).read())
        print("status:", {k: st[k] for k in ("version", "platform", "backend", "runtime_ready", "installed_backends")})
        if not st["runtime_ready"]:
            print("bundled llama.cpp engine was not found")
            return 1
        print("SMOKE OK")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
