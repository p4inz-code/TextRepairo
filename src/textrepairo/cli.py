"""Command line interface.

    textrepairo                      open the desktop app
    textrepairo repair "text" -m formal
    echo "text" | textrepairo repair -m friendly
    textrepairo serve                run the local web UI
    textrepairo models list|download|import|remove
    textrepairo runtime install
    textrepairo doctor
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from . import APP_NAME, __version__
from . import models as models_mod
from .config import data_dir, load_settings, save_settings
from .prompts import MODES


def _progress_printer(label: str):
    state = {"pct": -1}

    def cb(done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 0
        if pct != state["pct"]:
            state["pct"] = pct
            mb = done / 1024 / 1024
            print(f"\r{label}: {pct:3d}%  ({mb:,.0f} MB)", end="", file=sys.stderr, flush=True)

    return cb


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="textrepairo",
        description=f"{APP_NAME}: fix messy text in any language into proper English, fully offline.")
    p.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("repair", help="rewrite text (argument, file, or stdin)")
    r.add_argument("text", nargs="?", help="text to repair; omit to read stdin")
    r.add_argument("-m", "--mode", choices=list(MODES), default=None)
    r.add_argument("-f", "--file", help="read input from a file")
    r.add_argument("-o", "--output", help="write the result to a file")
    r.add_argument("--model", help="model id (lite|standard|pro|custom:<file>) for this run")
    r.add_argument("--diff", action="store_true", help="print a word diff to stderr")
    r.add_argument("--no-stream", action="store_true", help="print only the final result")

    s = sub.add_parser("serve", help="run the local web UI")
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--no-open", action="store_true", help="do not open a browser")

    sub.add_parser("gui", help="open the desktop app (default)")

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

    sub.add_parser("doctor", help="print diagnostics")
    return p


def cmd_repair(args: argparse.Namespace) -> int:
    from .engine import Engine, EngineError

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.text is not None:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("Nothing to repair. Pass text, --file, or pipe stdin.", file=sys.stderr)
        return 2
    settings = load_settings()
    if args.model:
        settings.model_id = args.model
    mode = args.mode or settings.default_mode
    engine = Engine()

    live = sys.stdout.isatty() and not args.no_stream and not args.output

    async def run() -> int:
        final = None
        printed = ""
        try:
            async for ev in engine.stream(text, mode, settings):
                if ev["event"] == "partial" and live:
                    new = ev["text"]
                    if new.startswith(printed) and len(new) > len(printed):
                        sys.stdout.write(new[len(printed):])
                        sys.stdout.flush()
                        printed = new
                elif ev["event"] == "done":
                    final = ev
        except EngineError as e:
            print(f"\nError: {e}", file=sys.stderr)
            return 1
        finally:
            await engine.aclose()
            engine.shutdown()
        assert final is not None
        if args.output:
            Path(args.output).write_text(final["text"], encoding="utf-8")
        elif live and final["text"].startswith(printed):
            sys.stdout.write(final["text"][len(printed):])
        elif live:  # streamed text was revised at the end: show the final version
            sys.stdout.write("\n" + final["text"])
        else:
            sys.stdout.write(final["text"])
        sys.stdout.write("\n")
        for w in final["warnings"]:
            print(f"warning: {w}", file=sys.stderr)
        if args.diff:
            line = "".join(
                f"[-{o['text']}-]" if o["op"] == "del" else f"{{+{o['text']}+}}" if o["op"] == "ins"
                else o["text"] for o in final["diff"])
            print(line, file=sys.stderr)
        return 0

    return asyncio.run(run())


def cmd_models(args: argparse.Namespace) -> int:
    s = load_settings()
    if args.models_cmd == "list":
        for m in models_mod.list_models():
            mark = "*" if m["id"] == s.model_id else " "
            state = "installed" if m["installed"] else "not downloaded"
            print(f"{mark} {m['id']:<10} {m['name']:<26} {m['size'] / 1e9:5.2f} GB  "
                  f"{m['license']:<12} {state}")
        print(f"\nModels folder: {models_mod.models_dir()}")
        return 0
    if args.models_cmd == "download":
        spec = models_mod.get_spec(args.id)
        assert spec
        try:
            models_mod.download_model(spec, _progress_printer(spec.name))
        except models_mod.ModelError as e:
            print(f"\nError: {e}", file=sys.stderr)
            return 1
        print("\nDone.", file=sys.stderr)
        return 0
    if args.models_cmd == "import":
        try:
            p = models_mod.import_model(args.path)
        except models_mod.ModelError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Imported. Use it with: textrepairo models use custom:{p.name}")
        return 0
    if args.models_cmd == "remove":
        try:
            models_mod.remove_model(args.id)
        except models_mod.ModelError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0
    if args.models_cmd == "use":
        s.model_id = args.id
        save_settings(s)
        print(f"Default model: {args.id}")
        return 0
    return 2


def cmd_runtime(args: argparse.Namespace) -> int:
    from .engine import Engine
    from .runtime import (asset_names, choose_backend, download_runtime, installed_backends,
                          platform_key)

    if args.runtime_cmd == "list":
        print(f"platform: {platform_key()}  installed: {', '.join(installed_backends()) or 'none'}")
        return 0
    backend = args.backend or choose_backend(load_settings().backend, Engine().hw)
    if not asset_names(backend):
        print(f"Backend '{backend}' is not available on {platform_key()}.", file=sys.stderr)
        return 1
    try:
        path = download_runtime(backend, _progress_printer(f"engine ({backend})"))
    except Exception as e:  # noqa: BLE001
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    print(f"\nInstalled: {path}", file=sys.stderr)
    return 0


def cmd_doctor() -> int:
    from .engine import Engine
    from .runtime import choose_backend, installed_backends, platform_key

    hw = Engine().hw
    s = load_settings()
    print(f"{APP_NAME} {__version__}")
    print(f"data folder : {data_dir()}")
    print(f"platform    : {platform_key()}  RAM {hw.ram_gb} GB  threads {hw.cpu_threads}")
    print(f"gpu         : {hw.gpu_name or 'none'} ({hw.gpu_vendor}, {hw.vram_gb} GB)")
    print(f"backend     : {choose_backend(s.backend, hw)}  installed: "
          f"{', '.join(installed_backends()) or 'none'}")
    print(f"recommended : {models_mod.recommend(hw.ram_gb, hw.vram_gb)}  current: {s.model_id}")
    for m in models_mod.list_models():
        print(f"  model {m['id']:<10} {'ok' if m['installed'] else 'missing'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd in (None, "gui"):
        from .app import run_desktop
        return run_desktop()
    if args.cmd == "serve":
        from .app import run_server
        return run_server(args.port, open_browser=not args.no_open)
    if args.cmd == "repair":
        return cmd_repair(args)
    if args.cmd == "models":
        return cmd_models(args)
    if args.cmd == "runtime":
        return cmd_runtime(args)
    if args.cmd == "doctor":
        return cmd_doctor()
    return 2


def gui_main() -> int:
    from .app import run_desktop
    return run_desktop()


if __name__ == "__main__":
    raise SystemExit(main())
