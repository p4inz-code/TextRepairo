# TextRepairo

**Write it right.** Paste messy text in any language and get clear, correct English back, in the style you pick. Everything runs on your own computer with a small open AI model. After a one-time model download, no internet is needed and your text never leaves your device.

- **Four styles:** *Fix* (spelling and grammar, keeps your words), *Formal*, *Friendly*, and *Prompt* (turns a rough request into a clear AI prompt).
- **Any language in, English out:** broken English, Hinglish, Hindi, Spanish, German, Chinese and 100+ more.
- **Private and offline:** no accounts, no telemetry, no cloud. The local server only listens on `127.0.0.1` and needs a per-launch token.
- **Review before you copy:** a *Changes* view shows exactly what was edited, and warnings flag dropped numbers or odd output.
- **Cool and quiet:** the engine runs at low priority and uses about half your CPU cores by default.
- **Desktop app, web UI and CLI** from the same code.
- **Free software:** GNU GPL v3 or later.

<p align="center">
  <img src="docs/screenshot-light.jpg" alt="TextRepairo fixing a sentence, light theme" width="49%">
  <img src="docs/screenshot-dark.jpg" alt="TextRepairo dark theme" width="49%">
</p>

## Install

Download the file for your system from the [latest release](https://github.com/p4inz-code/TextRepairo/releases/latest):

| System | File |
|---|---|
| Windows 10/11 | `TextRepairo-Setup-<version>.exe` (installer) or `TextRepairo-<version>-windows-x64.zip` (portable) |
| macOS (Apple Silicon) | `TextRepairo-<version>-macos-arm64.dmg` |
| Linux (x64) | `TextRepairo-<version>-linux-x64.AppImage`, `.deb`, or `.tar.gz` |

On first launch the app guides you through downloading a language model (one time):

| Tier | Model | Size | Good for |
|---|---|---|---|
| Lite | Qwen3 1.7B | about 1.1 GB | old laptops (4 GB RAM) |
| **Standard** | Qwen3 4B Instruct 2507 | about 2.5 GB | most computers, runs fine on a CPU |
| Pro | Qwen3 8B | about 5 GB | a GPU with 8 GB VRAM, or 16 GB RAM |

Already offline? Choose **I already have a model file** and import any `.gguf` file, or copy one into the models folder shown in Settings.

**Unsigned builds.** The releases are not code-signed yet, so your system may warn you. On Windows choose *More info > Run anyway*. On macOS right-click the app and choose *Open* (or run `xattr -cr /Applications/TextRepairo.app`). Each release lists SHA-256 checksums.

## Use

**Desktop app:** open TextRepairo, pick a style, paste text, press <kbd>Ctrl</kbd>+<kbd>Enter</kbd> (<kbd>⌘</kbd>+<kbd>Enter</kbd> on macOS).

**Command line:**

```bash
textrepairo repair "mujhe kal office jana hai but tabiyat thik nahi" -m formal
echo "i dont know wich one is better" | textrepairo repair -m fix --diff
textrepairo repair -f draft.txt -o fixed.txt -m friendly
textrepairo models list            # see models and which one is active
textrepairo models download pro    # get another tier
textrepairo runtime install --backend vulkan   # optional GPU acceleration
textrepairo serve                  # web UI in your browser, local only
textrepairo doctor                 # diagnostics
```

**GPU acceleration** is optional (Settings > Speed). The default is the CPU, which keeps the machine cool and works everywhere.

## How it works

1. The app starts the official [llama.cpp](https://github.com/ggml-org/llama.cpp) `llama-server` on a random loopback port with a random API key.
2. Your text is split into paragraphs, links/code/emails are protected with placeholders, and each part is sent to the model with a strict prompt that treats your text as data (so pasted instructions are not obeyed).
3. The reply is cleaned (no "Here is the corrected text", no thinking tags), placeholders are restored, sanity checks run, and a word-level diff is produced.

## Build from source

```bash
git clone https://github.com/p4inz-code/TextRepairo
cd TextRepairo
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev,desktop]"
python -m pytest                                   # fast tests, no model needed
textrepairo runtime install                        # downloads llama.cpp
textrepairo models download lite
textrepairo                                        # open the app
```

Build a standalone app with `python scripts/build_app.py` (PyInstaller). See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

Measure quality on your own machine (use `--threads` to keep it cool):

```bash
python eval/run_eval.py --model standard --threads 4 --limit 20
```

## Privacy

TextRepairo contacts the internet only when you press a download button (model files from Hugging Face, engine builds from GitHub Releases). There is no telemetry and no update check. See [SECURITY.md](SECURITY.md).

## License

GNU General Public License v3.0 or later. See [LICENSE](LICENSE). Third-party components and models and their licenses are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Models are licensed by their authors; the built-in choices are Apache-2.0.
