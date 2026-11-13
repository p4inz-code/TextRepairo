# A8 Documentation and repository audit (v0.2)

Question: does every claim in the documentation match what the software does, do all links work, and is there anything private in the repository or its history?

## Private details
- `test_no_private_details_in_tracked_text_files` scans every tracked text file for e-mail addresses, home-folder paths, the author's personal location and hardware details. Result: none.
- All commits use the GitHub no-reply identity (`git log --all --format='%an <%ae>'` shows one author).
- No secrets in any commit (regex scan for tokens, private keys and API-key assignments across all history).
- Public links that do appear (Discord invite, donate page, Buy me a coffee, portfolio) are copied from the author's own public READMEs and are used on purpose in the About screen and README.
- `docs/plans/` contains planning documents written as a conversation between the maintainer and the assistant. They contain no private information.

## Links
`scripts/check_links.py --online` over 27 Markdown documents and 35 external addresses: 0 broken relative links. Three external addresses did not answer the scripted HEAD request; two (Buy me a coffee, Liquid AI docs) answer 200 to a normal request, and one (`PRIVACY.md` on `main`) exists only on the `v0.2` branch until the merge to `main`.

## Claims checked against behavior
| Claim (where) | How it was checked | Result |
|---|---|---|
| 11 styles, 3 formality levels (README, CHANGELOG) | `test_status_exposes_new_fields`, packaged smoke test | True |
| Up to 10,000 characters (README) | client and server tests | True |
| History keeps 100, oldest deleted permanently, text overwritten (PRIVACY) | `test_history_keeps_newest_100_and_deletes_oldest`, `test_deleted_text_is_really_gone_from_the_file`, `test_trimmed_entries_are_overwritten` (looks inside the database file) | True |
| Private mode, Forget on exit, Clear history (PRIVACY) | server and CLI tests | True |
| "The only network requests are the optional update check and downloads you start" (README, PRIVACY, SECURITY) | live connection inventory (A2), `test_only_known_hosts_appear_in_the_source`, `test_no_telemetry_packages_are_installed` | True |
| The update request carries nothing about the user (PRIVACY) | `test_update_check_sends_nothing_about_the_user` (records the headers the fake server received) | True |
| "At most half of your CPU threads (never more than 8)" and low priority (README, Settings) | `default_threads` test and a live check: the engine ran as `BelowNormal` with 4 threads in the evaluation | True. The first draft said "about half of your cores", which was wrong on a 32-thread machine (it uses 8); corrected |
| Progress is real; never 100% early (README, CHANGELOG) | `tests/test_progress_history.py`, live runs | True |
| Slang packs, counts (PACKS.md) | status endpoint lists 3 packs, 425 entries | True |
| Portable mode via `portable.flag` (README, DEVELOPMENT) | `test_portable_flag_puts_data_next_to_the_app`, the read-only fallback and AppImage tests; packaged check in A9 | True in tests; see A9 for the packaged build |
| Windows installer installs per user and can update itself (README, release notes) | See A9 | See A9 |
| Attestation and SBOM published with each release (README, SECURITY) | Workflow written and validated as YAML; the SBOM command was run locally. Proven only when the release workflow has run | See A9 |
| Doctor never includes user text (README, SUPPORT) | `test_doctor_run_and_fixes` and the report builder; the report lists only settings, versions and paths (home folder replaced) | True |
| Output is English only (README, ROADMAP) | `test_only_english_output_is_enabled` | True |

## Wording fixed during the audit
- CPU usage wording (above).
- The v0.1 privacy statement ("no update check") was no longer true; SECURITY.md, PRIVACY.md and README now describe the update check.
- The README download table named files that the release workflow now produces (`...-windows-x64-portable.zip`); the workflow and notes were updated together.

## Repository hygiene
- Every source file has the license header (`test_source_files_carry_license_headers`).
- Required documents exist (`test_required_documents_exist`): LICENSE, ADDITIONAL_TERMS, PRIVACY, SECURITY, SUPPORT, ROADMAP, CHANGELOG, CONTRIBUTING, THIRD_PARTY_NOTICES, README, THREAT_MODEL, PACKS, DEVELOPMENT, EVAL.
- Issue templates (bug, platform test, slang suggestion), Dependabot, CodeQL and a CI dependency audit are in place.
- `.gitignore` excludes models, build output, local evaluation results and the local UI-test folders.
