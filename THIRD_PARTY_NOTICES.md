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

## Ideas and patterns referenced

- The sidecar pattern (spawn `llama-server` on loopback, talk OpenAI-compatible HTTP) follows the approach documented by llama.cpp and used by desktop apps such as [Liquid AI's desktop guide](https://docs.liquid.ai/deployment/on-device/llama-cpp/desktop).
- Findings on small-model grammar correction come from [Exploring the Feasibility of Multilingual GEC with a Single LLM up to 9B](https://arxiv.org/abs/2505.06004). No code or data from it is included.
- Models that were evaluated and **not** shipped because their license is not permissive: Gemma (Google terms), Llama (Meta community license), CoEdIT (CC-BY-NC-4.0).
