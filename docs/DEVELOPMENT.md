# Development guide

## Layout

```
src/textrepairo/
  prompts.py     styles x formality, human-voice rules, compose targets (PROMPT_VERSION)
  humanize.py    stock-AI-phrase score and the safe clean-up pass
  packs.py       slang/context packs: load, validate, match, import
  textproc.py    chunking, protected spans, output cleanup, checks, diff (pure functions)
  progress.py    honest progress math (weights, caps, monotonic, time left)
  engine.py      streams text through llama-server, emits progress, restores spans, runs checks
  runtime.py     find/download the llama.cpp binary (SHA-256 pinned), start/stop llama-server
  models.py      model registry (Apache-2.0 only), resumable download + SHA-256, import
  history.py     local history (SQLite, newest 100, secure delete)
  updater.py     optional update check, verified download, silent install (Windows installer builds)
  doctor.py      diagnostics shared by Settings > Doctor and `textrepairo doctor`
  config.py      paths, portable mode, settings, safe-mode session marker, limits
  hardware.py    RAM / GPU detection (no extra dependencies)
  server.py      FastAPI: /api/* (cookie + Origin + Host checks), CSP, static web UI
  app.py         desktop launcher (pywebview window, or the default browser)
  cli.py         command line
  data/packs/    built-in slang packs (JSON)
  web/           index.html, style.css, ui.js (components), app.js (no build step, system fonts only)
eval/            cases.jsonl + run_eval.py (quality harness)
packaging/       PyInstaller spec, entry point, Inno Setup script, icons
scripts/         build_app.py, package_linux.sh, smoke_dist.py, make_icons.py
tests/           fast tests using a fake llama-server (no model needed)
docs/plans/      planning documents, progress and decisions logs
docs/audits/     audit reports per release
```

## Common tasks

```bash
python -m pytest                       # unit and API tests, seconds, no model
python -m textrepairo serve            # run the UI at a local address
python eval/run_eval.py --model lite --threads 4 --limit 10 --pause 2   # gentle quality run
python scripts/build_app.py            # standalone app in dist/TextRepairo
python scripts/smoke_dist.py dist/TextRepairo/textrepairo-cli.exe
```

Use `TEXTREPAIRO_HOME=/some/folder` to keep dev models and settings away from your real data folder.

## Keeping the machine cool

Inference is the only heavy work. `llama-server` is started at below-normal priority with `min(8, cores/2)` threads. For experiments set `threads` in `settings.json` (or `--threads` in the eval script), use the Lite model, and add `--pause` between eval cases.

## Changing a prompt

1. Edit `prompts.py` and bump `PROMPT_VERSION`.
2. Run `eval/run_eval.py` on the cases for the styles you touched plus the `injection` cases, before and after, and compare the summary (pass counts and the AI-voice score; lower is better).
3. Add a case to `eval/cases.jsonl` for every bug you fix.

## Adding a model

Add a `ModelSpec` in `models.py` with the exact file size and SHA-256 (Hugging Face shows both), confirm the license on the **official** model card, add it to `THIRD_PARTY_NOTICES.md`, then run the eval. Only Apache-2.0 or MIT models belong in the registry.

## Upgrading llama.cpp

Change `LLAMA_CPP_TAG` in `runtime.py`, check the asset names in `asset_names()` still exist on that release, and replace every entry in `ASSET_SHA256` with the new digests (`gh api repos/ggml-org/llama.cpp/releases/tags/<tag>`, field `digest` of each asset). Then run `scripts/build_app.py` and the smoke test.

## Releasing

1. Update `__version__` in `src/textrepairo/__init__.py` and add `docs/release-notes/vX.Y.Z.md`.
2. Commit, then `git tag vX.Y.Z && git push origin main vX.Y.Z`.
3. The `Release` workflow builds Windows, macOS and Linux, smoke-tests each, and publishes the GitHub release with checksums, a software bill of materials and build attestations. The auto-updater reads `TextRepairo-Setup-<version>.exe` and `SHA256SUMS.txt` from the release, so keep those names.

## Testing the updater locally

Point the app at a fake release server on loopback: `TEXTREPAIRO_TEST_UPDATE_API=http://127.0.0.1:<port>/releases/latest`. Only loopback addresses are honored. `tests/test_updater_config_cli.py` contains a complete fake server.

## Portable mode

Place an empty file named `portable.flag` next to the app (or next to the `.AppImage`). Models, settings and history then live in a `data` folder beside it.
