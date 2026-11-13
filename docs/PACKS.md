# Slang and context packs

A pack tells the app what slang, chat shorthand or romanized words probably mean. The app finds matching words in your text, offline, and gives the model a short note (at most 20 per request) such as `"ngl" = not going to lie`. The model uses it only to understand your text.

Packs that ship with the app live in `src/textrepairo/data/packs/`. Yours go in the `packs` folder inside your data folder (Settings > Privacy > Open data folder), or use Settings > Slang packs > Import a pack. From a terminal: `textrepairo packs import my-words.json`.

## Format

```json
{
  "id": "my-words",
  "name": "My words",
  "version": 1,
  "entries": [
    ["zorp", "a made-up word that means happy"],
    ["bet", "okay, sure, deal", "slang"]
  ]
}
```

- `id`: lowercase letters, digits, `-` or `_`, up to 40 characters. It must not clash with a built-in pack.
- `entries`: `[term, meaning]` or `[term, meaning, note]`. The note is optional and can say when the entry applies.
- Limits: the file must be under 256 KB, at most 5,000 entries, terms up to 40 characters (at least 2), meanings up to 120, notes up to 80, no control characters.
- Matching ignores capitalization and matches whole words or phrases only (`ngl` does not match inside `angle`).
- Invalid packs are skipped and listed in Doctor. They never stop the app.

## Writing good entries
- One short meaning. Add a note when a word has more than one sense ("slang, use context").
- Use your own knowledge. **Do not copy from copyrighted dictionaries or websites.** The built-in lists are original work, released under the same license as the app.
- Words with two meanings (like `kal` in Hindi: yesterday or tomorrow) should say so, so the model decides from the sentence.

## Contributing to the built-in packs
Open a pull request that edits one of the JSON files, or open a "Slang or word suggestion" issue. The Hindi, Hinglish and Marathi lists are seed lists and are being reviewed by native speakers. Corrections are very welcome.
