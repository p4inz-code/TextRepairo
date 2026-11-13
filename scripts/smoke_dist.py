# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Smoke-test a built app: start `serve`, check the UI, session cookie, security headers, packs,
About documents and the status API, then stop. Also runs `doctor --json`.

    python scripts/smoke_dist.py dist/TextRepairo/textrepairo-cli[.exe]
"""

from __future__ import annotations

import http.cookiejar
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

    doc = subprocess.run([exe, "doctor", "--json"], capture_output=True, text=True, timeout=180)
    rows = json.loads(doc.stdout)
    ids = {r["id"] for r in rows}
    assert {"version", "data", "runtime", "packs", "history"} <= ids, ids
    print("doctor:", ", ".join(f"{r['id']}={r['status']}" for r in rows))

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

        # 1. the launch link becomes an HttpOnly session cookie and the token leaves the address
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        resp = opener.open(url, timeout=20)
        html = resp.read().decode()
        assert "TextRepairo" in html, "UI not served"
        assert "?t=" not in resp.geturl(), "token still in the address"
        cookie = next((c for c in jar if c.name == "tr_session"), None)
        assert cookie is not None and cookie.has_nonstandard_attr("HttpOnly"), "session cookie missing"
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp and "unsafe-inline" not in csp, "CSP missing"
        for path in ("style.css", "ui.js", "app.js", "icon.svg"):
            opener.open(f"{base}/{path}", timeout=20).read()

        # 2. no cookie and no token = no API
        try:
            urllib.request.urlopen(base + "/api/status", timeout=20)
            print("API answered without a session")
            return 1
        except urllib.error.HTTPError as e:
            assert e.code == 401, e.code

        # 3. status, styles, packs and About documents are present in the packaged build
        st = json.loads(opener.open(base + "/api/status", timeout=60).read())
        print("status:", {k: st[k] for k in ("version", "platform", "backend", "runtime_ready", "data_mode")})
        assert len(st["styles"]) == 11 and len(st["formalities"]) == 3, "styles missing"
        assert {p["id"] for p in st["packs"]} >= {"en-slang", "hinglish-roman", "marathi-roman"}, "packs missing"
        assert st["max_chars"] == 10000 and st["history_limit"] == 100
        for name in ("license", "terms", "privacy", "notices"):
            text = opener.open(f"{base}/api/about/doc/{name}", timeout=20).read().decode()
            assert "was not found in this build" not in text, f"document '{name}' missing from the build"
        if not st["runtime_ready"]:
            print("bundled llama.cpp engine was not found")
            return 1
        print("SMOKE OK")
        return 0
    except AssertionError as e:
        print("SMOKE FAILED:", e)
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
