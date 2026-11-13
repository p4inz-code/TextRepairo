# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Repository hygiene: licence headers, required documents, no private details, pinned checksums."""

import hashlib
import re
import subprocess
from pathlib import Path

import pytest

from textrepairo import runtime

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()


def _tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return [ROOT / line for line in out.stdout.splitlines() if (ROOT / line).is_file()]
    except (OSError, subprocess.SubprocessError):
        pass
    skip = {".venv", "dist", "build", ".git", "__pycache__", ".pytest_cache", ".uitest-home", "runtime"}
    return [p for p in ROOT.rglob("*") if p.is_file() and not (set(p.relative_to(ROOT).parts) & skip)]


FILES = _tracked_files()
TEXT_SUFFIX = {".py", ".md", ".js", ".css", ".html", ".json", ".jsonl", ".yml", ".yaml", ".toml", ".iss",
               ".sh", ".spec", ".txt", ".svg", ".cfg", ".gitignore", ".gitattributes"}


def test_source_files_carry_license_headers():
    missing = []
    for p in FILES:
        rel = p.relative_to(ROOT)
        if p.suffix in (".py", ".sh", ".iss", ".spec", ".js", ".css") and rel.parts[0] in (
                "src", "tests", "scripts", "eval", "packaging"):
            if "SPDX-License-Identifier: GPL-3.0-or-later" not in p.read_text(encoding="utf-8")[:400]:
                missing.append(str(rel))
    assert not missing, missing


def test_required_documents_exist():
    for name in ("LICENSE", "ADDITIONAL_TERMS.md", "PRIVACY.md", "SECURITY.md", "SUPPORT.md", "ROADMAP.md",
                 "CHANGELOG.md", "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md", "README.md",
                 "docs/GUIDE.md", "docs/THREAT_MODEL.md", "docs/PACKS.md", "docs/DEVELOPMENT.md", "docs/EVAL.md"):
        assert (ROOT / name).is_file(), name


def test_credit_line_is_consistent():
    terms = (ROOT / "ADDITIONAL_TERMS.md").read_text(encoding="utf-8")
    assert "Created by Atharva Patil, P4inz Interactive Labs" in terms
    assert "Copyright © 2026 Atharva Patil — P4inz Interactive Labs" in terms
    assert "P4inz Int Labs" not in "".join(p.read_text(encoding="utf-8", errors="ignore")
                                           for p in FILES if p.suffix in TEXT_SUFFIX and p != SELF)


PRIVATE = [r"masteratharva", r"gmail\.com", r"[A-Za-z]:\\Users\\", r"/Users/[A-Za-z]", r"\\Admin\\",
           r"\.claude", r"Navi Mumbai", r"RTX ?4060"]


def test_no_private_details_in_tracked_text_files():
    hits = []
    for p in FILES:
        if p.suffix not in TEXT_SUFFIX or p == SELF:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for pat in PRIVATE:
            if re.search(pat, text):
                hits.append(f"{p.relative_to(ROOT)}: {pat}")
    assert not hits, hits


def test_every_runtime_asset_is_pinned():
    missing = [n for b in runtime.BACKENDS
               for k in ("win-x64", "win-arm64", "macos-arm64", "macos-x64", "linux-x64", "linux-arm64")
               for n in runtime.asset_names(b, k) if n not in runtime.ASSET_SHA256]
    assert not missing, missing
    assert all(re.fullmatch(r"[0-9a-f]{64}", v) for v in runtime.ASSET_SHA256.values())


def test_verify_asset_accepts_match_and_rejects_everything_else(tmp_path, monkeypatch):
    data = b"engine bytes"
    name = "llama-fake-asset.zip"
    f = tmp_path / name
    f.write_bytes(data)
    monkeypatch.setitem(runtime.ASSET_SHA256, name, hashlib.sha256(data).hexdigest())
    runtime._verify_asset(name, f)
    assert f.exists()
    monkeypatch.setitem(runtime.ASSET_SHA256, name, "0" * 64)
    with pytest.raises(runtime.RuntimeError_, match="checksum"):
        runtime._verify_asset(name, f)
    assert not f.exists()  # a mismatching file is deleted
    g = tmp_path / "unknown.zip"
    g.write_bytes(data)
    with pytest.raises(runtime.RuntimeError_, match="not a known"):
        runtime._verify_asset("unknown.zip", g)
    assert not g.exists()


def test_injection_corpus_is_large_enough():
    import json
    rows = [json.loads(x) for x in (ROOT / "eval" / "cases.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    inj = [r for r in rows if r["id"].startswith("inj") or "injection" in r.get("tags", [])]
    assert len(inj) >= 30 and len(rows) >= 150
    assert len({r["id"] for r in rows}) == len(rows)


def test_no_telemetry_packages_are_installed():
    import importlib.util
    for mod in ("opentelemetry.sdk", "sentry_sdk", "posthog", "mixpanel", "segment", "amplitude", "datadog"):
        try:
            found = importlib.util.find_spec(mod)
        except (ImportError, ValueError):
            found = None
        assert found is None, f"{mod} is installed: the app must not ship telemetry"


def test_only_known_hosts_appear_in_the_source():
    """Every web address in the application code must be one of the project's known endpoints."""
    allowed = {"api.github.com", "github.com", "huggingface.co", "127.0.0.1", "localhost", "atharvapatil.tech",
               "discord.gg", "p4inz-code.github.io", "buymeacoffee.com", "ggml-org", "www.w3.org"}
    found = set()
    for p in (ROOT / "src" / "textrepairo").glob("*.py"):
        for host in re.findall(r"https?://([A-Za-z0-9.\-]+)", p.read_text(encoding="utf-8")):
            found.add(host)
    assert found <= allowed, sorted(found - allowed)
