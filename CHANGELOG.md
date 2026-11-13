# Changelog

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
