# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
import hashlib
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response

from textrepairo import config, history, updater

# ---------------------------------------------------------------- fake release server


class FakeRelease:
    def __init__(self, version="9.9.9", payload=b"INSTALLER-BYTES", tamper=False, notes="Notes"):
        self.version, self.payload, self.tamper = version, payload, tamper
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        base = f"http://127.0.0.1:{self.port}"
        name = f"TextRepairo-Setup-{version}.exe"
        digest = hashlib.sha256(payload).hexdigest()
        sums = f"{digest}  {name}\n" + "0" * 64 + "  TextRepairo-9.9.9-windows-x64.zip\n"
        app = FastAPI()
        self.hits: list[str] = []

        self.headers: list[dict] = []

        @app.get("/releases/latest")
        async def latest(request: Request):
            self.headers.append(dict(request.headers))
            self.hits.append("latest")
            return {"tag_name": f"v{version}", "html_url": f"{base}/page", "body": notes,
                    "assets": [{"name": name, "browser_download_url": f"{base}/dl/{name}"},
                               {"name": "SHA256SUMS.txt", "browser_download_url": f"{base}/dl/SHA256SUMS.txt"}]}

        @app.get("/dl/SHA256SUMS.txt")
        async def sums_route():
            return PlainTextResponse(sums)

        @app.get("/dl/{n}")
        async def dl(n: str):
            return Response(self.payload + (b"X" if self.tamper else b""))

        self.name = name
        self.api = f"{base}/releases/latest"
        cfg = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error")
        self.server = uvicorn.Server(cfg)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                break
            time.sleep(0.05)

    def close(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)


@pytest.fixture
def release(monkeypatch):
    made = []

    def make(**kw):
        r = FakeRelease(**kw)
        made.append(r)
        monkeypatch.setenv("TEXTREPAIRO_TEST_UPDATE_API", r.api)
        return r

    yield make
    for r in made:
        r.close()


# ---------------------------------------------------------------- updater

def test_version_helpers():
    assert updater.parse_version("v1.2.3") == (1, 2, 3) and updater.parse_version("nope") is None
    assert updater.is_newer("0.2.1", "0.2.0") and not updater.is_newer("0.2.0", "0.2.0")
    assert updater.is_newer("0.10.0", "0.9.9") and not updater.is_newer("garbage", "0.1.0")


def test_parse_sums():
    h = "a" * 64
    assert updater.parse_sums(f"{h}  file.exe\nnot a line\n{h.upper()} *other.zip") == {
        "file.exe": h, "other.zip": h}


def test_test_override_is_loopback_only(monkeypatch):
    monkeypatch.setenv("TEXTREPAIRO_TEST_UPDATE_API", "https://evil.example/x")
    assert updater.api_url() == updater.API_URL
    monkeypatch.setenv("TEXTREPAIRO_TEST_UPDATE_API", "http://10.0.0.5:80/x")
    assert updater.api_url() == updater.API_URL
    monkeypatch.setenv("TEXTREPAIRO_TEST_UPDATE_API", "http://127.0.0.1:9/x")
    assert updater.api_url() == "http://127.0.0.1:9/x"


def test_daily_limit_and_modes():
    now = 1_000_000.0
    s = config.Settings(update_mode="automatic", last_update_check=now - 3600)
    assert updater.should_check_now(s, now) is False
    s.last_update_check = now - 25 * 3600
    assert updater.should_check_now(s, now) is True
    s.update_mode = "off"
    assert updater.should_check_now(s, now) is False


def test_check_finds_a_newer_release_for_manual_builds(release):
    r = release()
    info = updater.check()
    assert info["available"] and info["latest"] == "9.9.9" and info["kind"] == "manual"
    assert info["asset"] is None and info["page_url"].endswith("/page")
    assert "latest" in r.hits


def test_check_says_up_to_date(release):
    release(version="0.0.1")
    assert updater.check()["available"] is False


def test_installer_build_downloads_and_verifies(release, monkeypatch):
    release()
    monkeypatch.setattr(updater, "install_kind", lambda: "installer")
    info = updater.check()
    assert info["kind"] == "installer" and info["asset"] == "TextRepairo-Setup-9.9.9.exe"
    seen = []
    path = updater.download(info, lambda d, t: seen.append((d, t)))
    assert path.read_bytes() == b"INSTALLER-BYTES" and seen and seen[-1][0] == seen[-1][1]


def test_bad_checksum_deletes_the_file_and_installs_nothing(release, monkeypatch):
    release(tamper=True)
    monkeypatch.setattr(updater, "install_kind", lambda: "installer")
    info = updater.check()
    with pytest.raises(updater.UpdateError, match="checksum"):
        updater.download(info)
    assert not list(config.updates_dir().glob("*"))


