# Releasing

1. Work on a branch, open a pull request, and wait for CI (tests on Windows, macOS and Linux, dependency audit) to pass.
2. Update `__version__` in `src/textrepairo/__init__.py`, `CHANGELOG.md`, and add `docs/release-notes/vX.Y.Z.md`.
3. Run the evaluation (`eval/run_eval.py`, throttled) and compare with the previous release. A drop in passes or a higher AI-voice score blocks the release (see `docs/audits/`).
4. Build and smoke-test the Windows app locally: `python scripts/build_app.py`, `python scripts/smoke_dist.py dist/TextRepairo/textrepairo-cli.exe`, and for the updater `python scripts/e2e_update_windows.py dist/TextRepairo-Setup-X.Y.Z.exe`.
5. Merge to `main`, then `git tag vX.Y.Z && git push origin vX.Y.Z`. The Release workflow builds all platforms, publishes the assets with `SHA256SUMS.txt`, a software bill of materials and build attestations.
6. Check the release page: every asset is present, the checksums match, and the notes read well. The auto-updater needs `TextRepairo-Setup-<version>.exe` and `SHA256SUMS.txt` with those exact names.
7. Write an audit summary in `docs/audits/vX.Y/`.
