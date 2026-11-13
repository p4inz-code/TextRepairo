# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
import json

import pytest
from fastapi.testclient import TestClient

from textrepairo import history
from textrepairo.server import MAX_BODY_BYTES, create_app


def _app(engine):
    return create_app(engine, token="tok", port=None)


def _client(engine):
    return TestClient(_app(engine), base_url="http://127.0.0.1")


def _events(resp_text: str) -> list[dict]:
    return [json.loads(b[5:]) for b in resp_text.split("\n\n") if b.startswith("data:")]


H = {"X-Token": "tok"}


# ---------------------------------------------------------------- session cookie flow

def test_launch_token_becomes_http_only_cookie(fake_engine):
    c = _client(fake_engine)
    r = c.get("/?t=tok", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    cookie = r.headers["set-cookie"].lower()
    assert "tr_session=" in cookie and "tr_session=tok;" not in cookie  # a session id, never the launch token
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert c.get("/api/status").status_code == 200  # the browser now holds the session cookie
    assert _client(fake_engine).get("/api/status").status_code == 401  # a client without it is refused


def test_bad_launch_token_is_refused(fake_engine):
    r = _client(fake_engine).get("/?t=nope", follow_redirects=False)
    assert r.status_code == 403 and "set-cookie" not in r.headers


def test_wrong_cookie_is_refused(fake_engine):
    c = _client(fake_engine)
    c.cookies.set("tr_session", "wrong")
    assert c.get("/api/status").status_code == 401


# ---------------------------------------------------------------- headers, origin, size

def test_security_headers_on_pages_and_api(fake_engine):
    c = _client(fake_engine)
    for r in (c.get("/"), c.get("/api/status", headers=H)):
        assert "default-src 'self'" in r.headers["content-security-policy"]
        assert "script-src 'self'" in r.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["referrer-policy"] == "no-referrer" and r.headers["cache-control"] == "no-store"


def test_csp_forbids_inline_script_and_style():
    from textrepairo.server import CSP
    assert "'unsafe-inline'" not in CSP and "'unsafe-eval'" not in CSP


def test_cross_origin_writes_are_blocked(fake_engine):
    c = _client(fake_engine)
    r = c.post("/api/settings", json={"theme": "dark"}, headers={**H, "Origin": "http://evil.example"})
    assert r.status_code == 403
    r = c.post("/api/settings", json={"theme": "dark"}, headers={**H, "Origin": "http://127.0.0.1"})
    assert r.status_code == 200
    r = c.post("/api/settings", json={"theme": "dark"}, headers={**H, "Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


def test_oversized_body_is_refused(fake_engine):
    c = _client(fake_engine)
    r = c.post("/api/settings", content=b"x" * (MAX_BODY_BYTES + 10),
               headers={**H, "Content-Type": "application/json"})
    assert r.status_code == 413


def test_status_exposes_new_fields(fake_engine):
    s = _client(fake_engine).get("/api/status", headers=H).json()
    assert s["max_chars"] == 10_000 and s["history_limit"] == 100
    assert len(s["styles"]) == 11 and [f["id"] for f in s["formalities"]] == ["normal", "advanced", "extreme"]
    assert s["languages"]["en"]["enabled"] and not s["languages"]["hi"]["enabled"]
    assert s["settings"]["history_enabled"] is True and s["settings"]["update_mode"] == "automatic"
    assert s["safe_mode"] is False and s["data_mode"] == "custom"


# ---------------------------------------------------------------- repair + history

def _repair(c, **body):
    with c.stream("POST", "/api/repair", json=body, headers=H) as r:
        text = "".join(r.iter_text())
        return r.status_code, _events(text)


def test_repair_limit_is_enforced_by_the_server(fake_engine):
    c = _client(fake_engine)
    r = c.post("/api/repair", json={"text": "x" * 10_001, "mode": "fix"}, headers=H)
    assert r.status_code == 413 and "10,000" in r.json()["error"]
    status, ev = _repair(c, text="x" * 10_000, mode="fix")
    assert status == 200 and ev[-1]["event"] == "done"


def test_repair_saves_history_by_default(fake_engine):
    c = _client(fake_engine)
    _, ev = _repair(c, text="helo wrld", mode="professional", formality="advanced")
    assert ev[-1]["saved"] is True and ev[-1]["formality"] == "advanced"
    e = history.list_entries()[0]
    assert e["style"] == "professional" and e["formality"] == "advanced"
    assert c.get("/api/history", headers=H).json()["count"] == 1


def test_private_mode_and_switch_off_write_nothing(fake_engine):
    c = _client(fake_engine)
    c.post("/api/settings", json={"private_mode": True}, headers=H)
    _, ev = _repair(c, text="secret text", mode="fix")
    assert ev[-1]["saved"] is False and history.count() == 0
    c.post("/api/settings", json={"private_mode": False, "history_enabled": False}, headers=H)
    _, ev = _repair(c, text="secret text", mode="fix")
    assert ev[-1]["saved"] is False and history.count() == 0


def test_history_endpoints(fake_engine):
    c = _client(fake_engine)
    for t in ("one", "two"):
        _repair(c, text=t, mode="fix")
    entries = c.get("/api/history", headers=H).json()["entries"]
    assert len(entries) == 2 and entries[0]["input_snippet"] == "two"
    full = c.post("/api/history/get", json={"id": entries[0]["id"]}, headers=H).json()
    assert full["input"] == "two" and full["output"].startswith("Fixed")
    assert c.post("/api/history/delete", json={"id": entries[0]["id"]}, headers=H).json()["ok"] is True
    assert c.post("/api/history/get", json={"id": entries[0]["id"]}, headers=H).status_code == 404
    c.post("/api/history/clear", headers=H)
    assert c.get("/api/history", headers=H).json()["count"] == 0


def test_forget_on_exit_clears_history(fake_engine):
    app = _app(fake_engine)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        c.post("/api/settings", json={"forget_on_exit": True}, headers=H)
        _repair(c, text="remember me", mode="fix")
        assert history.count() == 1
    assert history.count() == 0


def test_repair_validation_and_styles(fake_engine):
    c = _client(fake_engine)
    assert c.post("/api/repair", json={"text": "x", "mode": "nope"}, headers=H).status_code == 400
    assert c.post("/api/repair", json={"text": "x", "mode": "fix", "formality": "loud"}, headers=H).status_code == 400
    status, ev = _repair(c, text="helo", mode="formal")  # v0.1 name still works
    assert status == 200 and ev[-1]["mode"] == "professional"


def test_compose_target_reaches_the_prompt(fake_engine):
    c = _client(fake_engine)
    _repair(c, text="notes here", mode="compose", target="prompt_structured")
    system = fake_engine.fake.app.state.requests[-1]["messages"][0]["content"]
    assert "labeled sections" in system


def test_slang_notes_reach_the_prompt(fake_engine):
    c = _client(fake_engine)
    _, ev = _repair(c, text="ngl i cant come tmrw", mode="fix")
    system = fake_engine.fake.app.state.requests[-1]["messages"][0]["content"]
    assert '"ngl" = not going to lie' in system and ev[-1]["notes"] >= 2


def test_engine_requests_ask_for_progress(fake_engine):
    _repair(_client(fake_engine), text="hello", mode="fix")
    assert fake_engine.fake.app.state.requests[-1]["return_progress"] is True


# ---------------------------------------------------------------- settings validation

@pytest.mark.parametrize("patch", [
    {"default_formality": "loud"}, {"update_mode": "sometimes"}, {"theme": "neon"},
    {"default_mode": "shout"}, {"history_enabled": "yes"}, {"private_mode": 1},
])
def test_settings_validation(fake_engine, patch):
    assert _client(fake_engine).post("/api/settings", json=patch, headers=H).status_code == 400


def test_settings_accept_new_values(fake_engine):
    c = _client(fake_engine)
    r = c.post("/api/settings", json={"default_formality": "extreme", "update_mode": "notify",
                                      "default_mode": "formal"}, headers=H).json()
    assert r["default_formality"] == "extreme" and r["update_mode"] == "notify"
    assert r["default_mode"] == "professional"


# ---------------------------------------------------------------- packs, about, doctor

def test_pack_endpoints(fake_engine, tmp_path):
    c = _client(fake_engine)
    ids = {p["id"] for p in c.get("/api/packs", headers=H).json()["packs"]}
    assert "en-slang" in ids
    f = tmp_path / "p.json"
    f.write_text(json.dumps({"id": "mine", "entries": [["zorp", "a made-up word"]]}), encoding="utf-8")
    assert c.post("/api/packs/import", json={"path": str(f)}, headers=H).json()["id"] == "mine"
    assert c.post("/api/packs/import", json={"path": str(tmp_path / "nope.json")}, headers=H).status_code == 400
    assert c.post("/api/packs/remove", json={"id": "mine"}, headers=H).json()["ok"] is True
    assert c.post("/api/packs/remove", json={"id": "../x"}, headers=H).status_code == 400


def test_about_and_documents(fake_engine):
    c = _client(fake_engine)
    a = c.get("/api/about", headers=H).json()
    assert a["brand"] == "P4inz Interactive Labs" and a["author"] == "Atharva Patil"
    assert "Copyright" in a["copyright"] and set(a["links"]) >= {"repo", "portfolio", "discord", "donate"}
    assert c.get("/api/about/doc/notices", headers=H).status_code == 200
    assert c.get("/api/about/doc/..%2F..%2Fetc%2Fpasswd", headers=H).status_code == 404
    assert c.get("/api/about/doc/secrets", headers=H).status_code == 404


def test_doctor_run_and_fixes(fake_engine):
    c = _client(fake_engine)
    d = c.post("/api/doctor/run", headers=H).json()
    ids = {r["id"] for r in d["checks"]}
    assert {"version", "data", "disk", "runtime", "model", "settings", "history", "packs"} <= ids
    assert "doctor report" in d["report"] and "p4inz" not in d["report"].lower()
    assert c.post("/api/doctor/fix", json={"action": "reset_settings"}, headers=H).json()["ok"]
    assert c.post("/api/doctor/fix", json={"action": "rm -rf"}, headers=H).status_code == 400


def test_doctor_verify_model_reports_progress_and_result(fake_engine):
    c = _client(fake_engine)
    with c.stream("POST", "/api/doctor/verify-model", headers=H) as r:
        ev = _events("".join(r.iter_text()))
    assert ev[-1]["event"] == "done" and ev[-1]["result"]["known"] is False


def test_doctor_engine_test(fake_engine):
    r = _client(fake_engine).post("/api/doctor/engine-test", headers=H).json()
    assert r["ok"] is True and r["output"]


def test_open_data_folder_never_takes_a_path(fake_engine, monkeypatch):
    from textrepairo import server
    seen = []
    monkeypatch.setattr(server, "_open_folder", lambda p: seen.append(p))
    c = _client(fake_engine)
    assert c.post("/api/open-data-folder", json={"path": "C:/Windows"}, headers=H).json()["ok"]
    from textrepairo.config import data_dir
    assert seen == [data_dir()]


def test_chunked_oversized_body_is_refused(fake_engine):
    def chunks():
        for _ in range(40):
            yield b"x" * 8192  # 320 KB in total, sent without a Content-Length

    r = _client(fake_engine).post("/api/settings", content=chunks(),
                                  headers={**H, "Content-Type": "application/json"})
    assert r.status_code == 413
    ok = _client(fake_engine).post("/api/settings", json={"theme": "dark"}, headers=H)
    assert ok.status_code == 200


def test_desktop_launch_link_works_only_once(fake_engine):
    app = _app(fake_engine)
    app.state.single_use_launch = True
    first = TestClient(app, base_url="http://127.0.0.1")
    assert first.get("/?t=tok", follow_redirects=False).status_code == 303
    assert first.get("/api/status").status_code == 200
    second = TestClient(app, base_url="http://127.0.0.1")
    r = second.get("/?t=tok", follow_redirects=False)
    assert r.status_code == 403 and "already used" in r.json()["error"]
    assert second.get("/api/status").status_code == 401
    assert first.get("/api/status").status_code == 200  # the first window keeps working


def test_browser_launch_link_can_be_reused_and_each_gets_its_own_session(fake_engine):
    app = _app(fake_engine)
    a = TestClient(app, base_url="http://127.0.0.1")
    b = TestClient(app, base_url="http://127.0.0.1")
    ra = a.get("/?t=tok", follow_redirects=False)
    rb = b.get("/?t=tok", follow_redirects=False)
    assert ra.status_code == rb.status_code == 303
    assert ra.headers["set-cookie"].split(";")[0] != rb.headers["set-cookie"].split(";")[0]
    assert a.get("/api/status").status_code == 200 and b.get("/api/status").status_code == 200


def test_the_launch_token_itself_is_not_a_valid_cookie(fake_engine):
    c = _client(fake_engine)
    c.cookies.set("tr_session", "tok")
    assert c.get("/api/status").status_code == 401
