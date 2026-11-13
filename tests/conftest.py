from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from textrepairo.hardware import Hardware
from textrepairo.runtime import EngineInfo


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXTREPAIRO_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture
def hw() -> Hardware:
    return Hardware("Linux", "x86_64", 8, 16.0, "", "none", 0.0)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_fake_llama(reply):
    """A tiny OpenAI-compatible streaming endpoint. reply(messages) -> str."""
    app = FastAPI()
    app.state.requests = []

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.state.finish = "stop"
    app.state.tokenize_ok = True

    @app.post("/tokenize")
    async def tokenize(request: Request):
        body = await request.json()
        if not app.state.tokenize_ok:
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "nope"}, status_code=404)
        return {"tokens": list(range(max(1, len(body.get("content", "")) // 4)))}

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        body = await request.json()
        app.state.requests.append(body)
        text = reply(body["messages"])

        async def gen():
            for done in (40, 100):  # like llama-server's return_progress chunks
                pp = {"total": 100, "cache": 0, "processed": done, "time_ms": 1}
                yield "data: " + json.dumps({"choices": [], "prompt_progress": pp}) + "\n\n"
            for i in range(0, len(text), 5):
                piece = text[i:i + 5]
                yield "data: " + json.dumps({"choices": [{"delta": {"content": piece}}]}) + "\n\n"
            yield "data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": app.state.finish}]}) + "\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


class FakeServer:
    """Stands in for LlamaServer: serves a fake model on a loopback port."""

    def __init__(self, reply):
        self.app = make_fake_llama(reply)
        self.port = _free_port()
        cfg = uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="error")
        self.server = uvicorn.Server(cfg)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                break
            time.sleep(0.05)
        self.started_with = None

    def start(self, model_path, backend, settings, hw, ready_timeout=0):
        self.started_with = (Path(model_path).name, backend)
        return EngineInfo(f"http://127.0.0.1:{self.port}", "k", backend, str(model_path))

    def running(self):
        return True

    def stop(self):
        pass

    def close(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)


def _echo_reply(messages):
    last = messages[-1]["content"]
    body = last.removeprefix("<text>\n").split("\n</text>")[0]
    return f"Fixed: {body}" if "Fixed" not in body else body


@pytest.fixture
def engine_factory(isolated_home, hw, monkeypatch):
    """Build engines wired to fake llama servers with a custom reply function."""
    from textrepairo import engine as engine_mod
    from textrepairo import server as server_mod
    from textrepairo.config import Settings, models_dir, save_settings

    made: list[FakeServer] = []
    (models_dir() / "fake.gguf").write_bytes(b"GGUF" + b"\0" * 16)
    save_settings(Settings(model_id="custom:fake.gguf"))
    monkeypatch.setattr(engine_mod, "find_runtime", lambda backend: Path("llama-server"))
    monkeypatch.setattr(server_mod, "find_runtime", lambda backend: Path("llama-server"))

    def make(reply=_echo_reply):
        fake = FakeServer(reply)
        made.append(fake)
        eng = engine_mod.Engine(server=fake, hardware=hw)
        eng.fake = fake
        return eng

    yield make
    for f in made:
        f.close()


@pytest.fixture
def fake_engine(engine_factory):
    """Engine wired to a fake llama server that echoes the <text> body."""
    return engine_factory()
