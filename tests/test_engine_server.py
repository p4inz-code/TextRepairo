import json

import pytest
from fastapi.testclient import TestClient

from textrepairo.engine import EngineError
from textrepairo.server import create_app


async def test_engine_streams_and_restores_links(fake_engine):
    events = [e async for e in fake_engine.stream("pls see https://a.io/x now", "fix")]
    assert events[-1]["event"] == "done"
    assert any(e["event"] == "partial" for e in events)
    assert "https://a.io/x" in events[-1]["text"]
    assert events[-1]["text"].startswith("Fixed:")
    assert events[-1]["diff"]


async def test_engine_handles_paragraphs_and_whitespace(fake_engine):
    text = "one\n\ntwo\n"
    ev = [e async for e in fake_engine.stream(text, "formal")][-1]
    assert ev["text"].count("\n\n") == 1 and ev["text"].endswith("\n")


async def test_engine_empty_text(fake_engine):
    ev = [e async for e in fake_engine.stream("   ", "fix")]
    assert ev[0]["event"] == "done" and ev[0]["text"] == "   "


async def test_engine_unknown_mode(fake_engine):
    with pytest.raises(EngineError):
        [e async for e in fake_engine.stream("x", "shout")]


async def test_engine_sends_no_thinking_flag_only_for_hybrid(fake_engine):
    [e async for e in fake_engine.stream("hello", "fix")]
    req = fake_engine.fake.app.state.requests[-1]
    assert req["stream"] is True and req["temperature"] == 0.1
    assert "chat_template_kwargs" not in req  # custom model name has no qwen3 hint


async def test_engine_requires_model(isolated_home, hw, monkeypatch):
    from textrepairo.engine import Engine
    eng = Engine(hardware=hw)
    with pytest.raises(EngineError):
        [e async for e in eng.stream("hello", "fix")]


def _client(fake_engine):
    app = create_app(fake_engine, token="tok")
    return TestClient(app, base_url="http://127.0.0.1")


def test_api_requires_token(fake_engine):
    c = _client(fake_engine)
    assert c.get("/api/status").status_code == 401
    assert c.get("/api/status", headers={"X-Token": "wrong"}).status_code == 401
    r = c.get("/api/status", headers={"X-Token": "tok"})
    assert r.status_code == 200 and r.json()["ready"] is True


def test_rejects_foreign_host(fake_engine):
    app = create_app(fake_engine, token="tok")
    c = TestClient(app, base_url="http://evil.example")
    assert c.get("/api/status", headers={"X-Token": "tok"}).status_code == 403


def test_index_served_without_token(fake_engine):
    r = _client(fake_engine).get("/")
    assert r.status_code == 200 and "TextRepairo" in r.text
    assert r.headers["cache-control"] == "no-store"


def test_repair_endpoint_streams_sse(fake_engine):
    c = _client(fake_engine)
    with c.stream("POST", "/api/repair", json={"text": "helo wrld", "mode": "fix"},
                  headers={"X-Token": "tok"}) as r:
        body = "".join(r.iter_text())
    events = [json.loads(b[5:]) for b in body.split("\n\n") if b.startswith("data:")]
    assert events[-1]["event"] == "done" and "helo wrld" in events[-1]["text"]


def test_repair_validates_input(fake_engine):
    c = _client(fake_engine)
    h = {"X-Token": "tok"}
    assert c.post("/api/repair", json={"text": "x", "mode": "nope"}, headers=h).status_code == 400
    assert c.post("/api/repair", json={"text": "x" * 70000, "mode": "fix"}, headers=h).status_code == 413


def test_settings_endpoint_filters_keys(fake_engine):
    c = _client(fake_engine)
    h = {"X-Token": "tok"}
    r = c.post("/api/settings", json={"theme": "dark", "evil": 1}, headers=h)
    assert r.json()["theme"] == "dark" and "evil" not in r.json()
    assert c.post("/api/settings", json={"backend": "rm -rf"}, headers=h).status_code == 400
