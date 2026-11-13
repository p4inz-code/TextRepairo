# A7 Performance and heat audit (v0.2)

Measured on the author's Windows 11 PC (32 threads, 32 GB RAM, no GPU runtime installed), Standard model, CPU only.

| Check | Result |
|---|---|
| Engine priority | `BelowNormal` (checked on the running process) |
| Engine threads | `-t 4` during evaluation; the app default is min(8, cores/2) = 8 here |
| Engine batch size | 128 tokens (gives real reading progress, same speed, shorter CPU bursts) |
| Engine memory | about 5 GB working set with the 4 B model and a 4096-token context |
| Speed | median 4.3 s and mean 4.5 s per evaluation case at 4 threads; about 9 to 15 tokens per second writing; a cold first request spends about 5 s reading the ~800-token prompt, later requests reuse the cache |
| Progress overhead | negligible (pure arithmetic; events at most every 150 ms) |
| Leftover processes | none after the app or evaluation exits (checked: 0 `llama-server` processes) |
| Packaged app size | 145 MB folder, 53 MB installer |
| Heat | all evaluation runs were throttled (4 threads, rest between cases); no benchmark loops were left running |

Not measured: idle CPU with a precise sampler (the app does no background work when idle; the only timer is the one-off 8 second update check), macOS and Linux behavior.