def test_download_refuses_foreign_urls(monkeypatch):
    monkeypatch.delenv("TEXTREPAIRO_TEST_UPDATE_API", raising=False)
    info = {"asset_url": "https://evil.example/TextRepairo-Setup-9.9.9.exe", "sha256": "a" * 64,
            "asset": "TextRepairo-Setup-9.9.9.exe"}
    with pytest.raises(updater.UpdateError):
        updater.download(info)


def test_check_failure_is_reported(monkeypatch):
    monkeypatch.setenv("TEXTREPAIRO_TEST_UPDATE_API", "http://127.0.0.1:1/x")  # nothing listens here
    with pytest.raises(updater.UpdateError):
        updater.check(timeout=2)


def test_pending_update_installs_next_launch_only_when_verified(release, monkeypatch):
    release()
    monkeypatch.setattr(updater, "install_kind", lambda: "installer")
    info = updater.check()
    path = updater.download(info)
    updater.remember_pending(info, path)
    launched = []
    monkeypatch.setattr(updater, "launch_installer", lambda p: launched.append(p))
    assert updater.apply_pending() is True and launched == [path]
    assert config.load_settings().pending_update == {}
    # a tampered pending file is discarded and nothing is launched
    updater.remember_pending(info, path)
    path.write_bytes(b"changed")
    launched.clear()
    assert updater.apply_pending() is False and not launched and not path.exists()


def test_pending_update_respects_off_and_manual(monkeypatch):
    monkeypatch.setattr(updater, "install_kind", lambda: "manual")
    s = config.load_settings()
    s.pending_update = {"version": "9.9.9", "path": "x", "sha256": "a" * 64}
    config.save_settings(s)
    assert updater.apply_pending() is False


def test_launch_installer_uses_silent_flags(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kw: calls.append(args))
    updater.launch_installer(tmp_path / "setup.exe")
    assert "/VERYSILENT" in calls[0] and "/CLOSEAPPLICATIONS" in calls[0] and "/NORESTART" in calls[0]


def test_launch_installer_refuses_on_other_systems(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.sys, "platform", "linux")
    with pytest.raises(updater.UpdateError):
        updater.launch_installer(tmp_path / "x")


def test_update_endpoints_end_to_end(release, fake_engine, monkeypatch):
    from fastapi.testclient import TestClient
    from textrepairo.server import create_app
    release()
    monkeypatch.setattr(updater, "install_kind", lambda: "installer")
    launched, exited = [], []
    monkeypatch.setattr(updater, "launch_installer", lambda p: launched.append(p))
    app = create_app(fake_engine, token="tok")
    app.state.request_exit = lambda: exited.append(1)
    c = TestClient(app, base_url="http://127.0.0.1")
    h = {"X-Token": "tok"}
    assert c.get("/api/update/state", headers=h).json()["due"] is True
    assert c.post("/api/update/download", headers=h).status_code == 400  # check first
    info = c.post("/api/update/check", headers=h).json()
    assert info["available"] and info["kind"] == "installer"
    assert c.get("/api/update/state", headers=h).json()["due"] is False  # checked just now
    with c.stream("POST", "/api/update/download", headers=h) as r:
        ev = [json.loads(b[5:]) for b in "".join(r.iter_text()).split("\n\n") if b.startswith("data:")]
    assert ev[-1]["event"] == "done" and any(e["event"] == "progress" for e in ev)
    assert c.get("/api/update/state", headers=h).json()["pending"] is True
    assert c.post("/api/update/install", headers=h).json()["ok"] is True
    assert launched and config.load_settings().pending_update == {}
    time.sleep(1.3)
    assert exited == [1]


# ---------------------------------------------------------------- portable mode + safe mode

