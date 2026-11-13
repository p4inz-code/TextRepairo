# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Local HTTP API + web UI.

Binds to loopback only. The launch link carries a one-time token that is exchanged for an
HttpOnly, SameSite=Strict session cookie, so the token never stays in the address bar, the
history or page scripts. Every API call needs that cookie (or the token in an X-Token header
for scripts), a matching Origin on writes, and a loopback Host header.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import (APP_NAME, AUTHOR, BRAND, COFFEE_URL, COPYRIGHT, DISCORD_URL, DONATE_URL, PORTFOLIO_URL,
               REPO_URL, __version__)
from . import doctor as doctor_mod
from . import history as history_mod
from . import models as models_mod
from . import packs as packs_mod
from . import updater as updater_mod
from .config import (HISTORY_LIMIT, MAX_TEXT_CHARS, bundled_data_dir, data_dir, data_mode, load_settings,
                     portable_state, save_settings, web_dir)
from .engine import Engine, EngineError
from .errors import public_message
from .prompts import (FORMALITY, LANGUAGES, PROMPT_VERSION, STYLES, formality_catalog, resolve_style,
                      style_catalog)
from .runtime import (BACKENDS, RuntimeError_, asset_names, choose_backend, download_runtime,
                      find_runtime, installed_backends, platform_key)

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
SESSION_COOKIE = "tr_session"
MAX_BODY_BYTES = 128 * 1024  # largest accepted request body (10,000 characters is about 40 KB)
UPDATE_MODES = ("automatic", "notify", "off")

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
       "form-action 'none'; frame-ancestors 'none'")

ABOUT_DOCS = {"license": "LICENSE", "terms": "ADDITIONAL_TERMS.md", "privacy": "PRIVACY.md",
              "notices": "THIRD_PARTY_NOTICES.md", "security": "SECURITY.md"}


class RepairBody(BaseModel):
    text: str
    mode: str = "fix"
    formality: str | None = None
    target: str | None = None


class IdBody(BaseModel):
    id: str


class IntIdBody(BaseModel):
    id: int


class PathBody(BaseModel):
    path: str


class BackendBody(BaseModel):
    backend: str


class FixBody(BaseModel):
    action: str


class _TooLarge(BaseException):  # not Exception: frameworks must not turn it into a 400
    pass


