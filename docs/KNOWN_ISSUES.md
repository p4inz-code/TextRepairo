# Known issues and limits

Kept honest and short. Newest first.

## 0.2.x
- **Output is English only.** Hindi, Marathi and Hinglish output are planned (see ROADMAP.md).
- **Small models make mistakes.** The Standard model can rephrase more than you want, miss an unusual abbreviation, or leave a word unchanged. Fix mode changes as little as possible on purpose. Use the *Changes* tab, and try another style or the Pro model if a result is not right. You can teach the app words with a slang pack (docs/PACKS.md).
- **macOS and Linux builds are tested by CI only**, not on real machines yet. Please send a platform test report.
- **Linux opens in your browser** instead of a native window.
- **Hindi, Hinglish and Marathi slang packs are seed lists** and still need review by native speakers.
- **Only the Standard model has been evaluated** with the full test set. Lite is faster but weaker; Pro was not measured.
- **The first repair after starting the app or switching style is slower** because the model reads its instructions again (a few seconds on a typical CPU).
- **Windows installer:** if you installed 0.1.0 for all users, uninstall it first. 0.2.0 installs for your user only.
- **No screen-reader testing yet.** The interface is built with proper roles and keyboard support, but it has not been tried with NVDA or VoiceOver.
- **Text limit** is 10,000 characters per repair. Split longer text into parts.
