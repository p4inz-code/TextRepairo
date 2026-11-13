# A9 Release audit (v0.2)

| Check | Result |
|---|---|
| Full test suite (191 tests) | Pass locally; CI on Windows, macOS and Linux with Python 3.10 and 3.12 passed on the branch |
| Packaged Windows app built (PyInstaller, 145 MB) | Pass |
| Packaged smoke test: version, Doctor, session cookie, CSP, styles, packs, bundled license documents, status | `SMOKE OK` |
| Windows installer built (Inno Setup, 53 MB, per user) | Pass |
| Silent install to a scratch folder, no administrator prompt | Pass |
| **Self-update end to end** with the real installer and a local fake release server: update found, 56 MB downloaded with 101 real progress steps, SHA-256 verified, installer launched silently, old app closed, installer ran | `E2E OK` (`scripts/e2e_update_windows.py`) |
| Portable mode on the packaged build (`portable.flag` puts data in `data` next to the app) | Pass |
| Engine processes after exit | none left |
| Checksums, SBOM and attestation on the published release | Verified after publishing; see SUMMARY |

Not done: running the macOS and Linux builds on real machines; a screen-reader pass; the native window was not driven by an automated UI test (the same web interface was tested in a browser).
