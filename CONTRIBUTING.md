# Contributing

Thanks for helping. TextRepairo is GPL-3.0-or-later with the additional terms in [ADDITIONAL_TERMS.md](ADDITIONAL_TERMS.md); by contributing you agree your changes are released under the same license.

1. Read [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
2. `pip install -e ".[dev,desktop]"` and make `python -m pytest` pass before and after your change.
3. Prompt or model changes need before/after numbers from `eval/run_eval.py`. Add a case for each bug you fix.
4. Only add models with a permissive license (Apache-2.0 or MIT) confirmed on the official model card.
5. Keep the app offline: no telemetry. The only network use is the optional update check and downloads the user starts (see [PRIVACY.md](PRIVACY.md)). A change that adds a request must update PRIVACY.md and docs/THREAT_MODEL.md.
6. Keep the UI accessible: keyboard operable, visible focus, contrast in both themes, no external fonts or scripts. Controls are custom (see `web/ui.js`); do not add native `<select>`, `alert()`, `confirm()` or `title=` tooltips (a test checks this).
7. Add the header to new source files: `SPDX-License-Identifier: GPL-3.0-or-later` and `Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs` (or your own name for your own files).
8. **Slang packs:** edit the JSON in `src/textrepairo/data/packs/` (format in [docs/PACKS.md](docs/PACKS.md)). Write entries from your own knowledge. Do not copy from copyrighted dictionaries.

Good first issues: more slang pack entries (especially Hindi and Marathi, reviewed by a native speaker), more eval cases for your language, translations of the UI, a Linux native window.
