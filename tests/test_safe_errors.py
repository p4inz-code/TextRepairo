# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Nothing internal may reach the page: no exception text, stack traces or private paths."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from textrepairo import errors, models, packs
from textrepairo.errors import GENERIC, AppError, public_message, safe_user_file
from textrepairo.server import create_app

H = {"X-Token": "tok"}
BS = chr(92)  # a backslash


def test_unexpected_exceptions_give_a_generic_sentence_only():
    assert public_message(ValueError("secret C:" + BS + "Users" + BS + "someone" + BS + "key.txt")) == GENERIC
    assert public_message(KeyError("token-123")) == GENERIC
    assert "someone" not in public_message(PermissionError(13, "denied C:" + BS + "Users" + BS + "someone" + BS + "x"))


def test_app_errors_show_their_own_text_with_private_folders_hidden():
    home = str(Path.home())
    msg = public_message(AppError(f"could not read {home}{BS}thing"))
    assert home not in msg and "~" in msg
    from textrepairo.config import data_dir
    assert str(data_dir()) not in public_message(AppError(f"missing {data_dir()}/models/x"))


@pytest.mark.parametrize("bad", ["", "relative/file.json", BS + BS + "server" + BS + "share" + BS + "a.json", "//server/share/a.json",
                                 "C:/does/not/exist.json", "a\x00b.json", 123, None])
def test_user_file_checks_reject_bad_paths(bad):
    with pytest.raises(AppError):
        safe_user_file(bad, {".json"}, AppError, "pack")


def test_user_file_checks_reject_directories_and_wrong_types(tmp_path):
    with pytest.raises(AppError):
        safe_user_file(tmp_path, {".json"}, AppError, "pack")
    f = tmp_path / "a.txt"
    f.write_text("x")
    with pytest.raises(AppError, match="json"):
        safe_user_file(f, {".json"}, AppError, "pack")
    ok = tmp_path / "a.json"
    ok.write_text("{}")
    assert safe_user_file(ok, {".json"}, AppError, "pack") == ok.resolve()


def test_pack_import_writes_a_clean_copy_not_the_users_bytes(tmp_path):
    src = tmp_path / "p.json"
    src.write_text(json.dumps({"id": "mine", "entries": [["zorp", "a word"]], "evil": "<script>x</script>"}))
    packs.import_pack(src)
    saved = json.loads((packs.packs_dir() / "mine.json").read_text(encoding="utf-8"))
    assert set(saved) == {"id", "name", "version", "entries"}


def test_pack_remove_only_touches_files_inside_the_packs_folder(tmp_path):
    outside = tmp_path / "victim.json"
    outside.write_text("{}")
    assert packs.remove_pack("victim") is False and outside.exists()
    with pytest.raises(packs.PackError):
        packs.remove_pack(".." + BS + "victim")


def test_model_import_name_is_sanitised(tmp_path):
    f = tmp_path / "my model (v2)!.gguf"
    f.write_bytes(b"GGUF" + b"\0" * 16)
    dest = models.import_model(f)
    assert dest.parent == models.models_dir() and " " not in dest.name and "!" not in dest.name


def test_server_never_returns_exception_text(fake_engine):
    secret = "SECRET-INTERNAL-DETAIL C:" + BS + "Users" + BS + "someone"

    async def boom(*a, **k):
        raise ValueError(secret)
        yield  # pragma: no cover

    fake_engine.stream = boom
    c = TestClient(create_app(fake_engine, token="tok"), base_url="http://127.0.0.1")
    with c.stream("POST", "/api/repair", json={"text": "hello", "mode": "fix"}, headers=H) as r:
        body = "".join(r.iter_text())
    assert GENERIC in body and "SECRET" not in body and "someone" not in body


def test_server_error_responses_use_safe_text(fake_engine):
    c = TestClient(create_app(fake_engine, token="tok"), base_url="http://127.0.0.1")
    r = c.post("/api/models/import", json={"path": "C:/definitely/missing.gguf"}, headers=H)
    assert r.status_code == 400 and "Traceback" not in r.text and "Errno" not in r.text
    r = c.post("/api/packs/import", json={"path": BS + BS + "evil" + BS + "share" + BS + "x.json"}, headers=H)
    assert r.status_code == 400 and "network" in r.json()["error"]
