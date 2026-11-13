# Contributing

Thanks for helping. TextRepairo is GPL-3.0-or-later; by contributing you agree your changes are released under the same license.

1. Read [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
2. `pip install -e ".[dev,desktop]"` and make `python -m pytest` pass before and after your change.
3. Prompt or model changes need before/after numbers from `eval/run_eval.py`. Add a case for each bug you fix.
4. Only add models with a permissive license (Apache-2.0 or MIT) confirmed on the official model card.
5. Keep the app offline: no telemetry, no background network calls. Network is only for explicit user-triggered downloads.
6. Keep the UI accessible: keyboard operable, visible focus, contrast in both themes, no external fonts or scripts.

Good first issues: more eval cases for your language, translations of the UI, a Windows/macOS code-signing setup, a Linux native window.
