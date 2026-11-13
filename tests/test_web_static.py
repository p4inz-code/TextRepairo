# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Static guards for the web UI: CSP-safe, no native controls, no external resources."""

import re
from pathlib import Path

import pytest

from textrepairo import app as app_mod

WEB = Path(app_mod.__file__).parent / "web"
HTML = (WEB / "index.html").read_text(encoding="utf-8")
JS = {p.name: p.read_text(encoding="utf-8") for p in WEB.glob("*.js")}
CSS = (WEB / "style.css").read_text(encoding="utf-8")


def test_html_has_no_inline_script_style_or_handlers():
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", HTML)
    assert not re.search(r"<style\b", HTML)
    assert not re.search(r"\sstyle\s*=", HTML)
    assert not re.search(r"\son[a-z]+\s*=", HTML)


@pytest.mark.parametrize("name", sorted(JS))
def test_js_avoids_unsafe_apis_and_native_dialogs(name):
    src = JS[name]
    for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function", "document.write",
                "window.confirm", "window.alert", "window.prompt", "localStorage", "sessionStorage"):
        assert bad not in src, f"{name} uses {bad}"
    assert not re.search(r"(?<![\w.])(confirm|alert|prompt)\(", src), f"{name} calls a native dialog"
    assert 'setAttribute("style"' not in src and 'setAttribute("title"' not in src and ".title =" not in src


def test_no_native_form_controls_or_title_tooltips():
    assert "<select" not in HTML and "<dialog" not in HTML
    assert not re.search(r"<(?!title)[^>]*\stitle\s*=", HTML)
    for name, src in JS.items():
        assert 'el("select"' not in src and 'createElement("select")' not in src, name
    # the only native input types the UI creates are the real text boxes and the switch's hidden input
    assert 'type: "checkbox"' in JS["ui.js"] and 'role: "switch"' in JS["ui.js"]
    assert len(re.findall(r'type: "checkbox"', JS["ui.js"] + JS["app.js"])) == 1


def test_no_external_resources():
    for text in (HTML, CSS, *JS.values()):
        assert not re.search(r"(src|href)\s*=\s*[\"']https?://", text)
        assert "@import" not in text and "url(http" not in text
    for name, src in JS.items():
        assert not re.search(r"fetch\(\s*[\"']https?://", src), name


def test_scripts_are_same_origin_files():
    srcs = re.findall(r'<script[^>]*\ssrc="([^"]+)"', HTML)
    assert srcs == ["ui.js", "app.js"] and all((WEB / s).is_file() for s in srcs)


def test_every_web_file_has_license_header():
    for p in WEB.glob("*"):
        if p.suffix in (".js", ".css", ".html"):
            assert "SPDX-License-Identifier: GPL-3.0-or-later" in p.read_text(encoding="utf-8")[:300], p.name


@pytest.mark.parametrize("url,ok", [
    ("https://github.com/p4inz-code/TextRepairo", True),
    ("https://github.com/p4inz-code/TextRepairo/releases/tag/v0.2.0", True),
    ("https://atharvapatil.tech", True),
    ("https://atharvapatil.tech/support/", True),
    ("https://discord.gg/8UKt8s5FbW", True),
    ("https://buymeacoffee.com/p4inz", True),
    ("https://p4inz-code.github.io/donate/", True),
    ("https://atharvapatil.tech.evil.com/", False),
    ("https://github.com/p4inz-code/TextRepairoEvil", False),
    ("http://atharvapatil.tech", False),
    ("file:///C:/Windows/System32/calc.exe", False),
    ("javascript:alert(1)", False),
    ("", False),
])
def test_only_project_links_open_externally(url, ok):
    assert app_mod.is_allowed_external(url) is ok


def test_all_style_examples_exist_in_the_ui():
    from textrepairo.prompts import STYLES
    for sid in STYLES:
        assert f"{sid}:" in JS["app.js"].split("const EXAMPLES")[1].split("};")[0], sid


def test_interface_colors_meet_contrast():
    import importlib.util
    spec = importlib.util.spec_from_file_location("contrast_check", Path(__file__).resolve().parents[1] / "scripts" / "contrast_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main() == 0
