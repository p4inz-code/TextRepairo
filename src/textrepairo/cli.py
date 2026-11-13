# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Command line interface.

    textrepairo                              open the desktop app
    textrepairo repair "text" -m professional --formality advanced
    echo "text" | textrepairo repair -m friendly
    textrepairo repair -f notes.txt -o fixed.txt
    textrepairo repair -f a.txt -f b.txt --out-dir fixed/
    textrepairo serve                        run the local web UI
    textrepairo history list | show ID | clear
    textrepairo packs list | import FILE | remove ID
    textrepairo models list|download|import|remove|use
    textrepairo runtime install
    textrepairo update [--install]
    textrepairo doctor [--json] [--verify-model]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import APP_NAME, COPYRIGHT, __version__
from . import models as models_mod
from .config import MAX_TEXT_CHARS, data_dir, load_settings, save_settings
from .prompts import FORMALITY, STYLE_ALIASES, STYLES, resolve_style

EXIT_OK, EXIT_ERROR, EXIT_USAGE = 0, 1, 2


def _progress_printer(label: str):
    state = {"pct": -1}

    def cb(done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 0
        if pct != state["pct"]:
            state["pct"] = pct
            mb = done / 1024 / 1024
            print(f"\r{label}: {pct:3d}%  ({mb:,.0f} MB)", end="", file=sys.stderr, flush=True)

    return cb


def _bar(pct: float | None, width: int = 24) -> str:
    if pct is None:
        return "-" * width
    n = int(width * pct / 100)
    return "#" * n + "-" * (width - n)


def _fmt_eta(seconds: float | None) -> str:
    if seconds is None:
        return ""
    if seconds < 60:
        return f"about {max(1, round(seconds))} s left"
    return f"about {round(seconds / 60)} min left"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="textrepairo",
        description=f"{APP_NAME}: fix messy text in any language into proper English, fully offline.",
        epilog=COPYRIGHT)
    p.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = p.add_subparsers(dest="cmd")

    style_choices = [*STYLES, *STYLE_ALIASES]
    r = sub.add_parser("repair", help="rewrite text (argument, file(s), or stdin)")
    r.add_argument("text", nargs="?", help="text to repair; omit to read stdin")
    r.add_argument("-m", "--mode", "--style", dest="mode", choices=style_choices, default=None,
                   help="writing style (default: your saved default)")
    r.add_argument("--formality", choices=list(FORMALITY), default=None)
    r.add_argument("--target", choices=["message", "prompt", "prompt_structured"], default=None,
                   help="for the compose style: what to write")
    r.add_argument("-f", "--file", action="append", default=[], help="read input from a file (repeatable)")
    r.add_argument("-o", "--output", help="write the result to a file (single input)")
    r.add_argument("--out-dir", help="write results for several input files into this folder")
    r.add_argument("--model", help="model id (lite|standard|pro|custom:<file>) for this run")
    r.add_argument("--diff", action="store_true", help="print a word diff to stderr")
    r.add_argument("--json", action="store_true", help="print the result as JSON")
    r.add_argument("--no-stream", action="store_true", help="print only the final result")
    r.add_argument("--no-progress", action="store_true", help="do not show the progress line")
    r.add_argument("--private", action="store_true", help="do not save this result to history")
    r.add_argument("--max-chars", type=int, default=MAX_TEXT_CHARS,
                   help=f"character limit per input (default {MAX_TEXT_CHARS:,})")

    s = sub.add_parser("serve", help="run the local web UI")
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--no-open", action="store_true", help="do not open a browser")

    sub.add_parser("gui", help="open the desktop app (default)")

    h = sub.add_parser("history", help="saved results")
    hsub = h.add_subparsers(dest="history_cmd", required=True)
    hl = hsub.add_parser("list")
    hl.add_argument("--json", action="store_true")
    hs = hsub.add_parser("show")
    hs.add_argument("id", type=int)
    hsub.add_parser("clear")

    pk = sub.add_parser("packs", help="slang and context packs")
    psub = pk.add_subparsers(dest="packs_cmd", required=True)
    psub.add_parser("list")
    pi = psub.add_parser("import")
    pi.add_argument("path")
    prm = psub.add_parser("remove")
    prm.add_argument("id")

    m = sub.add_parser("models", help="manage models")
    msub = m.add_subparsers(dest="models_cmd", required=True)
    msub.add_parser("list")
    d = msub.add_parser("download")
    d.add_argument("id", choices=[x.id for x in models_mod.REGISTRY])
    i = msub.add_parser("import")
    i.add_argument("path")
    rm = msub.add_parser("remove")
    rm.add_argument("id")
    use = msub.add_parser("use", help="set the default model")
    use.add_argument("id")

    rt = sub.add_parser("runtime", help="manage the llama.cpp engine")
    rtsub = rt.add_subparsers(dest="runtime_cmd", required=True)
    ri = rtsub.add_parser("install")
    ri.add_argument("--backend", default=None, help="cpu | vulkan | cuda | metal (default: auto)")
    rtsub.add_parser("list")

    u = sub.add_parser("update", help="check for a newer version (the only network use besides downloads)")
    u.add_argument("--install", action="store_true", help="download, verify and install it (Windows installer builds)")

    dr = sub.add_parser("doctor", help="check that everything works")
    dr.add_argument("--json", action="store_true")
    dr.add_argument("--verify-model", action="store_true", help="hash the model file (can take a minute)")
    return p


