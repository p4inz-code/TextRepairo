# Roadmap

What exists and what is planned. Dates are not promised.

## Done in 0.2
Real progress bar, history (last 100, local), 11 writing styles with 3 formality levels, natural-sounding output by default, Compose mode, slang packs (English chat shorthand, romanized Hindi/Hinglish, romanized Marathi), custom interface controls, Doctor, About, portable mode, optional auto-update, tighter security (session cookie, CSP, pinned engine checksums).

## Next (0.3)
- **Hindi, Marathi and Hinglish output.** Today the output is English. The structure for more languages is in place (`LANGUAGES` in `src/textrepairo/prompts.py`). Each language will get its own prompts, formality rules (for example तू/तुम/आप), a test set and a native speaker's review before it is switched on.
- Global hotkey and a "fix my clipboard" shortcut, tray icon.
- A personal dictionary of words that must never be changed.

## Later
- Read aloud (Windows built-in voices first, then an optional small offline voice model).
- More slang pack coverage, contributed by the community.
- A fine-tuned model, only if tests show a gap that prompts cannot close.
- A browser extension.

## Not planned
Cloud sync, accounts, telemetry, anything that sends your text off the computer.

See [docs/plans/](docs/plans/) for the detailed planning documents.
