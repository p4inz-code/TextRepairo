# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Slang and context packs.

A pack is a small JSON file that tells the model what slang, chat shorthand or romanized
words probably mean. Packs ship with the app (`data/packs/`) and users can add their own
(`<data folder>/packs/`). Matching happens offline for each request, and only the matched
entries (at most `MAX_HINTS`) are added to the prompt, so prompts stay small and fast.

Pack text is treated as data. User packs are validated strictly (size, shape, length, no
control characters) before they are accepted.

Pack format:
    {"id": "my-pack", "name": "My words", "version": 1, "entries": [["term", "meaning", "optional note"]]}
"""

from __future__ import annotations

import json
import re
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from .config import bundled_data_dir, packs_dir
from .errors import AppError, safe_user_file

MAX_HINTS = 20
MAX_PACK_BYTES = 256 * 1024
MAX_ENTRIES = 5000
MAX_TERM = 40
MAX_MEANING = 120
MAX_NOTE = 80

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


class PackError(AppError, ValueError):
    pass


@dataclass
class Pack:
    id: str
    name: str
    version: int
    source: str  # bundled | user
    entries: list[tuple[str, str, str]]


def _clean(s: object, limit: int, what: str) -> str:
    if not isinstance(s, str):
        raise PackError(f"{what} must be text.")
    s = s.strip()
    if _CONTROL.search(s):
        raise PackError(f"{what} contains control characters.")
    if len(s) > limit:
        raise PackError(f"{what} is longer than {limit} characters.")
    return s


def validate_pack(raw: object, source: str) -> Pack:
    if not isinstance(raw, dict):
        raise PackError("A pack must be a JSON object.")
    pid = raw.get("id")
    if not isinstance(pid, str) or not _ID.match(pid):
        raise PackError("Pack 'id' must be lowercase letters, digits, '-' or '_' (max 40).")
    name = _clean(raw.get("name", pid), 80, "name")
    version = raw.get("version", 1)
    if not isinstance(version, int):
        raise PackError("'version' must be a whole number.")
    entries_raw = raw.get("entries")
    if not isinstance(entries_raw, list) or not entries_raw:
        raise PackError("'entries' must be a non-empty list.")
    if len(entries_raw) > MAX_ENTRIES:
        raise PackError(f"A pack can have at most {MAX_ENTRIES} entries.")
    entries: list[tuple[str, str, str]] = []
    for i, e in enumerate(entries_raw):
        if not isinstance(e, list) or len(e) not in (2, 3):
            raise PackError(f"Entry {i + 1} must be [term, meaning] or [term, meaning, note].")
        term = _clean(e[0], MAX_TERM, f"entry {i + 1} term")
        meaning = _clean(e[1], MAX_MEANING, f"entry {i + 1} meaning")
        note = _clean(e[2], MAX_NOTE, f"entry {i + 1} note") if len(e) == 3 else ""
        if len(term) < 2 or not meaning:
            raise PackError(f"Entry {i + 1} needs a term of at least 2 characters and a meaning.")
        entries.append((term, meaning, note))
    return Pack(pid, name, version, source, entries)


def _read(path: Path, source: str) -> Pack:
    if path.stat().st_size > MAX_PACK_BYTES:
        raise PackError("Pack file is too large.")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PackError(f"Could not read pack: {e}") from e
    return validate_pack(raw, source)


# ---------------------------------------------------------------- loading + matching

_lock = threading.Lock()
_cache: dict = {"sig": None, "packs": [], "rx": None, "index": {}}


def _signature() -> tuple:
    files = []
    for d in (bundled_data_dir() / "packs", packs_dir()):
        if d.is_dir():
            files += [(str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(d.glob("*.json"))]
    return tuple(files)


def load_packs() -> list[Pack]:
    """All valid packs. Invalid user packs are skipped, never fatal."""
    with _lock:
        sig = _signature()
        if _cache["sig"] == sig:
            return _cache["packs"]
        packs: list[Pack] = []
        seen: set[str] = set()
        for source, d in (("bundled", bundled_data_dir() / "packs"), ("user", packs_dir())):
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.json")):
                try:
                    pack = _read(p, source)
                except PackError:
                    continue
                if pack.id in seen:
                    continue
                seen.add(pack.id)
                packs.append(pack)
        index: dict[str, tuple[str, str]] = {}
        for pack in packs:
            for term, meaning, note in pack.entries:
                index.setdefault(term.lower(), (meaning, note))
        terms = sorted(index, key=len, reverse=True)
        rx = None
        if terms:
            alt = "|".join(re.escape(t) for t in terms)
            rx = re.compile(rf"(?<![\w'])(?:{alt})(?![\w'])", re.I)
        _cache.update(sig=sig, packs=packs, rx=rx, index=index)
        return packs


def match(text: str, limit: int = MAX_HINTS) -> list[str]:
    """Hints like '"ngl" = not going to lie' for terms found in `text` (first occurrence order)."""
    load_packs()
    rx, index = _cache["rx"], _cache["index"]
    if rx is None or not text:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for m in rx.finditer(text):
        key = m.group(0).lower()
        if key in seen or key not in index:
            continue
        seen.add(key)
        meaning, note = index[key]
        out.append(f'"{m.group(0)}" = {meaning}' + (f" ({note})" if note else ""))
        if len(out) >= limit:
            break
    return out


def list_packs() -> list[dict]:
    return [{"id": p.id, "name": p.name, "version": p.version, "source": p.source,
             "entries": len(p.entries)} for p in load_packs()]


def import_pack(path: str | Path) -> Pack:
    """Validate a pack file and copy it into the user packs folder."""
    src = safe_user_file(path, {".json"}, PackError, "pack (.json)")
    pack = _read(src, "user")
    if any(p.id == pack.id and p.source == "bundled" for p in load_packs()):
        raise PackError(f"A built-in pack already uses the id '{pack.id}'. Change the id and try again.")
    # Write our own validated copy (never the user's file byte for byte), named from the checked id.
    dest = packs_dir() / f"{pack.id}.json"
    dest.write_text(json.dumps({"id": pack.id, "name": pack.name, "version": pack.version,
                                "entries": [list(e) if e[2] else list(e[:2]) for e in pack.entries]},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    return pack


def remove_pack(pack_id: str) -> bool:
    if not _ID.match(pack_id):
        raise PackError("Bad pack id.")
    for existing in packs_dir().glob("*.json"):  # only files that are really in the packs folder
        if existing.stem == pack_id:
            existing.unlink()
            return True
    return False
