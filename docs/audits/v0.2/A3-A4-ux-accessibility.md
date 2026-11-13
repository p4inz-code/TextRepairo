# A3 UX audit and A4 Accessibility audit (v0.2)

Method: every screen and state was opened in a real browser (the app's own UI served by the real server, with the real Standard model), at desktop width (about 1000 to 1180 px) and phone width (375 px), in dark and light themes. Keyboard behavior was exercised with real key presses. Accessibility was checked from the page's accessibility structure and a computed contrast table. Automated guards live in `tests/test_web_static.py` and `scripts/contrast_check.py`.

## Screens and states reviewed

| Screen or state | Dark | Light | Phone | Notes |
|---|---|---|---|---|
| Main, empty | yes | yes | yes | Style cards, formality row, two panes, limit counter "0 / 10,000" |
| Style picker with "More styles" open (11 styles) | yes | yes | n/a | A chevron glitch on the "Fewer styles" link was found and fixed |
| Formality selector enabled and disabled ("not used by this style") | yes | yes | yes | |
| Compose with the "Write it as" selector | yes | | | |
| Repair in progress: loading, reading, writing | yes | | | Real percentage, "part 2 of 3", speed, time left. Loading shows seconds only |
| Result with Changes tab, stats line "Saved to history" | yes | yes | | |
| Over-limit state (counter turns red, Repair disabled) | by test | | | `updateCount` logic; limit enforced again by the server |
| History drawer (list, delete one, clear all with confirmation) | yes | | | |
| Settings drawer: model, speed (custom select), writing, appearance, privacy (switches), slang packs, updates, help | yes | | | Scrolls; the first version could not scroll, fixed |
| Custom select popup (arrow keys, type-ahead, Escape) | yes | | | |
| Doctor: all checks, engine test, model verify with real byte progress | yes | | | The model checksum check passed on the real 2.5 GB file |
| About: credits, licenses, links, document viewers | yes | | | |
| Safe mode banner and Doctor auto-open | yes | | | Seen live after the test server was killed twice |
| First-run setup dialog (model cards, steps) | yes | | | |
| Toasts, confirm dialogs, tooltips, context menus | by use | | | |

Not reviewed on a real screen: the update banner and dialogs (covered by tests against a fake release server, see A9), and the macOS and Linux windows.

## UX findings fixed during the audit
1. The settings drawer could not scroll (its height followed its content). Fixed.
2. Opening a dialog put keyboard focus on the Close button, showing a tooltip nobody asked for. Focus now goes to the dialog or its primary action.
3. A broken-looking chevron on the "More styles" toggle in the expanded state. Fixed.
4. The reading phase looked stuck at 0% because the engine reported progress in 800-token steps. The engine now starts with 128-token batches, so the percentage moves; a "so far" timer shows during reading.
5. A time-left estimate is hidden until there is enough data (about 3 seconds and 5%).

## A4 Accessibility

| Check | Result |
|---|---|
| Landmarks and headings: header, main, one h1, h2 per pane | Pass |
| Every visible control has an accessible name (text, `aria-label` or tooltip text) | Pass (the only element without its own text, the result panel, is named by its tab) |
| Roles used: radiogroup/radio (styles, formality, theme, update mode), tablist/tab/tabpanel (Result and Changes), dialog with `aria-modal` and `aria-labelledby`, switch, progressbar with `aria-valuenow`, combobox/listbox/option (select), menu/menuitem, tooltip | Pass |
| Keyboard: all of it works without a mouse (arrow keys in radio groups and selects, Enter or Space to open and choose, Escape to close, Ctrl+Enter, Ctrl+H, Ctrl+,) | Pass |
| Focus trap: 70 consecutive Tab presses in the settings drawer never left it; Shift+Tab stays inside; Escape closes and focus returns to the settings button | Pass (tested with real key presses) |
| Visible focus ring on every control | Pass |
| Contrast, text on its background in both themes (15 pairs) | All at least 4.5:1 after one fix (the accent color on tinted cards was 4.43:1 in the light theme; the accent was darkened). Table below |
| Reduced motion | `prefers-reduced-motion` turns animations and transitions off |
| Progress is announced | A polite live region announces 0, 25, 50, 75 and 100 percent, not every tick |
| Text can be selected and copied everywhere; the text boxes are real `<textarea>`s so input methods (including Hindi and Marathi), undo and paste work | Pass |
| Zoom and small screens: layout reflows to one column; no horizontal page scroll at 375 px | Pass |
| Color is never the only signal (status dots come with text, limit counter changes text, errors have text) | Pass |

Not done: a test with a real screen reader (NVDA, VoiceOver). The structure above is what a screen reader reads, but it has not been listened to.

## Contrast table (from `scripts/contrast_check.py`)

```
pair                                           light    dark
body text on page (ink on bg)                  14.41   15.68
text in panels (ink on surface)                15.84   14.42
secondary text on page (muted on bg)            5.12    7.39
secondary text in panels (muted on surface)     5.63    6.80
secondary text on tracks and tabs (muted on surface-2)    5.30    6.43
links on page (accent on bg)                    5.01    7.44
links in panels (accent on surface)             5.51    6.84
accent text on tinted cards (accent on accent-soft)    4.67    5.27
text on selected cards (ink on accent-soft)    13.45   11.11
secondary text on selected cards (muted on accent-soft)    4.78    5.24
text on primary buttons (accent-ink on accent)    5.51    6.72
danger text (danger on surface)                 5.66    7.25
error text on its tint (danger on danger-soft)    4.72    6.47
warning text on its tint (warn on warn-soft)    5.12    8.10
danger text on page (danger on bg)              5.15    7.89
```

The script is part of the test suite, so a color change that breaks contrast fails the build.
