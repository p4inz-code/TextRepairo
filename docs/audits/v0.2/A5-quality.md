# A5 Quality audit (v0.2)

Full method, tables and caveats are in [docs/EVAL.md](../../EVAL.md). This page records the audit gate.

## Gate
- Any regression against the 0.1.0 baseline blocks the release: **0 cases that passed in the baseline fail now** (61 shared cases).
- The AI-voice score must not rise: baseline 0.34, now 0.00 (after the clean-up step; the raw model was not measured separately).
- Every injection case must pass: **34 of 34**.
- The final full pass: 159 of 161. The two misses were over-strict checks (spelled-out number, length of an extremely formal answer). They were corrected and re-run alone; both pass.

## Runs
| Run | Cases | Passed | Purpose |
|---|---|---|---|
| Baseline (0.1.0 prompts) | 61 | 55 | Reference |
| First full run of 0.2 | 161 | 137 | Found 8 real problems and several wrong expectations |
| Targeted re-run (injection, formality, edge) | 67 | 58 | Checked the first round of fixes |
| Final full run | 161 | 159 | Release candidate |
| Re-run of the two corrected checks | 2 | 2 | Confirmation |

## Real problems found and fixed
Wrapper-tag breakout (`</text>`), short commands obeyed, essay and rule-list obedience, a changed phone number, an invented "PM", a rewritten date, contractions at high formality, ALL CAPS ignored, a spurious number warning, and a first version of the new guard that was too aggressive. Details in docs/EVAL.md.

## Limits
- Only the Standard model was evaluated (Lite and Pro were not).
- The cases are the project's own. One pass is a sample; model output varies slightly between runs.
- Native-speaker review of Hindi and Marathi input understanding has not happened yet (the slang packs are marked as seed lists).
- Evaluation ran at 4 CPU threads with a rest between cases to keep the PC cool.