def _read_inputs(args: argparse.Namespace) -> list[tuple[str | None, str]] | None:
    """[(file name or None, text)]"""
    if args.file:
        try:
            return [(f, Path(f).read_text(encoding="utf-8")) for f in args.file]
        except (OSError, UnicodeDecodeError) as e:
            print(f"Error: cannot read input: {e}", file=sys.stderr)
            return None
    if args.text is not None:
        return [(None, args.text)]
    if not sys.stdin.isatty():
        return [(None, sys.stdin.read())]
    print("Nothing to repair. Pass text, --file, or pipe stdin.", file=sys.stderr)
    return None


def cmd_repair(args: argparse.Namespace) -> int:
    from . import history
    from .engine import Engine, EngineError

    inputs = _read_inputs(args)
    if inputs is None:
        return EXIT_USAGE
    if len(inputs) > 1 and args.output:
        print("Use --out-dir (not --output) with several input files.", file=sys.stderr)
        return EXIT_USAGE
    settings = load_settings()
    if args.model:
        settings.model_id = args.model
    mode = resolve_style(args.mode or settings.default_mode)
    formality = args.formality or settings.default_formality
    engine = Engine()
    live = sys.stdout.isatty() and not args.no_stream and not args.output and not args.json \
        and len(inputs) == 1
    show_progress = sys.stderr.isatty() and not args.no_progress

    async def one(name: str | None, text: str) -> dict | None:
        final = None
        printed = ""
        last_line = ""
        try:
            async for ev in engine.stream(text, mode, settings, formality, args.target, args.max_chars):
                if ev["event"] == "partial" and live:
                    new = ev["text"]
                    if new.startswith(printed) and len(new) > len(printed):
                        if show_progress and last_line:
                            print("\r" + " " * len(last_line) + "\r", end="", file=sys.stderr)
                            last_line = ""
                        sys.stdout.write(new[len(printed):])
                        sys.stdout.flush()
                        printed = new
                elif ev["event"] == "progress" and show_progress and not live:
                    if ev.get("phase") == "loading":
                        last_line = f"loading model... {ev['elapsed_s']:.0f} s"
                    else:
                        last_line = (f"[{_bar(ev['pct'])}] {ev['pct']:5.1f}%  part {ev['chunk']}/"
                                     f"{ev['chunks']}  {_fmt_eta(ev.get('eta_s'))}")
                    print("\r" + last_line.ljust(70), end="", file=sys.stderr, flush=True)
                elif ev["event"] == "done":
                    final = ev
        except EngineError as e:
            print(f"\nError{f' ({name})' if name else ''}: {e}", file=sys.stderr)
            return None
        finally:
            if show_progress and last_line:
                print("\r" + " " * 72 + "\r", end="", file=sys.stderr)
        assert final is not None
        final["_printed"] = printed
        return final

    async def run() -> int:
        results: list[tuple[str | None, str, dict]] = []
        try:
            for name, text in inputs:
                res = await one(name, text)
                if res is None:
                    return EXIT_ERROR
                results.append((name, text, res))
        finally:
            await engine.aclose()
            engine.shutdown()
        outputs = []
        for name, text, final in results:
            if history.allowed(settings) and not args.private and final["text"].strip():
                try:
                    history.add(final["mode"], final["formality"], text, final["text"], final["model"],
                                final["seconds"], len(final["warnings"]))
                except Exception:  # noqa: BLE001
                    pass
            if args.output or args.out_dir:
                if args.out_dir:
                    out_dir = Path(args.out_dir)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    src = Path(name) if name else Path("stdin.txt")
                    target = out_dir / f"{src.stem}.repaired{src.suffix or '.txt'}"
                else:
                    target = Path(args.output)
                target.write_text(final["text"], encoding="utf-8")
                outputs.append(str(target))
            elif args.json:
                outputs.append(json.dumps({
                    "file": name, "text": final["text"], "warnings": final["warnings"],
                    "style": final["mode"], "formality": final["formality"], "seconds": final["seconds"],
                    "model": final["model"]}, ensure_ascii=False))
            else:
                printed = final["_printed"]
                if live and final["text"].startswith(printed):
                    sys.stdout.write(final["text"][len(printed):] + "\n")
                elif live:  # streamed text was revised at the end: show the final version
                    sys.stdout.write("\n" + final["text"] + "\n")
                else:
                    sys.stdout.write(final["text"] + "\n")
            for w in final["warnings"]:
                print(f"warning{f' ({name})' if name else ''}: {w}", file=sys.stderr)
            if args.diff:
                line = "".join(
                    f"[-{o['text']}-]" if o["op"] == "del" else f"{{+{o['text']}+}}" if o["op"] == "ins"
                    else o["text"] for o in final["diff"])
                print(line, file=sys.stderr)
        for o in outputs:
            print(o)
        return EXIT_OK

    return asyncio.run(run())


