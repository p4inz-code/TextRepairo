# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Check WCAG contrast ratios for the interface colors in both themes.

    python scripts/contrast_check.py          # prints a table, exits 1 if a text pair is below 4.5:1

Reads the color tokens from src/textrepairo/web/style.css so it cannot drift from the real design.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "src" / "textrepairo" / "web" / "style.css"


def tokens(block: str) -> dict[str, str]:
    return {k: v.strip() for k, v in re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", block)}


def lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# (foreground token, background token, what it is)
PAIRS = [
    ("ink", "bg", "body text on page"), ("ink", "surface", "text in panels"),
    ("muted", "bg", "secondary text on page"), ("muted", "surface", "secondary text in panels"),
    ("muted", "surface-2", "secondary text on tracks and tabs"),
    ("accent", "bg", "links on page"), ("accent", "surface", "links in panels"),
    ("accent", "accent-soft", "accent text on tinted cards"), ("ink", "accent-soft", "text on selected cards"),
    ("muted", "accent-soft", "secondary text on selected cards"),
    ("accent-ink", "accent", "text on primary buttons"),
    ("danger", "surface", "danger text"), ("danger", "danger-soft", "error text on its tint"),
    ("warn", "warn-soft", "warning text on its tint"), ("danger", "bg", "danger text on page"),
]


def main() -> int:
    css = CSS.read_text(encoding="utf-8")
    light = tokens(css.split(":root {", 1)[1].split("}", 1)[0])
    dark = tokens(re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\}', css, re.S).group(1))
    failures = 0
    print(f"{'pair':44} {'light':>7} {'dark':>7}")
    for fg, bg, what in PAIRS:
        row = []
        for theme in (light, dark):
            r = ratio(theme[fg], theme[bg])
            row.append(r)
            if r < 4.5:
                failures += 1
        flag = "" if min(row) >= 4.5 else "  <-- below 4.5:1"
        print(f"{what + ' (' + fg + ' on ' + bg + ')':44} {row[0]:7.2f} {row[1]:7.2f}{flag}")
    print("\nAll text pairs meet 4.5:1." if not failures else f"\n{failures} pair(s) below 4.5:1.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
