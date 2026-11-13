# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Local history of past results.

Stored in one SQLite file in the data folder. Nothing is ever sent anywhere. Only the newest
`HISTORY_LIMIT` entries are kept: adding one more permanently deletes the oldest. Deleted rows
are overwritten (`secure_delete`) so the text does not linger in the file.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path

from .config import HISTORY_LIMIT, Settings, data_dir

_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  style TEXT NOT NULL,
  formality TEXT NOT NULL,
  input TEXT NOT NULL,
  output TEXT NOT NULL,
  model TEXT NOT NULL,
  seconds REAL NOT NULL,
  warnings INTEGER NOT NULL
)"""


def history_path() -> Path:
    return data_dir() / "history.db"


def _connect() -> sqlite3.Connection:
    path = history_path()
    new = not path.exists()
    con = sqlite3.connect(path, timeout=10)
    if new:
        con.execute("PRAGMA auto_vacuum=FULL")  # must be set before the first table exists
    con.execute("PRAGMA secure_delete=ON")
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute(_SCHEMA)
    if new and os.name != "nt":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return con


def allowed(settings: Settings) -> bool:
    """History is recorded unless it is switched off or Private mode is on."""
    return settings.history_enabled and not settings.private_mode


def add(style: str, formality: str, text_in: str, text_out: str, model: str, seconds: float,
        warnings: int, limit: int = HISTORY_LIMIT) -> int:
    with _lock:
        con = _connect()
        try:
            cur = con.execute(
                "INSERT INTO history (ts, style, formality, input, output, model, seconds, warnings) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (time.time(), style, formality, text_in, text_out, model, float(seconds), int(warnings)))
            new_id = int(cur.lastrowid or 0)
            con.execute("DELETE FROM history WHERE id NOT IN "
                        "(SELECT id FROM history ORDER BY id DESC LIMIT ?)", (limit,))
            con.commit()
            return new_id
        finally:
            con.close()


def _row(r: tuple, full: bool) -> dict:
    d = {"id": r[0], "ts": r[1], "style": r[2], "formality": r[3], "model": r[6],
         "seconds": r[7], "warnings": r[8]}
    if full:
        d["input"], d["output"] = r[4], r[5]
    else:
        d["input_snippet"] = " ".join(r[4].split())[:90]
        d["output_snippet"] = " ".join(r[5].split())[:90]
    return d


_COLS = "id, ts, style, formality, input, output, model, seconds, warnings"


def list_entries(limit: int = HISTORY_LIMIT) -> list[dict]:
    with _lock:
        if not history_path().exists():
            return []
        con = _connect()
        try:
            rows = con.execute(f"SELECT {_COLS} FROM history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        finally:
            con.close()
    return [_row(r, False) for r in rows]


def get(entry_id: int) -> dict | None:
    with _lock:
        con = _connect()
        try:
            r = con.execute(f"SELECT {_COLS} FROM history WHERE id=?", (entry_id,)).fetchone()
        finally:
            con.close()
    return _row(r, True) if r else None


def delete(entry_id: int) -> bool:
    with _lock:
        con = _connect()
        try:
            n = con.execute("DELETE FROM history WHERE id=?", (entry_id,)).rowcount
            con.commit()
        finally:
            con.close()
    return n > 0


def count() -> int:
    with _lock:
        if not history_path().exists():
            return 0
        con = _connect()
        try:
            return int(con.execute("SELECT COUNT(*) FROM history").fetchone()[0])
        finally:
            con.close()


def clear() -> None:
    """Delete everything, then compact the file so no text is left behind."""
    with _lock:
        if not history_path().exists():
            return
        con = _connect()
        try:
            con.execute("DELETE FROM history")
            con.commit()
            con.execute("VACUUM")
        finally:
            con.close()


def integrity() -> str:
    with _lock:
        if not history_path().exists():
            return "ok"
        con = _connect()
        try:
            return str(con.execute("PRAGMA integrity_check").fetchone()[0])
        finally:
            con.close()