def cmd_history(args: argparse.Namespace) -> int:
    from . import history
    if args.history_cmd == "list":
        entries = history.list_entries()
        if args.json:
            print(json.dumps(entries, ensure_ascii=False, indent=1))
            return EXIT_OK
        import datetime
        for e in entries:
            when = datetime.datetime.fromtimestamp(e["ts"]).strftime("%Y-%m-%d %H:%M")
            print(f"{e['id']:>5}  {when}  {e['style']:<12} {e['input_snippet']}")
        print(f"\n{len(entries)} of {history.HISTORY_LIMIT} saved. Folder: {data_dir()}", file=sys.stderr)
        return EXIT_OK
    if args.history_cmd == "show":
        e = history.get(args.id)
        if not e:
            print("No such entry.", file=sys.stderr)
            return EXIT_ERROR
        print(f"--- input ---\n{e['input']}\n--- {e['style']} / {e['formality']} ---\n{e['output']}")
        return EXIT_OK
    history.clear()
    print("History cleared.", file=sys.stderr)
    return EXIT_OK


def cmd_packs(args: argparse.Namespace) -> int:
    from . import packs
    if args.packs_cmd == "list":
        for p in packs.list_packs():
            print(f"{p['id']:<18} {p['entries']:>5} entries  {p['source']:<8} {p['name']}")
        print(f"\nAdd your own: textrepairo packs import FILE.json (folder: {data_dir() / 'packs'})",
              file=sys.stderr)
        return EXIT_OK
    try:
        if args.packs_cmd == "import":
            p = packs.import_pack(args.path)
            print(f"Imported '{p.id}' ({len(p.entries)} entries).")
        else:
            print("Removed." if packs.remove_pack(args.id) else "No user pack with that id.")
    except packs.PackError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


