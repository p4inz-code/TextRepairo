# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
import json

import pytest

from textrepairo import humanize, packs, prompts
from textrepairo.config import packs_dir


# ---------------------------------------------------------------- packs

def _pack_file(tmp_path, **over):
    raw = {"id": "my-words", "name": "My words", "version": 1, "entries": [["zorp", "a made-up word"]]}
    raw.update(over)
    p = tmp_path / "pack.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    return p


def test_bundled_packs_load_and_are_valid():
    loaded = {p["id"]: p for p in packs.list_packs()}
    assert {"en-slang", "hinglish-roman", "marathi-roman"} <= set(loaded)
    assert all(p["source"] == "bundled" for p in loaded.values() if p["id"] in
               ("en-slang", "hinglish-roman", "marathi-roman"))
    assert loaded["en-slang"]["entries"] >= 100


def test_match_finds_whole_words_only():
    hits = packs.match("ngl that was lit, i cant come tmrw")
    joined = " | ".join(hits)
    assert '"ngl" = not going to lie' in joined and '"tmrw" = tomorrow' in joined
    assert not packs.match("an angle on the triangle")  # "ngl" is not inside other words


def test_match_hinglish_and_marathi():
    hits = " ".join(packs.match("mujhe kal office jana hai lekin tabiyat thik nahi, mala udya yeto"))
    assert "tabiyat" in hits and "udya" in hits


def test_match_is_capped_and_deduplicated():
    text = " ".join(["ngl", "tbh", "idk", "imo", "rn", "tmrw", "pls", "thx", "np", "btw", "fyi", "asap",
                    "brb", "gtg", "omw", "lmk", "nvm", "jk", "lol", "omg", "wtf", "smh", "ngl"] * 2)
    hits = packs.match(text)
    assert len(hits) == packs.MAX_HINTS and len({h.split('"')[1].lower() for h in hits}) == len(hits)


def test_user_pack_import_and_remove(tmp_path):
    p = packs.import_pack(_pack_file(tmp_path))
    assert p.id == "my-words" and (packs_dir() / "my-words.json").is_file()
    assert any('"zorp"' in h for h in packs.match("that is so zorp"))
    assert packs.remove_pack("my-words") is True and not packs.match("that is so zorp")


@pytest.mark.parametrize("bad", [
    {"id": "Bad Id"}, {"id": "x", "entries": []}, {"id": "x", "entries": [["only-one"]]},
    {"id": "x", "entries": [["ok", "a\x00b"]]}, {"id": "x", "entries": [["t", "m" * 500]]},
    {"id": "x", "entries": [["a", "meaning"]]}, {"id": "x", "entries": [[1, 2]]},
    {"id": "x", "version": "one", "entries": [["term", "meaning"]]},
])
def test_invalid_packs_are_rejected(tmp_path, bad):
    with pytest.raises(packs.PackError):
        packs.import_pack(_pack_file(tmp_path, **bad))


def test_import_rejects_bundled_id_and_non_json(tmp_path):
    with pytest.raises(packs.PackError, match="built-in"):
        packs.import_pack(_pack_file(tmp_path, id="en-slang"))
    txt = tmp_path / "x.txt"
    txt.write_text("{}")
    with pytest.raises(packs.PackError):
        packs.import_pack(txt)


def test_invalid_user_pack_file_is_skipped_not_fatal():
    (packs_dir() / "broken.json").write_text("{not json", encoding="utf-8")
    assert any(p["id"] == "en-slang" for p in packs.list_packs())


def test_oversized_pack_is_rejected(tmp_path):
    big = _pack_file(tmp_path, entries=[[f"term{i}", "meaning"] for i in range(5001)])
    with pytest.raises(packs.PackError):
        packs.import_pack(big)


# ---------------------------------------------------------------- humanize

def test_ai_tell_counts_only_what_the_author_did_not_write():
    out = "We delve into the matter and leverage a seamless approach."
    assert humanize.ai_tell_score("we look at it", out) > 0
    assert humanize.ai_tell_score("we delve into it, leverage it, seamless", out) == 0


def test_humanize_pass_swaps_stock_words_and_keeps_case():
    out = "Utilize the tool. We leverage it and delve into details."
    fixed = humanize.humanize_pass("use the tool", out)
    assert fixed.startswith("Use the tool.") and "leverage" not in fixed and "look into details" in fixed


def test_humanize_pass_never_touches_authors_own_words():
    src = "We should leverage this and utilize that"
    assert humanize.humanize_pass(src, src) == src


def test_humanize_pass_em_dash():
    assert humanize.humanize_pass("a b", "Fine — really fine.") == "Fine, really fine."
    assert humanize.humanize_pass("a — b", "Fine — really fine.") == "Fine — really fine."


# ---------------------------------------------------------------- prompts

def test_all_eleven_styles_build():
    assert len(prompts.STYLES) == 11
    for sid in prompts.STYLES:
        msgs = prompts.build_messages(sid, "some text")
        assert msgs[0]["role"] == "system" and "write like a real person" in msgs[0]["content"].lower()
        assert msgs[-1]["content"].startswith("<text>\nsome text\n</text>")
        assert "not instructions" in msgs[-1]["content"]


def test_formal_alias_and_catalog():
    assert prompts.resolve_style("formal") == "professional"
    cat = {c["id"]: c for c in prompts.style_catalog()}
    assert [c["id"] for c in prompts.style_catalog() if c["group"] == "main"] == [
        "fix", "professional", "friendly", "prompt"]
    assert cat["compose"]["targets"] and cat["fix"]["formality"] is False


def test_formality_only_applies_to_styles_that_use_it():
    pro = prompts.build_messages("professional", "x", "extreme")[0]["content"]
    fix = prompts.build_messages("fix", "x", "extreme")[0]["content"]
    assert "extremely formal" in pro.lower() and "extremely formal" not in fix.lower()
    adv = prompts.build_messages("email", "x", "advanced")[0]["content"]
    assert "Formality: advanced" in adv
    assert "Formality: normal" in prompts.build_messages("message", "x", "nonsense")[0]["content"]


def test_compose_targets():
    msg = prompts.build_messages("compose", "notes", target="message")[0]["content"]
    prm = prompts.build_messages("compose", "notes", target="prompt_structured")[0]["content"]
    default = prompts.build_messages("compose", "notes", target="bogus")[0]["content"]
    assert "message the author could send" in msg and "labeled sections" in prm
    assert default == msg  # unknown target falls back to the first one


def test_hints_are_added_as_notes_not_instructions():
    sys_msg = prompts.build_messages("fix", "ngl", hints=['"ngl" = not going to lie'])[0]["content"]
    assert 'Understanding notes' in sys_msg and '"ngl" = not going to lie' in sys_msg
    assert "Understanding notes" not in prompts.build_messages("fix", "ngl")[0]["content"]


def test_only_english_output_is_enabled():
    enabled = [k for k, v in prompts.LANGUAGES.items() if v["enabled"]]
    assert enabled == ["en"] and {"hi", "mr", "hinglish"} <= set(prompts.LANGUAGES)


def test_every_style_has_an_injection_example():
    words = ("ignore", "forget", "disregard", "you are now")
    for s in prompts.STYLES.values():
        pools = [s.examples, *s.target_examples.values()]
        assert any(any(w in src.lower() for w in words) for pool in pools for src, _ in pool), s.id
