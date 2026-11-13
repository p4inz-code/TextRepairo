# Third-party notices

TextRepairo is licensed under the GNU GPL v3 or later. It uses, downloads or was informed by the following projects. All listed licenses are compatible with GPLv3.

## Components bundled or downloaded by the app

| Component | Use | License |
|---|---|---|
| [llama.cpp](https://github.com/ggml-org/llama.cpp) (`llama-server`, ggml) | Local inference engine; prebuilt release binaries (pinned tag in `src/textrepairo/runtime.py`) | MIT |
| [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) | Lite model (GGUF by [Unsloth](https://huggingface.co/unsloth/Qwen3-1.7B-GGUF)) | Apache-2.0 |
| [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) | Standard model (GGUF by [Unsloth](https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF)) | Apache-2.0 |
| [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) | Pro model (official [GGUF](https://huggingface.co/Qwen/Qwen3-8B-GGUF)) | Apache-2.0 |

Models are downloaded by the user on request and are not part of the source repository. The model licenses were read from the official model cards when each model was added; re-check them when you change the registry in `src/textrepairo/models.py`.

## Python dependencies

| Package | License |
|---|---|
| [FastAPI](https://github.com/fastapi/fastapi) | MIT |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause |
| [HTTPX](https://github.com/encode/httpx) | BSD-3-Clause |
| [platformdirs](https://github.com/tox-dev/platformdirs) | MIT |
| [pywebview](https://github.com/r0x0r/pywebview) (desktop window) | BSD-3-Clause |
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) (build only) | GPL-2.0-or-later with the bootloader exception |
| [Pillow](https://github.com/python-pillow/Pillow) (icon generation, build only) | HPND |
| [cyclonedx-bom](https://github.com/CycloneDX/cyclonedx-python) (release SBOM, build only) | Apache-2.0 |
| [pip-audit](https://github.com/pypa/pip-audit) (CI only) | Apache-2.0 |
| Python standard library, including `sqlite3` (history) | PSF License; SQLite is public domain |

## Original work in this repository

- The slang and context packs (`src/textrepairo/data/packs/`), the prompt wording, the "write like a person" rules and the evaluation cases are original work of the TextRepairo authors, released under the project license. They were written from the authors' own knowledge. No text was copied from Urban Dictionary, other online dictionaries or the humanizer skill. That skill's description of common AI-writing patterns (itself based on observations published by Wikipedia editors, "Signs of AI writing") informed which kinds of phrases to avoid. The short pattern list in `src/textrepairo/humanize.py` was written independently.
- The additional terms in ADDITIONAL_TERMS.md follow the pattern used by the author's other project, kinoz.

## Ideas and patterns referenced

- The sidecar pattern (spawn `llama-server` on loopback, talk OpenAI-compatible HTTP) follows the approach documented by llama.cpp and used by desktop apps such as [Liquid AI's desktop guide](https://docs.liquid.ai/deployment/on-device/llama-cpp/desktop).
- Findings on small-model grammar correction come from [Exploring the Feasibility of Multilingual GEC with a Single LLM up to 9B](https://arxiv.org/abs/2505.06004). No code or data from it is included.
- Models that were evaluated and **not** shipped because their license is not permissive: Gemma (Google terms), Llama (Meta community license), CoEdIT (CC-BY-NC-4.0).
