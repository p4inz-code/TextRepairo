# A2 Privacy audit (v0.2)

## Live network inventory
Taken with `Get-NetTCPConnection` while the app server and the engine were running and a repair was being evaluated:

| Process | Sockets |
|---|---|
| App server (`textrepairo serve`) | Listening on `127.0.0.1:<port>`; established pairs between loopback addresses only |
| Engine (`llama-server`) | Listening on `127.0.0.1:<port>`; one established connection from the app, loopback only |

No connection to any non-loopback address was open. The Doctor check "Network exposure" also confirms the server does not answer on the PC's other addresses.

## Code and dependency checks
- Every web address in the application code belongs to a short allowed list (`test_only_known_hosts_appear_in_the_source`).
- No telemetry package is installed (`test_no_telemetry_packages_are_installed`; `opentelemetry-api` is only an inert interface that FastAPI requires).
- The update check sends only `User-Agent: TextRepairo/<version>` (`test_update_check_sends_nothing_about_the_user`).
- The application code prints only the local address and CLI results; the server runs with access logs off. User text is not logged anywhere.

## Stored data
History (newest 100, deleted text overwritten in the file, verified by reading the database file), Private mode, Forget on exit, switch-off and clear-all are covered by tests listed in A8. The smoke test and the end-to-end update test run in scratch data folders and do not touch real data (this audit found that the first smoke test left a safe-mode marker in the real data folder; fixed).

## Result
Pass. Residual: text can persist in the operating system's swap file or backups, which an application cannot control (stated in the threat model).
