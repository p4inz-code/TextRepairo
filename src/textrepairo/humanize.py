# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Keep output sounding like a person wrote it.

Two jobs:
  * `ai_tell_hits` / `ai_tell_score` measure stock "AI voice" (used by the eval harness and tests).
  * `humanize_pass` removes the most obvious tells from a result, but only ones that were NOT in the
    author's own text, so it never changes words the author wrote.

The patterns are our own short list of well-known stock phrases and hype words. They are
deliberately conservative: ordinary words people use every day are not on it.
"""

from __future__ import annotations

import re

# (name, regex). Each regex hit counts once. Matching is case-insensitive.
_TELLS: list[tuple[str, str]] = [
    ("delve", r"\bdelv(?:e|es|ed|ing)\b"),
    ("tapestry", r"\btapestr(?:y|ies)\b"),
    ("testament", r"\ba testament to\b"),
    ("pivotal", r"\bpivotal\b"),
    ("realm", r"\bin the realm of\b|\brealm of possibilit"),
    ("intricate", r"\bintricate\b"),
    ("vibrant", r"\bvibrant\b"),
    ("seamless", r"\bseamless(?:ly)?\b"),
    ("leverage", r"\bleverag(?:e|es|ed|ing)\b"),
    ("utilize", r"\butili[sz](?:e|es|ed|ing)\b"),
    ("elevate", r"\belevat(?:e|es|ed|ing) (?:your|the|our)\b"),
    ("unlock", r"\bunlock(?:s|ed|ing)? (?:the|your|new)\b"),
    ("embark", r"\bembark(?:s|ed|ing)?\b"),
    ("foster", r"\bfoster(?:s|ed|ing)? (?:a|an|the|growth|collaboration|innovation)\b"),
    ("underscore", r"\bunderscor(?:e|es|ed|ing)\b"),
    ("game_changer", r"\bgame[- ]chang(?:er|ing)\b"),
    ("cutting_edge", r"\bcutting[- ]edge\b"),
    ("ever_evolving", r"\bever[- ](?:evolving|changing)\b"),
    ("fast_paced", r"\bfast[- ]paced\b"),
    ("navigate_complex", r"\bnavigat(?:e|ing) the (?:complexit|landscape|challenges)"),
    ("in_todays", r"\bin today'?s (?:fast|digital|modern|world|ever)"),
    ("important_note", r"\bit(?:'s| is) (?:important|worth) (?:to note|noting)\b"),
    ("hope_finds", r"\bi hope this (?:email|message|note) finds you well\b"),
    ("feel_free", r"\bfeel free to reach out\b"),
    ("dont_hesitate", r"\bdon'?t hesitate to\b|\bdo not hesitate to\b"),
    ("happy_to", r"\bi(?:'d| would) be (?:happy|delighted|glad) to (?:assist|help)\b"),
    ("furthermore", r"\bfurthermore\b"),
    ("moreover", r"\bmoreover\b"),
    ("in_conclusion", r"\bin conclusion\b"),
    ("not_only", r"\bnot only\b[^.!?]{0,80}\bbut also\b"),
    ("plays_role", r"\bplays? a (?:crucial|vital|pivotal|key|significant) role\b"),
    ("em_dash", "—"),
]
_COMPILED = [(n, re.compile(p, re.I)) for n, p in _TELLS]


def ai_tell_hits(text: str) -> dict[str, int]:
    """Count stock-AI patterns in `text`."""
    hits: dict[str, int] = {}
    for name, rx in _COMPILED:
        n = len(rx.findall(text))
        if n:
            hits[name] = n
    return hits


def ai_tell_score(src: str, out: str) -> float:
    """AI-voice hits per 100 words of output, counting only hits the author did not write."""
    src_hits, out_hits = ai_tell_hits(src), ai_tell_hits(out)
    extra = sum(max(0, n - src_hits.get(k, 0)) for k, n in out_hits.items())
    words = max(1, len(re.findall(r"\w+", out)))
    return round(extra * 100.0 / words, 2)


# ---------------------------------------------------------------- safe replacements

_SWAPS: list[tuple[str, re.Pattern[str], str]] = [
    ("utilize", re.compile(r"\butili[sz]e\b", re.I), "use"),
    ("utilizes", re.compile(r"\butili[sz]es\b", re.I), "uses"),
    ("utilized", re.compile(r"\butili[sz]ed\b", re.I), "used"),
    ("utilizing", re.compile(r"\butili[sz]ing\b", re.I), "using"),
    ("leverage", re.compile(r"\bleverage\b", re.I), "use"),
    ("leverages", re.compile(r"\bleverages\b", re.I), "uses"),
    ("leveraged", re.compile(r"\bleveraged\b", re.I), "used"),
    ("leveraging", re.compile(r"\bleveraging\b", re.I), "using"),
    ("delve into", re.compile(r"\bdelve into\b", re.I), "look into"),
    ("delves into", re.compile(r"\bdelves into\b", re.I), "looks into"),
    ("delving into", re.compile(r"\bdelving into\b", re.I), "looking into"),
    ("seamlessly", re.compile(r"\bseamlessly\b", re.I), "smoothly"),
    ("seamless", re.compile(r"\bseamless\b", re.I), "smooth"),
    ("game_changer", re.compile(r"\bgame[- ]changer\b", re.I), "big improvement"),
    ("cutting_edge", re.compile(r"\bcutting[- ]edge\b", re.I), "modern"),
]


def _match_case(repl: str, original: str) -> str:
    if original.isupper() and len(original) > 1:
        return repl.upper()
    if original[:1].isupper():
        return repl[:1].upper() + repl[1:]
    return repl


def humanize_pass(src: str, out: str) -> str:
    """Swap a few stock phrases for plain ones and tame em dashes, unless the author used them."""
    text = out
    src_low = src.lower()
    for name, rx, repl in _SWAPS:
        if name.replace("_", " ") in src_low or rx.search(src):
            continue
        text = rx.sub(lambda m, r=repl: _match_case(r, m.group(0)), text)
    if "—" not in src and "—" in text:
        text = re.sub(r"\s*—\s*", ", ", text)
        text = re.sub(r",\s*,", ",", text)
        text = re.sub(r",\s*([.!?])", r"\1", text)
    return text
