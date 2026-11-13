# Changelog

## 0.2.0

Smarter, safer, and written to sound like a person.

**New**
- **Real progress bar.** It shows the real percentage, the part you are on ("part 3 of 7"), speed and an estimated time left. Reading your text uses the engine's own counters. Writing is an estimate, so it never shows 100% before the result is really done. Loading the model shows elapsed seconds instead of a made-up percentage.
- **Eleven writing styles:** Fix, Professional (the old Formal), Friendly, Prompt, Compose, Message, Email, Casual, Concise, Persuasive, Empathetic. **Three formality levels** (Normal, Advanced, Extremely formal) for the styles where it makes sense.
- **Compose:** turn scattered notes or keywords into a finished message, prompt or structured prompt. It never invents facts; gaps become `[placeholders]`.
- **Natural by default.** Every style follows "write like a person" rules, and a small safety net removes stock AI phrases (and em dashes) the author did not write.
- **History** of your last 100 results, on this computer only. Private mode, Forget on exit, delete one or clear all. Deleted text is overwritten.
- **Slang packs:** English chat shorthand and slang, Hindi/Hinglish and Marathi written in English letters. Add your own (see docs/PACKS.md).
- **Doctor** (Settings > Doctor, `textrepairo doctor`): checks the engine, model (with checksum verification and a real progress bar), data folder, history, packs and that the server is not reachable from the network.
- **About** screen with credits, licenses and links.
- **Portable mode:** the Windows zip and the Linux tar.gz keep models, settings and history next to the app.
- **Optional auto-update** (Automatic, Notify me or Off), checked against the published SHA-256. Windows installer builds can install themselves.
- **Text limit** of 10,000 characters per repair, with a live counter.
- **CLI:** `--formality`, `--json`, several `-f` files with `--out-dir`, real progress on the terminal, `--private`, `history`, `packs`, `update`, `doctor --json`.

**Interface**
- Every control is drawn by the app: dropdowns, switches, dialogs, drawers, tooltips, context menus and scrollbars, all keyboard operable.

**Security**
- The launch token becomes an HttpOnly, SameSite=Strict session cookie. Strict Content-Security-Policy, Origin checks, request size limits, one repair at a time.
- llama.cpp engine downloads are now verified against pinned SHA-256 values.
- CI runs `pip-audit` and CodeQL. Releases include a software bill of materials and build attestations.

**Changed**
- The Windows installer installs for the current user (no administrator prompt). If you installed 0.1.0 for all users, uninstall it first.
- The portable Windows file is now `TextRepairo-<version>-windows-x64-portable.zip`.
- The privacy text now says plainly that the only network use is the optional update check and downloads you start yourself.

**Known limits**
- Output is English only. Hindi, Marathi and Hinglish output are planned (see ROADMAP.md). Typed Hinglish and Marathi input is understood better thanks to the packs.
- The builds are not code-signed. macOS and Linux builds are tested by CI only.

## 0.1.0

First public release.

- Four styles: Fix, Formal, Friendly, Prompt. Any language in, English out.
- Local AI with llama.cpp and Apache-2.0 Qwen3 models (Lite 1.7B, Standard 4B, Pro 8B), one-time download with resume and SHA-256 check, or import your own `.gguf`.
- Desktop app (native window, browser fallback), web UI and CLI.
- Changes view (word diff), warnings for dropped numbers or odd output, protected links, code and emails.
- Offline and private: loopback-only server, per-launch token, Host check, no telemetry.
- Cool by default: low-priority engine on about half the CPU cores. Optional GPU acceleration (Vulkan; Metal on Apple Silicon).
- Installers and packages for Windows, macOS (Apple Silicon) and Linux.
- Evaluation harness with 60 multilingual cases, including prompt-injection checks.
