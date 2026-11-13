# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
"""Turn an evaluation result file into Markdown tables.

    python eval/summarize.py eval/results/standard-<timestamp>.json
    python eval/summarize.py new.json --baseline eval/results/baseline-v0.1.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load(path: str) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def category(r: dict) -> str:
    cid = r["id"]
    if cid.startswith(("inj", )):
        return "prompt injection"
    for prefix, name in (("sl-", "slang and chat shorthand"), ("hg-", "Hinglish input"), ("mr-", "Marathi input"),
                         ("ed-", "edge cases"), ("fm-", "formality"), ("cp-", "compose"), ("st-", "other styles"),
                         ("hv-", "human voice")):
        if cid.startswith(prefix):
            return name
    return "multilingual and style basics (v0.1 set)"


def table(rows: list[dict], key) -> str:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    out = ["| Group | Cases | Passed |", "|---|---|---|"]
    for name, g in sorted(groups.items()):
        out.append(f"| {name} | {len(g)} | {sum(r['ok'] for r in g)} |")
    out.append(f"| **All** | **{len(rows)}** | **{sum(r['ok'] for r in rows)}** |")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--baseline")
    args = ap.parse_args()
    rows = load(args.results)
    print("### By category\n\n" + table(rows, category))
    print("\n### By style\n\n" + table(rows, lambda r: {"formal": "professional"}.get(r["mode"], r["mode"])))
    tell = [r["ai_tell"] for r in rows if "ai_tell" in r]
    print(f"\nAI-voice score (hits per 100 words, lower is better): {sum(tell) / max(1, len(tell)):.2f} over {len(tell)} cases")
    secs = [r["seconds"] for r in rows]
    print(f"Time per case: median {sorted(secs)[len(secs) // 2]:.1f} s, mean {sum(secs) / len(secs):.1f} s")
    if args.baseline:
        base = {r["id"]: r for r in load(args.baseline)}
        both = [r for r in rows if r["id"] in base]
        regress = [r["id"] for r in both if base[r["id"]]["ok"] and not r["ok"]]
        fixed = [r["id"] for r in both if not base[r["id"]]["ok"] and r["ok"]]
        print(f"\nCompared with the baseline on the {len(both)} shared cases: "
              f"{len(fixed)} newly passing {fixed}, {len(regress)} newly failing {regress}")
    fails = [r for r in rows if not r["ok"]]
    if fails:
        print("\n### Failing cases\n")
        for r in fails:
            bad = [k for k, v in r["checks"].items() if not v]
            print(f"- `{r['id']}` ({', '.join(bad)}): `{r['input'][:80]}` gave `{r['output'][:100]}`")


if __name__ == "__main__":
    main()