def _frozen(monkeypatch, exe: Path):
    monkeypatch.delenv("TEXTREPAIRO_HOME", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.delenv("APPIMAGE", raising=False)


def test_portable_flag_puts_data_next_to_the_app(monkeypatch, tmp_path):
    app = tmp_path / "App"
    app.mkdir()
    (app / "portable.flag").write_text("", encoding="utf-8")
    _frozen(monkeypatch, app / "TextRepairo.exe")
    assert config.data_mode() == "portable"
    assert config.data_dir() == (app / "data").resolve() or config.data_dir() == app / "data"
    config.save_settings(config.Settings(theme="dark"))
    assert (app / "data" / "settings.json").is_file()


def test_no_flag_means_normal_data_folder(monkeypatch, tmp_path):
    app = tmp_path / "App"
    app.mkdir()
    _frozen(monkeypatch, app / "TextRepairo.exe")
    assert config.data_mode() == "installed"
    assert tmp_path not in config.data_dir().parents


def test_read_only_portable_falls_back_with_a_note(monkeypatch, tmp_path):
    app = tmp_path / "App"
    app.mkdir()
    (app / "portable.flag").write_text("", encoding="utf-8")
    _frozen(monkeypatch, app / "TextRepairo.exe")
    monkeypatch.setattr(config, "_writable_dir", lambda p: False)
    active, note = config.portable_state()
    assert active is False and "read-only" in note


def test_appimage_flag_sits_next_to_the_appimage(monkeypatch, tmp_path):
    (tmp_path / "portable.flag").write_text("", encoding="utf-8")
    _frozen(monkeypatch, tmp_path / "mnt" / "TextRepairo")
    monkeypatch.setenv("APPIMAGE", str(tmp_path / "TextRepairo.AppImage"))
    assert config.data_mode() == "portable"


def test_safe_mode_after_two_bad_exits():
    assert config.begin_session() is False  # first ever start
    assert config.begin_session() is False  # previous one did not end cleanly (1)
    assert config.begin_session() is True  # and again (2): safe mode
    config.end_session()
    assert config.begin_session() is False  # a clean end resets the counter


def test_old_formal_default_is_migrated():
    config.save_settings(config.Settings(default_mode="formal"))
    assert config.load_settings().default_mode == "professional"


# ---------------------------------------------------------------- CLI

def _run_cli(argv, capsys):
    from textrepairo import cli
    code = cli.main(argv)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_cli_repair_json_and_history(fake_engine, monkeypatch, capsys):
    import textrepairo.engine as engine_mod
    monkeypatch.setattr(engine_mod, "Engine", lambda: fake_engine)
    code, out, _ = _run_cli(["repair", "helo wrld", "--json", "-m", "professional", "--formality", "advanced"], capsys)
    data = json.loads(out)
    assert code == 0 and data["style"] == "professional" and data["formality"] == "advanced"
    assert history.count() == 1


def test_cli_private_flag_skips_history(fake_engine, monkeypatch, capsys):
    import textrepairo.engine as engine_mod
    monkeypatch.setattr(engine_mod, "Engine", lambda: fake_engine)
    _run_cli(["repair", "hello", "--private", "--json"], capsys)
    assert history.count() == 0


def test_cli_limit_and_exit_codes(fake_engine, monkeypatch, capsys):
    import textrepairo.engine as engine_mod
    monkeypatch.setattr(engine_mod, "Engine", lambda: fake_engine)
    code, _, err = _run_cli(["repair", "x" * 50, "--max-chars", "10"], capsys)
    assert code == 1 and "limit" in err
    code, _, err = _run_cli(["repair", "-f", "a", "-f", "b", "-o", "x"], capsys)
    assert code == 2


def test_cli_batch_files_to_out_dir(fake_engine, monkeypatch, capsys, tmp_path):
    import textrepairo.engine as engine_mod
    monkeypatch.setattr(engine_mod, "Engine", lambda: fake_engine)
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("first file", encoding="utf-8")
    b.write_text("second file", encoding="utf-8")
    code, out, _ = _run_cli(["repair", "-f", str(a), "-f", str(b), "--out-dir", str(tmp_path / "out")], capsys)
    assert code == 0
    assert (tmp_path / "out" / "a.repaired.txt").read_text(encoding="utf-8").startswith("Fixed")
    assert (tmp_path / "out" / "b.repaired.txt").is_file()


def test_cli_history_packs_doctor(capsys):
    history.add("fix", "normal", "hello", "Hello.", "m", 0.1, 0)
    code, out, _ = _run_cli(["history", "list"], capsys)
    assert code == 0 and "hello" in out
    code, out, _ = _run_cli(["history", "show", "1"], capsys)
    assert "Hello." in out
    code, out, _ = _run_cli(["history", "clear"], capsys)
    assert history.count() == 0
    code, out, _ = _run_cli(["packs", "list"], capsys)
    assert "en-slang" in out
    code, out, _ = _run_cli(["doctor", "--json"], capsys)
    assert code in (0, 1) and {r["id"] for r in json.loads(out)} >= {"version", "data", "model"}


def test_oversized_update_is_refused(release, monkeypatch):
    release(payload=b"A" * 5000)
    monkeypatch.setattr(updater, "install_kind", lambda: "installer")
    monkeypatch.setattr(updater, "MAX_UPDATE_BYTES", 1000)
    info = updater.check()
    with pytest.raises(updater.UpdateError, match="larger than expected"):
        updater.download(info)
    assert not list(config.updates_dir().glob("*"))


def test_update_check_sends_nothing_about_the_user(release):
    r = release()
    updater.check()
    h = r.headers[0]
    assert h["user-agent"] == f"TextRepairo/{updater.__version__}"
    for leak in ("cookie", "authorization", "x-token", "referer", "x-user", "x-machine"):
        assert leak not in h, leak
    assert r.hits == ["latest"]  # a not-newer or manual-build check contacts nothing else
