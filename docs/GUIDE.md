# TextRepairo guide

TextRepairo fixes messy text and gives you clear, natural English. It runs on your own computer. You can use it in three ways. All three do the same job and share the same settings and history.

| Way | Best for | How to start |
|---|---|---|
| **1. The app** | Most people. Click and type. | Open **TextRepairo** like any other program |
| **2. The web page** | People who like a browser tab, and Linux | Run `serve` (see below) |
| **3. The command line** | Files, many texts at once, scripts | Type a `repair` command |

---

## Before you start: install it and get a model

1. Download the file for your computer from the [releases page](https://github.com/p4inz-code/TextRepairo/releases/latest):
   - **Windows:** `TextRepairo-Setup-<version>.exe`. Or the `portable.zip` if you don't want to install anything.
   - **Mac (Apple Silicon):** the `.dmg`. Open it and drag TextRepairo to Applications.
   - **Linux:** the `.AppImage` (just run it), the `.deb`, or the `.tar.gz`.
2. Open it. The first time, TextRepairo asks you to **download one AI model** (1 to 5 GB). Pick **Standard** if you are not sure. This needs internet once. After that it works offline.
3. If Windows says "Windows protected your PC", click **More info**, then **Run anyway**. On a Mac, right-click the app and choose **Open**.

Already have a model file (`.gguf`)? Click **I already have a model file** and choose it.

---

## Way 1: The app

1. **Open** TextRepairo.
2. **Paste or type** your text in the left box. It can be bad English, slang, or another language. (Up to 10,000 characters.)
3. **Pick a style.** The four main ones are shown. Click **More styles** for the rest.

   | Style | What it does |
   |---|---|
   | Fix | Fixes spelling and grammar. Keeps your words. |
   | Professional | Polished English for work or school. |
   | Friendly | Warm and easy to read. |
   | Prompt | Turns a rough request into a clear AI prompt. |
   | Compose | Turns scattered notes into a finished message or prompt. |
   | Message | A short chat message, ready to send. |
   | Email | A full email with subject, greeting and closing. |
   | Casual | Relaxed, like texting a friend. |
   | Concise | The same message in fewer words. |
   | Persuasive | More convincing, without exaggeration. |
   | Empathetic | Warm and caring. |

4. **Set the formality** (only for styles that use it): **Normal**, **Advanced** or **Extremely formal**. The control is greyed out when a style doesn't use it.
5. Press **Repair text** (or **Ctrl+Enter**). A progress bar shows the real percentage, the part it is on, the speed and the time left.
6. Read the result on the right. Click **Changes** to see exactly what was altered. Click **Copy** to copy it.

**Handy things**
- **History** (clock icon, or Ctrl+H): your last 100 results. Click one to bring it back. Everything stays on your computer.
- **Settings** (gear icon, or Ctrl+,): change the model, switch history off, turn on **Private mode** (nothing is saved), add slang packs, choose how updates work.
- **Doctor** (in Settings): checks that everything works. Use it first if something is wrong.
- **Stop** (or Esc) cancels a repair in progress.
- Light and dark theme: the moon icon.

---

## Way 2: The web page

This is the same screen, but in your browser.

1. Open a terminal (Command Prompt or PowerShell on Windows).
2. Run:
   ```bash
   textrepairo serve
   ```
   If you installed the Windows installer, the command is `textrepairo-cli.exe` in the install folder (usually `%LOCALAPPDATA%\Programs\TextRepairo`):
   ```bash
   "%LOCALAPPDATA%\Programs\TextRepairo\textrepairo-cli.exe" serve
   ```
3. It prints a link and opens your browser. Use it exactly like the app (see Way 1).
4. Press **Ctrl+C** in the terminal to stop it.

Only your own computer can open this page. Nobody else on your network can.

If the desktop window doesn't open on your computer (some Linux systems), the app falls back to this web page by itself.

---

## Way 3: The command line

Use this for files, for many texts at once, or inside your own scripts.

Where is the command?
- Installed with `pip`, or on Linux from the `.deb`: `textrepairo`
- Windows installer: `textrepairo-cli.exe` in the install folder (see above)
- Mac: the `textrepairo-cli` file inside the app (right-click the app, choose *Show Package Contents*, then *Contents*, then *MacOS*)

(Below, we write `textrepairo`. Use the right name for your system.)

**Fix a sentence**
```bash
textrepairo repair "i dont no wat to do abt this"
```

**Choose a style and formality**
```bash
textrepairo repair "cant come tmrw, got a family thing" -m professional --formality advanced
```
Styles: `fix`, `professional`, `friendly`, `prompt`, `compose`, `message`, `email`, `casual`, `concise`, `persuasive`, `empathetic`. Formality: `normal`, `advanced`, `extreme`.

**Pipe text in**
```bash
echo "bro cant come today got fever tell sir" | textrepairo repair -m message
```

**Fix a file**
```bash
textrepairo repair -f notes.txt -o fixed.txt
```

**Fix many files** (results go in the `fixed` folder)
```bash
textrepairo repair -f a.txt -f b.txt --out-dir fixed/
```

**For scripts:** print JSON, and don't save to history
```bash
textrepairo repair "hello wrld" --json --private
```

**Other commands**
```bash
textrepairo history list        # your saved results
textrepairo history clear       # delete them all
textrepairo doctor              # check that everything works
textrepairo update              # is there a newer version?
textrepairo packs list          # slang packs
textrepairo models list         # models you have
textrepairo --help              # everything else
```

On a terminal the command shows a progress line with the percentage. Exit code `0` means success; `1` an error; `2` a usage mistake.

---

## Good to know

- **Output is English** for now. Hindi, Marathi and Hinglish output are planned. You *can* type in any language, and typed Hinglish and Marathi (in English letters) are understood.
- **Slang:** built-in packs help with chat shorthand ("ngl", "tmrw") and words like "mujhe kal office jana hai". Add your own words in [PACKS.md](PACKS.md).
- **Always read the result** before you send it. The AI is small and can occasionally change more than you want. The **Changes** view is there for that.
- **Privacy:** your text never leaves your computer. See [PRIVACY.md](../PRIVACY.md).
- **Portable:** the Windows `portable.zip` and Linux `.tar.gz` keep everything in a `data` folder next to the app. Move the folder, and your models, settings and history move with it.
- **Updates:** Settings > Updates chooses *Automatic*, *Notify me* or *Off*.
- **Something wrong?** Settings > Doctor > *Copy report*, then [open an issue](https://github.com/p4inz-code/TextRepairo/issues/new/choose). The report never contains your text.
