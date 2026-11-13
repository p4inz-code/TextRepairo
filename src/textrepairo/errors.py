# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Errors that are safe to show to the user, and safe handling of user-chosen file paths.

The app only ever shows two kinds of error text in its interface:
  * messages written by this app (`AppError.public`), with the home and data folders hidden, and
  * a short generic sentence for anything unexpected (details are never sent to the page).
Python exception text, stack traces and internal paths never reach the browser.
"""

from __future__ import annotations

import errno
import os
import sys
from pathlib import Path

GENERIC = "Something went wrong. Open Settings > Doctor to check your setup, then try again."


class AppError(Exception):
    """An error whose message was written for the user."""

    def __init__(self, public: str) -> None:
        super().__init__(public)
        self.public = public


def _hide_paths(text: str) -> str:
    from .config import data_dir
    for real, label in ((str(data_dir()), "<data>"), (str(Path.home()), "~")):
        if real and real in text:
            text = text.replace(real, label)
    return text


def public_message(exc: BaseException) -> str:
    """The text to show for `exc`. Unknown exceptions give a generic sentence, never their details."""
    if isinstance(exc, AppError):
        return _hide_paths(exc.public)
    if isinstance(exc, OSError):
        name = errno.errorcode.get(exc.errno or 0, "")
        return "A file or folder could not be used" + (f" ({name})." if name else ".")
    return GENERIC


def safe_user_file(path: object, suffixes: set[str], error: type[AppError], label: str) -> Path:
    """Check a file path that the user picked: absolute, an ordinary file, the right type.

    Network-share paths (\\server\share, //server/share) are refused so a pick can never make the
    computer contact another machine.
    """
    if not isinstance(path, (str, os.PathLike)):
        raise error(f"Choose a {label} file.")
    raw = os.fspath(path)
    if not raw or "\x00" in raw or len(raw) > 1024:
        raise error(f"Choose a {label} file.")
    if raw.startswith(("\\\\", "//")):
        raise error("Files on network shares can't be imported. Copy the file to this computer first.")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        raise error(f"Give the full path of the {label} file.")
    try:
        resolved = p.resolve(strict=True)
    except (OSError, RuntimeError):
        raise error(f"The {label} file was not found.") from None
    if sys.platform == "win32" and str(resolved).startswith("\\\\"):
        raise error("Files on network shares can't be imported. Copy the file to this computer first.")
    if not resolved.is_file():
        raise error(f"Choose a {label} file.")
    if resolved.suffix.lower() not in suffixes:
        raise error(f"Only {', '.join(sorted(suffixes))} files can be imported here.")
    return resolved
