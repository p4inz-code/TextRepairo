"""Local HTTP API + web UI. Binds to loopback only and requires a per-launch token."""

from __future__ import annotations

import asyncio
import json
import secrets
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any, AsyncIterator, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from . import models as models_mod
from .config import data_dir, load_settings, save_settings, web_dir
from .engine import Engine, EngineError
from .prompts import MODES
from .runtime import (BACKENDS, RuntimeError_, asset_names, choose_backend, download_runtime,
                      find_runtime, installed_backends, platform_key)

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
MAX_TEXT_CHARS = 60_000


class RepairBody(BaseModel):
    text: str
    mode: str = "fix"


class IdBody(BaseModel):
    id: str


class PathBody(BaseModel):
    path: str


class BackendBody(BaseModel):
    backend: str


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
        import time
        now = time.time()
        pct = int(done * 100 / total) if total else 0
        if now - last["t"] < 0.25 and pct == last["pct"]:
            return
        last["t"], last["pct"] = now, pct
        loop.call_soon_threadsafe(queue.put_nowait, {"event": "progress", "done": done, "total": total})

    def runner() -> None:
        try:
            work(progress, cancel.is_set)
            loop.call_soon_threadsafe(queue.put_nowait, {"event": "done"})
        except Exception as e:  # noqa: BLE001 - reported to the UI
            loop.call_soon_threadsafe(queue.put_nowait, {"event": "error", "message": str(e)})

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


def create_app(engine: Engine | None = None, token: str | None = None) -> FastAPI:
    eng_ = engine or Engine()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        eng_.shutdown()
        await eng_.aclose()

    app = FastAPI(title="TextRepairo", version=__version__, docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.engine = eng_
    app.state.token = token or secrets.token_urlsafe(24)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = (request.headers.get("host") or "").rsplit(":", 1)[0] if not (
            request.headers.get("host") or "").startswith("[") else "[::1]"
        if host not in ALLOWED_HOSTS:
            return JSONResponse({"error": "bad host"}, status_code=403)
        if request.url.path.startswith("/api/"):
            supplied = request.headers.get("x-token", "")
            if not secrets.compare_digest(supplied, app.state.token):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    eng: Engine = app.state.engine

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
            "settings": asdict(s),
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
            "modes": [{"id": m.id, "label": m.label, "summary": m.summary} for m in MODES.values()],
        }

    @app.post("/api/repair")
    async def repair(body: RepairBody, request: Request):
        if len(body.text) > MAX_TEXT_CHARS:
            return JSONResponse({"error": f"Text is too long (max {MAX_TEXT_CHARS} characters)."},
                                status_code=413)
        if body.mode not in MODES:
            return JSONResponse({"error": "unknown mode"}, status_code=400)

        async def gen() -> AsyncIterator[str]:
            try:
                async for ev in eng.stream(body.text, body.mode):
                    yield sse(ev)
                    if await request.is_disconnected():
                        return
            except EngineError as e:
                yield sse({"event": "error", "message": str(e)})
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                yield sse({"event": "error", "message": f"Unexpected error: {e}"})

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/api/settings")
    async def update_settings(patch: dict) -> dict:
        s = load_settings()
        allowed = {"model_id", "backend", "default_mode", "theme", "context_size", "threads",
                   "gpu_layers", "keep_engine_loaded"}
        for k, v in patch.items():
            if k in allowed:
                setattr(s, k, v)
        if s.backend not in ("auto", *BACKENDS):
            return JSONResponse({"error": "bad backend"}, status_code=400)
        save_settings(s)
        return asdict(s)

    @app.post("/api/models/download")
    async def model_download(body: IdBody):
        spec = models_mod.get_spec(body.id)
        if spec is None:
            return JSONResponse({"error": "unknown model"}, status_code=404)
        return StreamingResponse(
            run_blocking_job(lambda p, c: models_mod.download_model(spec, p, c)),
            media_type="text/event-stream")

    @app.post("/api/models/delete")
    async def model_delete(body: IdBody) -> dict:
        s = load_settings()
        if s.model_id == body.id:
            eng.shutdown()
        try:
            models_mod.remove_model(body.id)
        except models_mod.ModelError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return {"ok": True}

    @app.post("/api/models/import")
    async def model_import(body: PathBody):
        try:
            p = await asyncio.to_thread(models_mod.import_model, body.path)
        except models_mod.ModelError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
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
            return JSONResponse({"error": str(e)}, status_code=400)
        return {"ok": True}

    web = web_dir()
    if web.is_dir():
        app.mount("/", StaticFiles(directory=str(web), html=True), name="web")

    return app
