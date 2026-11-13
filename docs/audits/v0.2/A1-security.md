# A1 Security audit (v0.2)

Scope: the local server, the interface, the engine launch, downloads, the updater, dependencies and secrets. Method: automated tests, a header check against a running server, dependency audit, secret scan, and a review against [docs/THREAT_MODEL.md](../../THREAT_MODEL.md).

## Results

| # | Check | How it was checked | Result |
|---|---|---|---|
| 1 | Server listens on loopback only | Doctor "Network exposure" connects to the PC's other addresses; `netstat` inventory (see A2) | Pass |
| 2 | Wrong or missing session is refused | `test_wrong_cookie_is_refused`, `test_bad_launch_token_is_refused`, `test_api_requires_token` | Pass |
| 3 | Launch token becomes an HttpOnly, SameSite=Strict cookie and leaves the address | `test_launch_token_becomes_http_only_cookie`; packaged-app smoke test checks the same | Pass |
| 4 | Foreign `Host` header refused (DNS rebinding) | `test_rejects_foreign_host` | Pass |
| 5 | Cross-origin and cross-site writes refused | `test_cross_origin_writes_are_blocked` | Pass |
| 6 | Strict CSP, `nosniff`, `no-referrer`, `no-store`, `X-Frame-Options` on pages and API | `test_security_headers_on_pages_and_api`, `test_csp_forbids_inline_script_and_style` | Pass |
| 7 | Interface has no inline code, `innerHTML`, `eval`, native dialogs | `tests/test_web_static.py` (static scan of HTML and JS) | Pass |
| 8 | Request size capped, including chunked bodies without a length | `test_oversized_body_is_refused`, `test_chunked_oversized_body_is_refused` | Pass (this audit found that the first version only checked `Content-Length`; a streaming size limit was added) |
| 9 | Text length capped at 10,000 characters by the server | `test_repair_limit_is_enforced_by_the_server` | Pass |
| 10 | One repair at a time | Engine lock (`Engine._repair_lock`), exercised by every engine test | Pass |
| 11 | Prompt injection | 34 injection cases against the real model, plus wrapper-tag masking (`</text>` in user text is masked) | See A5. This audit found two real failures in the first run (`</text>` breakout and a short "reply with only OK" command); both were fixed and re-tested |
| 12 | Engine archives verified by pinned SHA-256; unknown assets refused; path traversal refused | `test_every_runtime_asset_is_pinned`, `test_verify_asset_accepts_match_and_rejects_everything_else`, zip and tar traversal tests | Pass (this audit found that v0.1 did not verify engine downloads; it does now) |
| 13 | Model downloads verified by pinned SHA-256 | Existing model tests; Doctor "Verify model" re-hashes the real file | Pass (checked: the installed Standard model matches its published checksum) |
| 14 | Updater: checksum mismatch deletes the file and installs nothing | `test_bad_checksum_deletes_the_file_and_installs_nothing` | Pass |
| 15 | Updater: only project URLs; update address cannot be redirected except to loopback in test mode | `test_download_refuses_foreign_urls`, `test_test_override_is_loopback_only` | Pass |
| 16 | Updater: oversized download refused | `test_oversized_update_is_refused` | Pass |
| 17 | Updater: pending ("Later") update re-verified before install | `test_pending_update_installs_next_launch_only_when_verified` | Pass |
| 18 | Only project links can be opened from the app window | `test_only_project_links_open_externally` (including look-alike host names) | Pass |
| 19 | Slang packs validated (size, shape, length, control characters, id clash) | `tests/test_packs_prompts.py` | Pass |
| 20 | Dependency vulnerabilities | `pip-audit` on the dev environment after upgrading setuptools and pip: "No known vulnerabilities found". CI runs it on every push | Pass |
| 21 | Secrets in the tree and in all git history | Regex scan for tokens, private keys, API-key assignments across all commits | None found |
| 22 | No private details in tracked files | `test_no_private_details_in_tracked_text_files` | Pass |
| 23 | Commit identity | All commits use the GitHub no-reply address | Pass |
| 24 | Safe mode after two abnormal exits | `test_safe_mode_after_two_bad_exits`; also seen live when the test server was killed twice | Pass |

## Findings fixed during the audit
1. Engine downloads were not verified (v0.1). Fixed with pinned checksums.
2. The first body-size limit missed chunked uploads. Fixed with a streaming limit.
3. `</text>` inside pasted text could close the data block and the model then obeyed the text that followed. Fixed by masking wrapper tags like links and code.
4. Phone numbers, dates and times could be altered by the model. Fixed by masking them.

## Accepted risks (also in the threat model)
- Updates are integrity-checked by SHA-256 from the same release page (decision: no signing key). A compromised GitHub account could publish a bad update. Mitigation: build attestations and an SBOM.
- Prompt injection against a small model cannot be ruled out. The model has no tools and no network, so the worst case is a wrong text that the user reviews.
- The Windows and macOS builds are not code-signed.
