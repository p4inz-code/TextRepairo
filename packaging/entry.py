"""PyInstaller entry point for both the GUI and the CLI executables."""

import multiprocessing
import os
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    # Windowed builds have no console: give libraries harmless streams.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    from textrepairo.cli import main

    raise SystemExit(main())
