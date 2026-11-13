# A6 License audit (v0.2)

Question: can everything in this release be distributed under GPL-3.0-or-later with the additional terms, and are all notices present?

## Project license
- `LICENSE` is the GNU GPL v3. `ADDITIONAL_TERMS.md` adds the section 7 terms (credit stays, modified versions are marked, the name is reserved), in the same form as the author's kinoz project. Both are linked from the README, the About screen (Settings > About > License / Additional terms) and `THIRD_PARTY_NOTICES.md`.
- Every source file in `src`, `tests`, `scripts`, `eval`, `packaging` and every file in `src/textrepairo/web` carries `SPDX-License-Identifier: GPL-3.0-or-later` and the copyright line "Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs". Enforced by `test_source_files_carry_license_headers` and `test_every_web_file_has_license_header`.
- The credit line is the same everywhere (`test_credit_line_is_consistent`); the brand is "P4inz Interactive Labs", not "Int Labs".

## Models (checked again on 2026-11-13 against the Hugging Face model pages)
| Model | Repository | License on the page |
|---|---|---|
| Lite, Qwen3 1.7B | `Qwen/Qwen3-1.7B`, GGUF `unsloth/Qwen3-1.7B-GGUF` | Apache-2.0 |
| Standard, Qwen3 4B Instruct 2507 | `Qwen/Qwen3-4B-Instruct-2507`, GGUF `unsloth/Qwen3-4B-Instruct-2507-GGUF` | Apache-2.0 |
| Pro, Qwen3 8B | `Qwen/Qwen3-8B`, GGUF `Qwen/Qwen3-8B-GGUF` | Apache-2.0 |

`test_registry_is_sane` fails if a model in the registry has any other license. Models are not part of the repository or the installers; the user downloads them. Gemma, Llama and CoEdIT stay excluded (non-permissive terms).

## Engine
llama.cpp, MIT (GitHub license metadata checked). The pinned release assets are bundled in the packaged app (CPU or Metal build) and downloaded by checksum for GPU builds. The release archive carries only the LLVM OpenMP license file, not llama.cpp's own MIT license, so the full MIT text (copyright "The ggml authors") is now included at the end of `THIRD_PARTY_NOTICES.md`, which the app bundles and shows in About.

## Python dependencies (installed closure of the runtime packages)
All permissive and GPL-compatible: MIT (fastapi, pydantic, pydantic-core, anyio, platformdirs, annotated-types, annotated-doc, typing-inspection, bottle, proxy-tools, pythonnet, clr-loader, h11), BSD-3-Clause (uvicorn, httpx, httpcore, starlette, idna, click, pycparser, pywebview), Apache-2.0 (opentelemetry-api, inert interface only), MPL-2.0 (certifi), PSF-2.0 (typing-extensions), MIT-0 (cffi). Build and CI tools: PyInstaller (GPL-2.0-or-later with the bootloader exception, which allows any license for the built app), Pillow (HPND), cyclonedx-bom and pip-audit (Apache-2.0). Listed in `THIRD_PARTY_NOTICES.md`.

`opentelemetry-api` comes with FastAPI. No SDK or exporter is installed, so nothing is collected or sent. `test_no_telemetry_packages_are_installed` and `test_only_known_hosts_appear_in_the_source` keep it that way.

## Original content created for 0.2
- Slang packs (`en-slang` 149 entries, `hinglish-roman` 175, `marathi-roman` 101): written from the authors' own knowledge. **No text was copied from Urban Dictionary, other online dictionaries or the humanizer skill.** The Hindi, Hinglish and Marathi lists are seed lists awaiting review by a native speaker (this is stated in the pack files and in `docs/PACKS.md`).
- "Write like a person" rules and the stock-phrase list (`humanize.py`): our own wording. The humanizer skill (a list of common AI-writing patterns, itself based on Wikipedia editors' observations) informed which kinds of phrases to avoid. No sentences from it are reproduced, so no share-alike obligation arises.
- Prompts, few-shot examples and the 161 evaluation cases: original.
- Screenshots in `docs/` are of this app showing made-up sample text.

## Findings
1. `THIRD_PARTY_NOTICES.md` did not list the full dependency closure, and did not contain the llama.cpp MIT license text that the bundled binaries require. Both added.
2. The About screen read documents from the repository root only; the packaged app now bundles `LICENSE`, `ADDITIONAL_TERMS.md`, `PRIVACY.md`, `SECURITY.md` and `THIRD_PARTY_NOTICES.md` (the smoke test fails if any is missing from the build).

## Not verified
The GGUF files are repackaged by Unsloth; their pages state Apache-2.0, the same as the original models. Their conversion pipeline was not audited. This audit is not legal advice.