def cmd_models(args: argparse.Namespace) -> int:
    s = load_settings()
    if args.models_cmd == "list":
        for m in models_mod.list_models():
            mark = "*" if m["id"] == s.model_id else " "
            state = "installed" if m["installed"] else "not downloaded"
            print(f"{mark} {m['id']:<10} {m['name']:<26} {m['size'] / 1e9:5.2f} GB  "
                  f"{m['license']:<12} {state}")
        print(f"\nModels folder: {models_mod.models_dir()}")
        return EXIT_OK
    if args.models_cmd == "download":
        spec = models_mod.get_spec(args.id)
        assert spec
        try:
            models_mod.download_model(spec, _progress_printer(spec.name))
        except models_mod.ModelError as e:
            print(f"\nError: {e}", file=sys.stderr)
            return EXIT_ERROR
        print("\nDone.", file=sys.stderr)
        return EXIT_OK
    if args.models_cmd == "import":
        try:
            p = models_mod.import_model(args.path)
        except models_mod.ModelError as e:
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_ERROR
        print(f"Imported. Use it with: textrepairo models use custom:{p.name}")
        return EXIT_OK
    if args.models_cmd == "remove":
        try:
            models_mod.remove_model(args.id)
        except models_mod.ModelError as e:
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_ERROR
        return EXIT_OK
    if args.models_cmd == "use":
        s.model_id = args.id
        save_settings(s)
        print(f"Default model: {args.id}")
        return EXIT_OK
    return EXIT_USAGE


def cmd_runtime(args: argparse.Namespace) -> int:
    from .engine import Engine
    from .runtime import (asset_names, choose_backend, download_runtime, installed_backends,
                          platform_key)

    if args.runtime_cmd == "list":
        print(f"platform: {platform_key()}  installed: {', '.join(installed_backends()) or 'none'}")
        return EXIT_OK
    backend = args.backend or choose_backend(load_settings().backend, Engine().hw)
    if not asset_names(backend):
        print(f"Backend '{backend}' is not available on {platform_key()}.", file=sys.stderr)
        return EXIT_ERROR
    try:
        path = download_runtime(backend, _progress_printer(f"engine ({backend})"))
    except Exception as e:  # noqa: BLE001
        print(f"\nError: {e}", file=sys.stderr)
        return EXIT_ERROR
    print(f"\nInstalled: {path}", file=sys.stderr)
    return EXIT_OK


def cmd_update(args: argparse.Namespace) -> int:
    from . import updater
    try:
        info = updater.check()
    except updater.UpdateError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR
    updater.record_check()
    if not info["available"]:
        print(f"You are up to date ({__version__}).")
        return EXIT_OK
    print(f"A newer version is available: {info['latest']} (you have {__version__}).\n{info['page_url']}")
    if not args.install:
        return EXIT_OK
    if info["kind"] != "installer":
        print("This build cannot update itself. Download it from the page above.", file=sys.stderr)
        return EXIT_ERROR
    try:
        path = updater.download(info, _progress_printer("update"))
        print("\nVerified. Installing...", file=sys.stderr)
        updater.launch_installer(path)
    except updater.UpdateError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    from . import doctor
    rows = doctor.run_checks()
    if args.verify_model:
        try:
            res = doctor.verify_model(load_settings().model_id, _progress_printer("hashing model"))
            print(file=sys.stderr)
            rows.append(doctor._row("model-hash", "Model checksum", "ok" if res["ok"] else "fail",
                                    res["message"]))
        except models_mod.ModelError as e:
            rows.append(doctor._row("model-hash", "Model checksum", "fail", str(e)))
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        marks = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL", "info": "    "}
        print(f"{APP_NAME} {__version__}  |  {COPYRIGHT}\n")
        for r in rows:
            print(f"[{marks.get(r['status'], '    ')}] {r['label']}: {r['detail']}")
    return EXIT_ERROR if any(r["status"] == "fail" for r in rows) else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd in (None, "gui"):
        from .app import run_desktop
        return run_desktop()
    if args.cmd == "serve":
        from .app import run_server
        return run_server(args.port, open_browser=not args.no_open)
    handlers = {"repair": cmd_repair, "history": cmd_history, "packs": cmd_packs, "models": cmd_models,
                "runtime": cmd_runtime, "update": cmd_update, "doctor": cmd_doctor}
    if args.cmd in handlers:
        return handlers[args.cmd](args)
    return EXIT_USAGE


def gui_main() -> int:
    from .app import run_desktop
    return run_desktop()


if __name__ == "__main__":
    raise SystemExit(main())
