# Development guide

## Layout

```
src/textrepairo/
  prompts.py     prompt templates per mode (PROMPT_VERSION)
  textproc.py    chunking, protected spans, output cleanup, checks, diff (pure functions)
  engine.py      streams text through llama-server, restores spans, runs checks
  runtime.py     find/download the llama.cpp binary, start/stop llama-server (loopback + API key)
  models.py      model registry (Apache-2.0 only), resumable download + SHA-256, import
  hardware.py    RAM / GPU detection (no extra dependencies)
  server.py      FastAPI: /api/* (token + Host check) and the static web UI
  app.py         desktop launcher (pywebview window, or the default browser)
  cli.py         command line
  web/           index.html, style.css, app.js (no build step, system fonts only)
eval/            cases.jsonl + run_eval.py (quality harness)
packaging/       PyInstaller spec, entry point, Inno Setup script, icons
scripts/         build_app.py, package_linux.sh, smoke_dist.py, make_icons.py
tests/           fast tests using a fake llama-server (no model needed)
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
2. Run `eval/run_eval.py` on at least `fix`, `formal` and the `injection` cases before and after; compare the summary.
3. Add a case to `eval/cases.jsonl` for every bug you fix.

## Adding a model

Add a `ModelSpec` in `models.py` with the exact file size and SHA-256 (Hugging Face shows both), confirm the license on the **official** model card, add it to `THIRD_PARTY_NOTICES.md`, then run the eval. Only Apache-2.0 or MIT models belong in the registry.

## Upgrading llama.cpp

Change `LLAMA_CPP_TAG` in `runtime.py`, check the asset names in `asset_names()` still exist on that release, run `scripts/build_app.py` and the smoke test.

## Releasing

1. Update `__version__` in `src/textrepairo/__init__.py` and add `docs/release-notes/vX.Y.Z.md`.
2. Commit, then `git tag vX.Y.Z && git push origin main vX.Y.Z`.
3. The `Release` workflow builds Windows, macOS and Linux, smoke-tests each, and publishes the GitHub release with checksums.
