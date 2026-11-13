# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Check that links in the Markdown documents work.

    python scripts/check_links.py            # relative links and anchors only (offline)
    python scripts/check_links.py --online   # also request every external address once

Exit code 1 if a relative link points at a missing file.
"""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_LINK = re.compile(r'(?:href|src)="([^"]+)"')
SKIP = {".venv", "dist", "build", ".git", ".uitest-home", ".uitest-empty", "node_modules"}


def md_files() -> list[Path]:
    return [p for p in ROOT.rglob("*.md") if not (set(p.relative_to(ROOT).parts) & SKIP)]


def main() -> int:
    online = "--online" in sys.argv
    broken: list[str] = []
    external: dict[str, str] = {}
    for md in md_files():
        text = md.read_text(encoding="utf-8", errors="ignore")
        for target in LINK.findall(text) + HTML_LINK.findall(text):
            if target.startswith(("http://", "https://")):
                external.setdefault(target.split("#")[0], str(md.relative_to(ROOT)))
                continue
            if target.startswith(("mailto:", "#", "data:")):
                continue
            path = target.split("#")[0].split("?")[0]
            if not path:
                continue
            dest = (md.parent / path).resolve()
            if not dest.exists():
                broken.append(f"{md.relative_to(ROOT)}: {target}")
    for b in broken:
        print("BROKEN", b)
    print(f"{len(md_files())} documents, {len(external)} external addresses, {len(broken)} broken relative links")
    if online:
        bad = 0
        for url, where in sorted(external.items()):
            if "<" in url or "{" in url or "shields.io" in url or "localhost" in url:
                continue
            try:
                req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "TextRepairo-linkcheck"})
                code = urllib.request.urlopen(req, timeout=20).status
            except urllib.error.HTTPError as e:
                code = e.code
            except Exception as e:  # noqa: BLE001
                code = type(e).__name__
            ok = isinstance(code, int) and code < 400 or code in (403, 405, 429)
            print(("ok   " if ok else "FAIL ") + str(code) + "  " + url + "  (" + where + ")")
            bad += 0 if ok else 1
        print(f"{bad} external address(es) failed")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
