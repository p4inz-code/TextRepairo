"""Pure text helpers: chunking, protected spans, output cleanup, checks and diffs."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

# ---------------------------------------------------------------- chunking

_SENTENCE_END = re.compile(r"(?<=[.!?。！？।])\s+")


@dataclass
class Chunk:
    text: str
    sep: str  # whitespace that followed this chunk in the original


def split_chunks(text: str, max_chars: int = 1400) -> list[Chunk]:
    """Split on blank lines, then sentences, keeping the original separators."""
    parts = re.split(r"(\n\s*\n)", text)
    chunks: list[Chunk] = []
    i = 0
    while i < len(parts):
        body = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        i += 2
        stripped = body.strip()
        if not stripped:
            if chunks:
                chunks[-1].sep += body + sep
            elif body or sep:
                chunks.append(Chunk("", body + sep))
            continue
        lead = body[: len(body) - len(body.lstrip())]
        trail = body[len(body.rstrip()):]
        if lead and not chunks:
            chunks.append(Chunk("", lead))
        pieces = _pack(stripped, max_chars)
        for j, piece in enumerate(pieces):
            last = j == len(pieces) - 1
            chunks.append(Chunk(piece, (trail + sep) if last else " "))
    return chunks


def _pack(paragraph: str, max_chars: int) -> list[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]
    sentences = _SENTENCE_END.split(paragraph)
    out: list[str] = []
    cur = ""
    for s in sentences:
        while len(s) > max_chars:  # no sentence breaks: hard split on spaces
            cut = s.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            if cur:
                out.append(cur)
                cur = ""
            out.append(s[:cut].strip())
            s = s[cut:].strip()
        if cur and len(cur) + 1 + len(s) > max_chars:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip() if cur else s
    if cur:
        out.append(cur)
    return [o for o in out if o]


# ---------------------------------------------------------------- protected spans

_PROTECT = re.compile(
    r"(```.*?```"  # fenced code
    r"|`[^`\n]+`"  # inline code
    r"|https?://[^\s<>\"')\]]+"  # urls
    r"|www\.[^\s<>\"')\]]+"
    r"|[\w.+-]+@[\w-]+(?:\.[\w-]+)+"  # emails
    r"|(?<![\w/])[A-Za-z]:\\[^\s]+"  # windows paths
    r"|(?<![\w])~?/(?:[\w.-]+/)+[\w.-]+"  # unix paths
    r")",
    re.S,
)
_PLACEHOLDER = re.compile(r"\[\[KEEP_(\d+)\]\]")


def mask(text: str, start: int = 0) -> tuple[str, dict[str, str]]:
    """Replace code, links, emails and paths with [[KEEP_n]] tokens the model must preserve."""
    store: dict[str, str] = {}

    def repl(m: re.Match) -> str:
        key = f"[[KEEP_{start + len(store)}]]"
        store[key] = m.group(0)
        return key

    return _PROTECT.sub(repl, text), store


def hide_partial_placeholder(text: str) -> str:
    """While streaming, cut a half-written [[KEEP_n]] token off the end."""
    idx = text.rfind("[[")
    if idx != -1 and "]]" not in text[idx:]:
        return text[:idx]
    if text.endswith("["):
        return text[:-1]
    return text


def unmask(text: str, store: dict[str, str]) -> tuple[str, list[str]]:
    """Restore protected spans. Returns text and the tokens the model dropped."""
    missing = [k for k in store if k not in text]
    out = text
    for k, v in store.items():
        out = out.replace(k, v)
    return out, missing


# ---------------------------------------------------------------- cleanup

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_PREFACE = re.compile(
    r"^\s*(?:sure[,!.]?|certainly[,!.]?|of course[,!.]?|here(?:'s| is| are)[^\n:]{0,60}:|"
    r"corrected (?:text|version)[^\n:]{0,30}:|rewritten (?:text|version)[^\n:]{0,30}:|"
    r"revised (?:text|version)[^\n:]{0,30}:)\s*\n?",
    re.I,
)


def clean_output(raw: str) -> str:
    s = _THINK.sub("", raw)
    s = re.sub(r"^.*?</think>", "", s, flags=re.S)  # dangling close tag
    s = re.sub(r"</?text>", "", s, flags=re.I).strip()
    for _ in range(2):
        s = _PREFACE.sub("", s, count=1).lstrip()
    if len(s) > 1 and s[0] == s[-1] and s[0] in "\"'" and s.count(s[0]) == 2:
        s = s[1:-1].strip()
    fence = re.fullmatch(r"```[a-zA-Z]*\n(.*?)\n```", s, flags=re.S)
    if fence:
        s = fence.group(1).strip()
    return s


# ---------------------------------------------------------------- checks

_NUM = re.compile(r"\d[\d,.:/-]*\d|\d")


def non_latin_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    odd = sum(1 for c in letters if ord(c) > 0x024F)
    return odd / len(letters)


def check_output(src: str, out: str) -> list[str]:
    """Cheap sanity checks; the UI shows these as warnings, never as errors."""
    warnings: list[str] = []
    if src.strip() and not out.strip():
        warnings.append("The model returned an empty result.")
        return warnings
    if non_latin_ratio(out) > 0.15:
        warnings.append("The result still contains many non-English characters.")
    ratio = len(out) / max(1, len(src))
    if len(src) > 40 and (ratio > 3.0 or ratio < 0.25):
        warnings.append("The result is much longer or shorter than the input. Please review it.")
    missing_nums = [n for n in set(_NUM.findall(src)) if n not in out]
    if missing_nums and non_latin_ratio(src) < 0.15:
        warnings.append("Some numbers from the input are missing in the result: "
                        + ", ".join(sorted(missing_nums)[:5]))
    return warnings


# ---------------------------------------------------------------- diff

_TOKEN = re.compile(r"\s+|[\w'’]+|[^\w\s]", re.U)


def diff_ops(a: str, b: str) -> list[dict]:
    """Word-level diff as a list of {op: eq|del|ins, text}."""
    ta, tb = _TOKEN.findall(a), _TOKEN.findall(b)
    sm = difflib.SequenceMatcher(a=ta, b=tb, autojunk=False)
    ops: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            ops.append({"op": "eq", "text": "".join(ta[i1:i2])})
        else:
            if i2 > i1:
                ops.append({"op": "del", "text": "".join(ta[i1:i2])})
            if j2 > j1:
                ops.append({"op": "ins", "text": "".join(tb[j1:j2])})
    return ops