class BodyLimitMiddleware:
    """Refuse request bodies over `limit` bytes, even when sent in chunks with no Content-Length."""

    def __init__(self, app, limit: int = MAX_BODY_BYTES) -> None:
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        total = 0
        started = False

        async def limited_receive():
            nonlocal total
            msg = await receive()
            if msg["type"] == "http.request":
                total += len(msg.get("body", b""))
                if total > self.limit:
                    raise _TooLarge()
            return msg

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _TooLarge:
            if not started:
                body = b'{"error":"request too large"}'
                await send({"type": "http.response.start", "status": 413,
                            "headers": [(b"content-type", b"application/json"),
                                        (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})


def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def run_blocking_job(work: Callable[[Callable[[int, int], None], Callable[[], bool]], Any]
                           ) -> AsyncIterator[str]:
    """Run blocking `work(progress, cancelled)` in a thread and stream progress as SSE."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    cancel = threading.Event()
    last = {"t": 0.0, "pct": -1}

    def progress(done: int, total: int) -> None:
        now = time.time()
        pct = int(done * 100 / total) if total else 0
        if now - last["t"] < 0.25 and pct == last["pct"]:
            return
        last["t"], last["pct"] = now, pct
        loop.call_soon_threadsafe(queue.put_nowait, {"event": "progress", "done": done, "total": total})

    def runner() -> None:
        try:
            result = work(progress, cancel.is_set)
            ev: dict = {"event": "done"}
            if isinstance(result, dict):
                ev["result"] = result
            loop.call_soon_threadsafe(queue.put_nowait, ev)
        except Exception as e:  # noqa: BLE001 - reported to the UI
            loop.call_soon_threadsafe(queue.put_nowait, {"event": "error", "message": public_message(e)})

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    try:
        while True:
            ev = await queue.get()
            yield sse(ev)
            if ev["event"] in ("done", "error"):
                break
    finally:
        cancel.set()


def _doc_text(name: str) -> str:
    """Read a project document shipped with the app (or from the repo when run from source)."""
    candidates = [bundled_data_dir() / name, Path(__file__).resolve().parents[2] / name]
    for p in candidates:
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    return f"{name} was not found in this build."


def _open_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])  # noqa: S603,S607
    else:
        subprocess.Popen(["xdg-open", str(path)])  # noqa: S603,S607


def create_app(engine: Engine | None = None, token: str | None = None,
               port: int | None = None) -> FastAPI:
    eng_ = engine or Engine()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        try:
            if load_settings().forget_on_exit:
                history_mod.clear()
        except Exception:  # noqa: BLE001
            pass
        eng_.shutdown()
        await eng_.aclose()

    app = FastAPI(title=APP_NAME, version=__version__, docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.add_middleware(BodyLimitMiddleware, limit=MAX_BODY_BYTES)
    app.state.engine = eng_
    app.state.token = token or secrets.token_urlsafe(24)
    app.state.port = port
    app.state.safe_mode = False
    app.state.request_exit = lambda: None  # set by the launcher (closes the window / stops the server)
    app.state.single_use_launch = False  # the desktop window turns this on: its link works once
    app.state.launch_used = False
    sessions: set[str] = set()  # session ids handed out in exchange for the launch token

    def authed(request: Request) -> bool:
        tok = app.state.token
        cookie = request.cookies.get(SESSION_COOKIE, "")
        header = request.headers.get("x-token", "")
        in_session = bool(cookie) and any(secrets.compare_digest(cookie, s) for s in sessions)
        return in_session or secrets.compare_digest(header, tok)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        raw_host = request.headers.get("host") or ""
        host = "[::1]" if raw_host.startswith("[") else raw_host.rsplit(":", 1)[0]
        if host not in ALLOWED_HOSTS:
            return JSONResponse({"error": "bad host"}, status_code=403)
        path = request.url.path
        # One-time launch link: ?t=<token> becomes a session cookie, then the address is cleaned.
        if path == "/" and "t" in request.query_params:
            if secrets.compare_digest(request.query_params["t"], app.state.token):
                if app.state.single_use_launch and app.state.launch_used:
                    return JSONResponse({"error": "This link was already used. Open TextRepairo again."},
                                        status_code=403)
                app.state.launch_used = True
                sid = secrets.token_urlsafe(32)  # the cookie holds a session id, never the launch token
                sessions.add(sid)
                resp = RedirectResponse("/", status_code=303)
                resp.set_cookie(SESSION_COOKIE, sid, httponly=True, samesite="strict", path="/")
                resp.headers["Cache-Control"] = "no-store"
                return resp
            return JSONResponse({"error": "bad token"}, status_code=403)
        if path.startswith("/api/"):
            if not authed(request):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                origin = request.headers.get("origin")
                if origin is not None and origin != f"http://{raw_host}":
                    return JSONResponse({"error": "bad origin"}, status_code=403)
                if request.headers.get("sec-fetch-site", "same-origin") == "cross-site":
                    return JSONResponse({"error": "cross-site request blocked"}, status_code=403)
                length = request.headers.get("content-length")
                if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
                    return JSONResponse({"error": "request too large"}, status_code=413)
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return resp

    eng: Engine = app.state.engine

    # ------------------------------------------------------------ status
    @app.get("/api/status")
    async def status() -> dict:
        s = load_settings()
        hw = eng.hw
        backend = choose_backend(s.backend, hw)
        if find_runtime(backend) is None and find_runtime("cpu") is not None:
            backend = "cpu"  # what will actually run until the GPU engine is installed
        model_ok = False
        try:
            models_mod.resolve_model(s.model_id)
            model_ok = True
        except models_mod.ModelError:
            pass
        runtime_ok = find_runtime(backend) is not None or find_runtime("cpu") is not None
        return {
            "version": __version__,
            "platform": platform_key(),
            "hardware": hw.to_dict(),
            "settings": asdict(s) | {"pending_update": bool(s.pending_update)},
            "models": list(models_mod.list_models()),
            "recommended_model": models_mod.recommend(hw.ram_gb, hw.vram_gb),
            "backend": backend,
            "installed_backends": installed_backends(),
            "available_backends": [b for b in BACKENDS if asset_names(b)],
            "model_ready": model_ok,
            "runtime_ready": runtime_ok,
            "ready": model_ok and runtime_ok,
            "engine_running": eng.server.running(),
            "data_dir": str(data_dir()),
            "data_mode": data_mode(),
            "styles": style_catalog(),
            "formalities": formality_catalog(),
            "languages": LANGUAGES,
            "max_chars": MAX_TEXT_CHARS,
            "history_limit": HISTORY_LIMIT,
            "history_count": history_mod.count(),
            "packs": packs_mod.list_packs(),
            "safe_mode": app.state.safe_mode,
            "prompt_version": PROMPT_VERSION,
            "update_kind": updater_mod.install_kind(),
        }

    # ------------------------------------------------------------ repair
    @app.post("/api/repair")
    async def repair(body: RepairBody, request: Request):
        if len(body.text) > MAX_TEXT_CHARS:
            return JSONResponse({"error": f"This text has {len(body.text):,} characters. The limit is "
                                          f"{MAX_TEXT_CHARS:,}. Split it into parts."}, status_code=413)
        mode = resolve_style(body.mode)
        if mode not in STYLES:
            return JSONResponse({"error": "unknown style"}, status_code=400)
        if body.formality is not None and body.formality not in FORMALITY:
            return JSONResponse({"error": "unknown formality"}, status_code=400)
        settings = load_settings()

        async def gen() -> AsyncIterator[str]:
            try:
                async for ev in eng.stream(body.text, mode, settings, body.formality, body.target):
                    if ev["event"] == "done":
                        ev["saved"] = False
                        if history_mod.allowed(settings) and ev["text"].strip():
                            try:
                                await asyncio.to_thread(
                                    history_mod.add, mode, ev["formality"], body.text, ev["text"],
                                    ev["model"], ev["seconds"], len(ev["warnings"]))
                                ev["saved"] = True
                            except Exception:  # noqa: BLE001 - history must never break a repair
                                pass
                    yield sse(ev)
                    if await request.is_disconnected():
                        return
            except EngineError as e:
                yield sse({"event": "error", "message": public_message(e)})
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                yield sse({"event": "error", "message": public_message(e)})

        return StreamingResponse(gen(), media_type="text/event-stream")

    # ------------------------------------------------------------ settings
    @app.post("/api/settings")
    async def update_settings(patch: dict) -> dict:
        s = load_settings()
        allowed = {"model_id", "backend", "default_mode", "default_formality", "theme", "context_size",
                   "threads", "gpu_layers", "keep_engine_loaded", "history_enabled", "private_mode",
                   "forget_on_exit", "update_mode"}
        for k, v in patch.items():
            if k in allowed:
                setattr(s, k, v)
        s.default_mode = resolve_style(s.default_mode)
        if s.backend not in ("auto", *BACKENDS):
            return JSONResponse({"error": "bad backend"}, status_code=400)
        if s.default_mode not in STYLES:
            return JSONResponse({"error": "bad style"}, status_code=400)
        if s.default_formality not in FORMALITY:
            return JSONResponse({"error": "bad formality"}, status_code=400)
        if s.update_mode not in UPDATE_MODES:
            return JSONResponse({"error": "bad update mode"}, status_code=400)
        if s.theme not in ("system", "light", "dark"):
            return JSONResponse({"error": "bad theme"}, status_code=400)
        for flag in ("history_enabled", "private_mode", "forget_on_exit", "keep_engine_loaded"):
            if not isinstance(getattr(s, flag), bool):
                return JSONResponse({"error": f"bad value for {flag}"}, status_code=400)
        save_settings(s)
        return asdict(s)

    # ------------------------------------------------------------ history
    @app.get("/api/history")
    async def history_list() -> dict:
        s = load_settings()
        return {"entries": history_mod.list_entries(), "count": history_mod.count(),
                "limit": HISTORY_LIMIT, "enabled": s.history_enabled, "private": s.private_mode}

    @app.post("/api/history/get")
    async def history_get(body: IntIdBody):
        e = history_mod.get(body.id)
        return e if e else JSONResponse({"error": "not found"}, status_code=404)

    @app.post("/api/history/delete")
    async def history_delete(body: IntIdBody) -> dict:
        return {"ok": history_mod.delete(body.id)}

    @app.post("/api/history/clear")
    async def history_clear() -> dict:
        history_mod.clear()
        return {"ok": True}

    # ------------------------------------------------------------ packs
    @app.get("/api/packs")
    async def packs_list() -> dict:
        return {"packs": packs_mod.list_packs()}

    @app.post("/api/packs/import")
    async def packs_import(body: PathBody):
        try:
            p = await asyncio.to_thread(packs_mod.import_pack, body.path)
        except packs_mod.PackError as e:
            return JSONResponse({"error": public_message(e)}, status_code=400)
        return {"id": p.id, "entries": len(p.entries)}

    @app.post("/api/packs/remove")
    async def packs_remove(body: IdBody):
        try:
            return {"ok": packs_mod.remove_pack(body.id)}
        except packs_mod.PackError as e:
            return JSONResponse({"error": public_message(e)}, status_code=400)

    # ------------------------------------------------------------ models + runtime
    @app.post("/api/models/download")
    async def model_download(body: IdBody):
        spec = models_mod.get_spec(body.id)
        if spec is None:
            return JSONResponse({"error": "unknown model"}, status_code=404)
        return StreamingResponse(
            run_blocking_job(lambda p, c: models_mod.download_model(spec, p, c)),
            media_type="text/event-stream")

    @app.post("/api/models/delete")
    async def model_delete(body: IdBody):
        s = load_settings()
        if s.model_id == body.id:
            eng.shutdown()
        try:
            models_mod.remove_model(body.id)
        except models_mod.ModelError as e:
            return JSONResponse({"error": public_message(e)}, status_code=400)
        return {"ok": True}

    @app.post("/api/models/import")
    async def model_import(body: PathBody):
        try:
            p = await asyncio.to_thread(models_mod.import_model, body.path)
        except models_mod.ModelError as e:
            return JSONResponse({"error": public_message(e)}, status_code=400)
        return {"id": f"custom:{p.name}"}

    @app.post("/api/runtime/install")
    async def runtime_install(body: BackendBody):
        if body.backend not in BACKENDS or not asset_names(body.backend):
            return JSONResponse({"error": "backend not available on this platform"}, status_code=400)
        return StreamingResponse(
            run_blocking_job(lambda p, c: download_runtime(body.backend, p, c)),
            media_type="text/event-stream")

    @app.post("/api/engine/stop")
    async def engine_stop() -> dict:
        eng.shutdown()
        return {"ok": True}

    @app.post("/api/engine/start")
    async def engine_start():
        try:
            await asyncio.to_thread(eng.ensure_started)
        except EngineError as e:
            return JSONResponse({"error": public_message(e)}, status_code=400)
        return {"ok": True}

    # ------------------------------------------------------------ doctor
    @app.post("/api/doctor/run")
    async def doctor_run() -> dict:
        rows = await asyncio.to_thread(doctor_mod.run_checks, app.state.port, eng.server.running(), eng.hw)
        return {"checks": rows, "report": doctor_mod.report_text(rows)}

    @app.post("/api/doctor/verify-model")
    async def doctor_verify():
        s = load_settings()
        return StreamingResponse(
            run_blocking_job(lambda p, c: doctor_mod.verify_model(s.model_id, p)),
            media_type="text/event-stream")

    @app.post("/api/doctor/engine-test")
    async def doctor_engine_test():
        t0 = time.time()
        try:
            res = await eng.repair("teh quick brown fox jump over lazy dog", "fix")
        except EngineError as e:
            return JSONResponse({"error": public_message(e)}, status_code=400)
        total = time.time() - t0
        tps = round(res.tokens / res.seconds, 1) if res.seconds > 0 and res.tokens else None
        return {"ok": bool(res.text.strip()), "seconds": round(total, 1), "tokens": res.tokens,
                "tokens_per_s": tps, "output": res.text}

    @app.post("/api/doctor/fix")
    async def doctor_fix(body: FixBody):
        if body.action == "reset_settings":
            doctor_mod.reset_settings()
        elif body.action == "clear_cache":
            doctor_mod.clear_cache()
        elif body.action == "clear_history":
            history_mod.clear()
        else:
            return JSONResponse({"error": "unknown action"}, status_code=400)
        return {"ok": True}

    # ------------------------------------------------------------ about + folders
    @app.get("/api/about")
    async def about() -> dict:
        return {
            "name": APP_NAME, "version": __version__, "copyright": COPYRIGHT, "brand": BRAND,
            "author": AUTHOR, "license": "GNU GPL v3 or later, with additional terms (credit stays, "
                                         "modified versions are marked, the name is reserved)",
            "links": {"repo": REPO_URL, "portfolio": PORTFOLIO_URL, "discord": DISCORD_URL,
                      "donate": DONATE_URL, "coffee": COFFEE_URL},
            "models": [{"name": m["name"], "license": m["license"]} for m in models_mod.list_models()],
            "data_dir": str(data_dir()), "data_mode": data_mode(), "portable_note": portable_state()[1],
            "prompt_version": PROMPT_VERSION,
        }

    @app.get("/api/about/doc/{name}")
    async def about_doc(name: str):
        if name not in ABOUT_DOCS:
            return JSONResponse({"error": "unknown document"}, status_code=404)
        return PlainTextResponse(_doc_text(ABOUT_DOCS[name]))

    @app.post("/api/open-data-folder")
    async def open_data_folder() -> dict:
        try:
            _open_folder(data_dir())
        except OSError as e:
            return {"ok": False, "error": public_message(e)}
        return {"ok": True}

    # ------------------------------------------------------------ updates
    @app.get("/api/update/state")
    async def update_state() -> dict:
        s = load_settings()
        return {"mode": s.update_mode, "last_check": s.last_update_check, "kind": updater_mod.install_kind(),
                "pending": bool(s.pending_update), "current": __version__,
                "safe_mode": app.state.safe_mode,
                "due": updater_mod.should_check_now(s) and not app.state.safe_mode}

    @app.post("/api/update/check")
    async def update_check():
        try:
            info = await asyncio.to_thread(updater_mod.check)
        except updater_mod.UpdateError as e:
            return JSONResponse({"error": public_message(e)}, status_code=502)
        updater_mod.record_check()
        app.state.update_info = info
        return info

    @app.post("/api/update/download")
    async def update_download():
        info = getattr(app.state, "update_info", None)
        if not info or not info.get("available"):
            return JSONResponse({"error": "No update to download. Check for updates first."},
                                status_code=400)

        def work(progress, cancelled):
            path = updater_mod.download(info, progress, cancelled)
            app.state.update_path = str(path)
            updater_mod.remember_pending(info, path)
            return {"path": path.name}

        return StreamingResponse(run_blocking_job(work), media_type="text/event-stream")

    @app.post("/api/update/install")
    async def update_install():
        path = getattr(app.state, "update_path", None)
        if not path or not Path(path).is_file():
            return JSONResponse({"error": "Nothing downloaded yet."}, status_code=400)
        try:
            updater_mod.clear_pending()
            updater_mod.launch_installer(Path(path))
        except (updater_mod.UpdateError, OSError) as e:
            return JSONResponse({"error": public_message(e)}, status_code=400)
        threading.Timer(1.0, app.state.request_exit).start()
        return {"ok": True}

    web = web_dir()
    if web.is_dir():
        app.mount("/", StaticFiles(directory=str(web), html=True), name="web")

    return app
