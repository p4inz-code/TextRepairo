# Threat model

What TextRepairo protects, from whom, and how. Keep this file honest: if a defense is weaker than it sounds, say so.

## What matters
1. **Your text** (it can be private: emails, notes, messages).
2. **Your computer** (the app must not become a way into it).
3. **The integrity of what you run** (the app, the engine, the models).

## Parts and trust boundaries

```
[App window or browser tab]  --HTTP, loopback, session cookie-->  [TextRepairo server, Python]
                                                                          |
                                                      HTTP, loopback, random API key
                                                                          v
                                                               [llama-server (llama.cpp)]
                                                                          |
                                                                   [GGUF model file]
```

Optional network: update check (GitHub API), model download (Hugging Face), engine download (GitHub releases).

## Threats and defenses

| # | Threat | Defense | Residual risk |
|---|---|---|---|
| T1 | Another computer on the network uses the server | Binds to 127.0.0.1 only; Doctor checks the port is not reachable on the PC's other addresses | None known |
| T2 | A web page in your browser talks to the local server (CSRF, DNS rebinding) | Loopback `Host` check, SameSite=Strict HttpOnly cookie, `Origin` check on writes, `Sec-Fetch-Site` check, no CORS headers | A local program running as you can read the cookie file. That is outside this model |
| T3 | Another local program uses the engine port | Random port and random API key per launch | A program running as the same user could read process memory |
| T4 | Script injection into the interface | Strict CSP (no inline code), no `innerHTML`, tests enforce it | None known |
| T5 | Pasted text hijacks the model (prompt injection) | Text sent as data, reminder after the text, injection examples in every style, output checks, a test set of 34 injection cases that is run against the real model | Small models can still be fooled. Output is for the user to review, and the model has no tools or network access, so the worst case is a wrong text, not an action |
| T6 | Tampered model download | Pinned SHA-256 per model; Doctor can re-verify | Imported custom models are not verified |
| T7 | Tampered engine download | Pinned SHA-256 per release asset; unknown assets refused; path-traversal checks on extraction | A compromise of the pinned upstream release before pinning would not be seen |
| T8 | Fake or tampered update | Installer must match `SHA256SUMS.txt` from the same release; download URLs must be under the project's GitHub releases; update address cannot be redirected except to loopback in test mode | The checksum comes from the same place as the file, so a compromised GitHub account could ship a bad update. Mitigation: provenance attestations let careful users verify. No code signing |
| T9 | Text left behind on disk | History capped at 100, secure delete, Private mode, Forget on exit, no text in logs | Text can remain in the operating system's swap file, backups or SSD wear-leveling, which an app cannot control |
| T10 | Malicious slang pack | Strict validation; pack text is data; only matched entries (max 20) are used | A pack can nudge the model's reading of a word. Only import packs you trust |
| T11 | Malicious GGUF file | Only user-imported; documented warning | llama.cpp parses the file. Only import models from trusted sources |
| T12 | Supply chain (dependencies, build) | Pinned actions, Dependabot, pip-audit, CodeQL, SBOM, attestations | Normal open-source risk |

## Out of scope
An attacker who already controls your user account or your operating system. Physical access to an unlocked computer. Side channels.

## Review checklist for changes
- Does this add a network request? Update PRIVACY.md and this file.
- Does this add something the server accepts? Validate size, shape and origin.
- Does the interface build HTML from text? Don't. Use `textContent`.
- Does this log or store user text? Don't, unless it is the history feature.
