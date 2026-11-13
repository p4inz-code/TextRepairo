# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Quality harness: run the cases through a real local model and score them.

    python eval/run_eval.py --model standard --threads 4 --limit 20
    python eval/run_eval.py --model lite --modes fix,formal --langs en

Checks are deliberately simple and objective (no cloud judge, runs offline):
  keep       substrings that must survive (names, numbers, links, code)
  forbid     substrings that must NOT appear (slang in formal mode, answers to injected questions)
  english    output must be (almost) all Latin script
  clean      no "Here is..." preface, no tags, not empty
  size       output not wildly longer/shorter than the input
  similarity fix-mode only: word overlap with the reference (reported, soft)
  keep_any   at least one of these must appear (e.g. a formal salutation)
  unchanged  text that is already correct must come back (almost) unchanged
  not_upper  ALL-CAPS input must not come back in all caps
  paras      the number of paragraphs must stay the same
  ai_tell    stock "AI voice" phrases per 100 words that the author did not write (reported)
Use --threads to keep the machine cool; the app itself defaults to about half the cores.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

from textrepairo.config import load_settings
from textrepairo.engine import Engine, EngineError
from textrepairo.humanize import ai_tell_score
from textrepairo.textproc import non_latin_ratio

HERE = Path(__file__).parent


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def words(s: str) -> list[str]:
    return re.findall(r"[\w']+", s.lower())


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(a=words(a), b=words(b), autojunk=False).ratio()


PREFACE = re.compile(r"^\s*(sure|certainly|here(?:'s| is)|of course|corrected|rewritten)\b", re.I)


def score(case: dict, out: str) -> dict[str, bool]:
    low = out.lower()
    inp = case["input"]
    res: dict[str, bool] = {}
    res["clean"] = bool(out.strip()) and not PREFACE.match(out) and "<text>" not in low
    res["english"] = non_latin_ratio(out) < 0.1
    ratio = len(out) / max(1, len(inp))
    wide = case["mode"] in ("prompt", "compose", "email") or case.get("formality") == "extreme"
    cjk = non_latin_ratio(inp) > 0.3  # Chinese or Japanese text is short, so English needs more characters
    res["size"] = 0.25 <= ratio <= (12.0 if wide else 8.0 if cjk else 3.5) or len(inp) < 15
    if case.get("keep"):
        res["keep"] = all(k.lower() in low for k in case["keep"])
    if case.get("forbid"):
        res["forbid"] = not any(f.lower() in low for f in case["forbid"])
    if case.get("forbid_exact"):
        res["no_obey"] = all(out.strip().strip(".").strip().lower() != f.lower()
                             for f in case["forbid_exact"])
    if case.get("keep_any"):
        res["keep_any"] = any(k.lower() in low for k in case["keep_any"])
    if case.get("unchanged"):
        res["unchanged"] = similarity(out, inp) >= 0.9
    if case.get("not_upper"):
        letters = [c for c in out if c.isalpha()]
        res["not_upper"] = bool(letters) and sum(c.isupper() for c in letters) / len(letters) < 0.5
    if case.get("paras"):
        def count_paras(t: str) -> int:
            return len(re.split(r"\n\s*\n", t.strip()))
        res["paras"] = count_paras(out) == count_paras(inp)
    if case.get("max_chars"):
        res["short"] = len(out) <= case["max_chars"]
    return res


async def run(args: argparse.Namespace) -> int:
    settings = load_settings()
    settings.model_id = args.model
    if args.threads:
        settings.threads = args.threads
    cases = load_cases(Path(args.cases))
    if args.modes:
        cases = [c for c in cases if c["mode"] in args.modes.split(",")]
    if args.langs:
        cases = [c for c in cases if c["lang"] in args.langs.split(",")]
    if args.ids:
        prefixes = tuple(x.strip() for x in args.ids.split(",") if x.strip())
        cases = [c for c in cases if c["id"].startswith(prefixes)]
    if args.limit:
        cases = cases[: args.limit]
    engine = Engine()
    rows = []
    t0 = time.time()
    try:
        for i, case in enumerate(cases, 1):
            try:
                res = await engine.repair(case["input"], case["mode"], settings,
                                          formality=case.get("formality"), target=case.get("target"))
                out, secs = res.text, res.seconds
            except EngineError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            checks = score(case, out)
            sim = similarity(out, case["reference"]) if case.get("reference") else None
            ok = all(checks.values())
            tell = ai_tell_score(case["input"], out)
            rows.append({"id": case["id"], "mode": case["mode"], "lang": case["lang"], "ok": ok,
                         "checks": checks, "similarity": sim, "seconds": secs, "ai_tell": tell,
                         "input": case["input"], "output": out})
            flag = "PASS" if ok else "FAIL"
            print(f"[{i:>3}/{len(cases)}] {flag} {case['id']:<14} {secs:5.1f}s", flush=True)
            if not ok or args.verbose:
                bad = [k for k, v in checks.items() if not v]
                print(f"      in : {case['input'][:110]!r}\n      out: {out[:110]!r}  fails={bad}")
            if args.pause:
                await asyncio.sleep(args.pause)  # let the CPU cool between cases
    finally:
        await engine.aclose()
        engine.shutdown()

    by_mode, by_lang = defaultdict(list), defaultdict(list)
    for r in rows:
        by_mode[r["mode"]].append(r["ok"])
        by_lang[r["lang"]].append(r["ok"])
    sims = [r["similarity"] for r in rows if r["similarity"] is not None]
    print("\n== summary ==")
    print(f"model={args.model}  cases={len(rows)}  pass={sum(r['ok'] for r in rows)}  "
          f"time={time.time() - t0:.0f}s")
    for name, group in (("mode", by_mode), ("lang", by_lang)):
        print(f"by {name}: " + "  ".join(f"{k}={sum(v)}/{len(v)}" for k, v in sorted(group.items())))
    if sims:
        print(f"fix similarity to reference (avg): {sum(sims) / len(sims):.2f}")
    tells: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        tells[r["mode"]].append(r["ai_tell"])
    allt = [r["ai_tell"] for r in rows]
    print("ai-tell per 100 words (lower is better): overall "
          f"{sum(allt) / max(1, len(allt)):.2f}  " + "  ".join(
              f"{k}={sum(v) / len(v):.2f}" for k, v in sorted(tells.items())))
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{args.model.replace(':', '_')}-{int(time.time())}.json"
    out_file.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"details: {out_file}")
    return 0 if all(r["ok"] for r in rows) or args.allow_fail else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="standard")
    p.add_argument("--cases", default=str(HERE / "cases.jsonl"))
    p.add_argument("--modes", help="comma list, e.g. fix,formal")
    p.add_argument("--langs", help="comma list, e.g. en,hinglish")
    p.add_argument("--ids", help="comma list of case id prefixes, e.g. inj,fm-,en-fix-01")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--threads", type=int, default=0, help="CPU threads (0 = app default)")
    p.add_argument("--pause", type=float, default=0.0, help="seconds to rest between cases")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--allow-fail", action="store_true", help="exit 0 even if some cases fail")
    return asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
