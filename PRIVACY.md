# Privacy

**TextRepairo does not collect, send or sell any information about you.** There are no accounts, no analytics, no ads and no crash reporting. Your text is processed by an AI model that runs on your own computer.

## What stays on your computer
Everything TextRepairo remembers is stored locally, in its data folder (shown in Settings > About, and openable with Settings > Privacy > Open data folder):

| What | Why | Where |
|---|---|---|
| Settings (theme, style, formality, model, update mode…) | so it looks the way you left it | `settings.json` |
| History of your last 100 results (your text and the result) | so you can get a result back | `history.db` |
| Slang packs you added | extra word meanings | `packs/` |
| AI models and the text engine | they are the app's brain | `models/`, `runtime/` |
| A downloaded update, until it is installed | so "Later" works | `updates/` |
| A marker that tells whether the last session closed properly | to start in safe mode after two bad exits | `session.lock` |

Delete the data folder and all of it is gone. In portable mode the data folder is `data` next to the app.

## History
History is **on by default**, because most people want to get a result back. It keeps the newest **100** entries. Entry 101 permanently deletes the oldest one, and deleted text is overwritten in the file, not just hidden. Under **Settings > Privacy** you can:

- switch history off,
- turn on **Private mode** (nothing is saved while it is on, and a small "Private" tag stays visible),
- turn on **Forget on exit** (clears the history every time you close the app),
- delete single entries, or **Clear history** completely.

From a terminal, `textrepairo history clear` does the same, and `textrepairo repair --private` skips saving for one run.

## The network
TextRepairo works fully offline once a model is installed. It makes network requests only in these cases:

1. **Update check (optional).** A plain `GET` to `https://api.github.com/repos/p4inz-code/TextRepairo/releases/latest` with the generic `User-Agent` `TextRepairo/<version>`. It sends **no** user id, no text, no file names, no system information. If an update exists and you chose Automatic (or press the button), the installer is downloaded from `github.com/p4inz-code/TextRepairo/releases`. It runs at most once a day, about 8 seconds after start. **Settings > Updates** chooses **Automatic**, **Notify me** or **Off** (Off never contacts the network on its own). You can always check by hand.
2. **Downloads you start yourself.** AI model files from `huggingface.co` and the text engine from `github.com/ggml-org/llama.cpp` releases. Both are verified against pinned SHA-256 checksums before use.

GitHub and Hugging Face see your IP address as any website would, and handle it under their own privacy statements. No server run by the author is involved. Downloaded updates are installed only if their SHA-256 matches the one published with the release, and only when the app has your go-ahead (or Automatic mode).

## What the local servers do
The app runs a small web server and the AI engine on your computer. Both listen on `127.0.0.1` only, so other computers cannot reach them. See [SECURITY.md](SECURITY.md).

## Third-party components
The AI engine (llama.cpp) and the models run offline on your text. They have their own licenses (see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).

## Changes
If this policy changes, the change is listed in [CHANGELOG.md](CHANGELOG.md).
