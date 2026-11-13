# Security and privacy

## Design

- The app server binds to `127.0.0.1` only. Every `/api/*` request needs a per-launch random token, and requests with a foreign `Host` header are rejected (protects against DNS-rebinding from web pages).
- The model server (`llama-server`) also binds to `127.0.0.1`, on a random port, with a random API key that only the app knows.
- Your text is sent only to those local processes. There is no telemetry, no analytics and no update check.
- Network access happens only when you press a download button: model files from `huggingface.co` and engine binaries from `github.com/ggml-org/llama.cpp` releases. Model files are verified against a pinned SHA-256 before use. Engine archives are extracted with path-traversal checks.
- Pasted text is wrapped as data in the prompt, so instructions inside it are not followed. This reduces, but cannot completely rule out, prompt-injection effects with small models. Always review the result.
- Imported `.gguf` files are loaded by llama.cpp. Only import models from sources you trust.

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security tab > Report a vulnerability) rather than a public issue.
