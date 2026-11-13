from textrepairo.textproc import (check_output, clean_output, diff_ops, mask, non_latin_ratio,
                                  split_chunks, unmask)


def test_chunks_roundtrip_preserves_text():
    text = "First para.\n\nSecond para is here.\n\n\nThird.\n"
    chunks = split_chunks(text)
    assert "".join(c.text + c.sep for c in chunks) == text


def test_long_paragraph_is_split_on_sentences():
    sentence = "This is a sentence that is moderately long. "
    text = sentence * 80
    chunks = split_chunks(text.strip(), max_chars=500)
    assert len(chunks) > 5
    assert all(len(c.text) <= 500 for c in chunks)
    rebuilt = " ".join(c.text for c in chunks)
    assert rebuilt == text.strip()


def test_unbroken_text_is_hard_split():
    chunks = split_chunks("word " * 1000, max_chars=300)
    assert all(len(c.text) <= 300 for c in chunks)


def test_empty_and_whitespace():
    assert split_chunks("") == []
    chunks = split_chunks("   \n\n  ")
    assert "".join(c.text + c.sep for c in chunks) == "   \n\n  "


def test_mask_and_unmask_links_code_emails():
    src = "Visit https://example.com/a?b=1 or mail me@site.org, run `pip install x` now."
    masked, store = mask(src)
    assert "https://" not in masked and "me@site.org" not in masked and "`pip" not in masked
    assert len(store) == 3
    restored, missing = unmask(masked, store)
    assert restored == src and missing == []


def test_unmask_reports_dropped_tokens():
    masked, store = mask("see https://a.io now")
    out, missing = unmask("see now", store)
    assert missing == list(store)
    assert "https" not in out


def test_clean_output_strips_chatter():
    assert clean_output("Sure! Here is the corrected text:\nHello world.") == "Hello world."
    assert clean_output('"Hello world."') == "Hello world."
    assert clean_output("<think>hmm</think>Hello.") == "Hello."
    assert clean_output("<text>\nHi there\n</text>") == "Hi there"
    assert clean_output("```\ncode stays\n```") == "code stays"
    assert clean_output('He said "yes" and "no"') == 'He said "yes" and "no"'


def test_check_output_warnings():
    assert check_output("hello", "") == ["The model returned an empty result."]
    assert check_output("I paid 250 dollars on 12/03", "I paid dollars on")[0].startswith(
        "Some numbers")
    assert any("non-English" in w for w in check_output("namaste", "नमस्ते दोस्त कैसे हो आप"))
    assert check_output("I have 3 apples.", "I have 3 apples.") == []


def test_non_latin_ratio():
    assert non_latin_ratio("hello") == 0
    assert non_latin_ratio("你好吗") == 1
    assert non_latin_ratio("1234") == 0


def test_diff_ops_marks_changes():
    ops = diff_ops("i dont know", "I don't know")
    kinds = {o["op"] for o in ops}
    assert kinds == {"eq", "del", "ins"}
    assert "".join(o["text"] for o in ops if o["op"] != "ins") == "i dont know"
    assert "".join(o["text"] for o in ops if o["op"] != "del") == "I don't know"


def test_hide_partial_placeholder():
    from textrepairo.textproc import hide_partial_placeholder as h
    assert h("visit [[KEEP_0") == "visit "
    assert h("visit [[KEEP_0]] now") == "visit [[KEEP_0]] now"
    assert h("visit [") == "visit "
    assert h("plain") == "plain"
