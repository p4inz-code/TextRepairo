# Security

## Design

- The app server binds to `127.0.0.1` only. Requests whose `Host` header is not a loopback name are rejected (this stops DNS-rebinding from web pages).
- The launch link carries a random token. The server swaps it for an **HttpOnly, SameSite=Strict session cookie** holding a separate random session id, and redirects, so the token never stays in the address bar, the browser history or page scripts. In the native window the link works exactly once, so a copy of it (for example from a console) is useless afterwards. In the browser fallback and `textrepairo serve` it can be reused so you can open a second tab. Every `/api/*` call needs that cookie (scripts may send the token as an `X-Token` header). Writes must carry a matching `Origin`, and cross-site requests are refused.
- Every response carries a strict **Content-Security-Policy** (scripts and styles only from the app itself, no inline code, no framing), `nosniff`, `no-referrer` and `no-store`. A test fails the build if the interface ever uses inline scripts, `innerHTML`, `eval` or native browser dialogs.
- Request bodies are capped, the text length is capped (10,000 characters), and only one repair runs at a time.
- The model server (`llama-server`) also binds to `127.0.0.1`, on a random port, with a random API key that only the app knows. It runs at below-normal priority and is stopped when the app exits.
- Your text is sent only to those local processes. There is no telemetry, no analytics and no crash reporting. The app never logs your text.
- **Network use** is limited to: the optional update check (see [PRIVACY.md](PRIVACY.md)), and downloads you start yourself. Model files are verified against a pinned SHA-256 before use. The llama.cpp engine archives are verified against pinned SHA-256 values for the exact release (`ASSET_SHA256` in `src/textrepairo/runtime.py`); an unknown or mismatching file is deleted and refused. Archives are extracted with path-traversal checks.
- **Updates** are installed only if the downloaded file matches the SHA-256 published in `SHA256SUMS.txt` on the same GitHub release. This proves the file arrived intact. It does **not** prove who published it: anyone who controls the release page controls both files. Releases are also published with GitHub build attestations and a software bill of materials so technical users can verify where a file came from.
- Pasted text is wrapped as data in the prompt, repeated back with a reminder after the text, and checked after the model answers. Slang pack text is treated as data too, and user packs are validated (size, shape, length, no control characters). This reduces, but cannot completely rule out, prompt-injection effects with small models. Always review the result.
- Imported `.gguf` files are loaded by llama.cpp. Only import models from sources you trust.
- History is stored in a local SQLite file with `secure_delete`, so deleted text is overwritten. See [PRIVACY.md](PRIVACY.md).

More detail: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## Supply chain

- GitHub Actions are pinned to commit hashes. Dependabot watches Python packages and actions. CI runs `pip-audit`, and CodeQL scans Python and JavaScript.
- Each release lists a SHA-256 for every file, a CycloneDX software bill of materials and a build provenance attestation.

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security tab > Report a vulnerability) rather than a public issue.
