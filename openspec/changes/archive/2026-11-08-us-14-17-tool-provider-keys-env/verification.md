# Verification — us-14-17-tool-provider-keys-env

Change: us-14-17-tool-provider-keys-env
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension | Status |
|---|---|
| Completeness | 10/10 tasks, 7 reqs |
| Correctness | 7/7 scenarios observed. One part of "Availability" is checked at the function both admission paths call, as noted |
| Coherence | Followed the proposal and design. Additions:<ul><li>The catalog digest leaves out a key's source, since that varies per workspace like availability.</li><li>The install script's "is an OpenRouter key saved" check now filters by provider, since the table is shared.</li><li>Workflows grant no key-backed tool directly (`WORKFLOW_TOOLS` holds none), so their key availability comes through the Experts they delegate to.</li></ul> |

## Scenarios

"DB" rows come from `tests/db/tool_keys_check.py`, run by `scripts/app_db.py` in the `db` profile. It used a disposable database, the real gateway, run admission and leases, and the real Tavily and Jina adapters with fake transports. "Browser" rows come from `apps/web/tests/browser/settings-tool-keys.spec.ts` and the updated `experts.spec.ts` and `tools.spec.ts`, against the identity qualification's disposable stack. That stack's configuration root holds an arranged `.env` with a Jina key.

| Scenario | Result | Observed in |
|---|---|---|
| Settings, then the environment, then .env | PASS | **DB, with nothing saved:**<ul><li>Tavily came from the process environment, past a lower `.env` value.</li><li>Jina came from `.env`, past a whitespace-only `.env.local`.</li><li>The requests carried the environment Tavily key and the `.env` Jina key.</li></ul>**DB, after a save:** the workspace's saved Tavily key won over the environment key in the next request.<br>**Offline:** `test_env_files_follow_mp03_order_and_blank_values_are_skipped` covers MP-03's four files, with blank values skipped. `test_the_process_environment_wins_over_every_env_file` and `test_a_relative_configuration_root_is_never_read` also pass |
| Resolved per attempt from the run's workspace | PASS | **DB:**<ul><li>Workspace A's run sent its first saved key.</li><li>A second workspace's run sent the environment key.</li><li>After the owner replaced A's key, A's next call through the same registry, with no restart, sent the replacement.</li></ul>**Offline:** `test_the_adapter_resolves_inside_the_attempt_and_sends_the_key_only_as_its_header` rotates a `.env` value between two calls of one tool instance |
| Owner saves, replaces and removes, and members see only the source | PASS | **DB:**<ul><li>A save moved the source to `settings` and the version from 0 to 1.</li><li>A stale version was refused with `stale_version`, and a value with a space with `invalid_key`. The saved key was unchanged: the next call still sent it.</li></ul>**Browser, as the owner:**<ul><li>Saving through the form showed "Saved." and cleared the field. The source read "Saved here for this workspace…", and the page's HTML didn't contain the key.</li><li>Through the BFF, `short` was refused with 422 and a stale version with 409 `stale_version`.</li><li>No response from `/api/settings/tool-keys` or `/api/v1/tools` contained any fixture key.</li></ul>**Browser, as a member of workspace A only:** they read both sources, and their PUT and DELETE were refused with 403 `owner_required`.<br>**Offline:** `test_saving_seals_the_key_and_opens_no_connection` patched out sockets and the HTTP client, and a save made no request and wrote only ciphertext. `test_a_malformed_key_is_refused_by_shape_alone` refuses before the database |
| Removing falls back to the environment | PASS | **DB:**<ul><li>Saved Jina was used, then removed, and the next call sent the `.env` Jina key.</li><li>The source read `environment`, at version 2.</li><li>A second removal was refused with `credential_missing`.</li><li>The `.env` file was byte-for-byte unchanged.</li></ul>**Browser:** removing the saved Jina key showed "Removed." and the source "JINA_API_KEY from the server environment or .env". The arranged `.env` file was byte-for-byte unchanged |
| Availability follows the same order | PASS, admission at function level | **DB:**<ul><li>For the catalog, `tavily_search` read `available` with source `settings` in the workspace with a saved key, and `key_missing` in the other. `search_web` read `key_missing` with no source in both.</li><li>`require_available` with each workspace's view gave admitted and `tool_unavailable`. Run admission (`api/run_routes.py`) and routine admission (`application/routines.py`) both call exactly this, with `key_sources` for the request's workspace.</li><li>The real `create_expert` saved a `tavily_search` Expert in the workspace with a saved key, and refused one with `expert_tool_unavailable` in the other. The check process had no Tavily variable.</li></ul>**Browser:**<ul><li>The Tools page's `tavily_search` read "Unavailable: key not set", with the repair "Save a Tavily key in Settings → Tool keys, or set TAVILY_API_KEY in .env, then restart the worker and the API."</li><li>`search_web` read "Key from the environment", and after the owner's save `tavily_search` read "Key from Settings".</li><li>The US-14.5 suite passed with its updated expectation that only keyed tools without a source are `key_missing`, the two Jina tools being from the environment. It covers the API refusing a run or version that grants an unavailable tool.</li></ul> |
| make start passes only the two keys, as data | PASS | `tests/harness/test_tool_keys_env.py` runs the Makefile's own `TOOL_KEYS` line in `/bin/sh`, in a temporary directory with fixture `.env` files:<ul><li>Only `TAVILY_API_KEY` and `JINA_API_KEY` reached the environment. `OPENROUTER_API_KEY` and `OTHER` didn't.</li><li>A value holding `$(…)`, backticks, quotes and `;` arrived literally, and no file it names was created.</li><li>Blank values and a missing file passed nothing.</li><li>Only the API and worker launches take `,keys`, and nothing sources `.env`.</li></ul>`make -n start-api` showed the expanded line |
| The sealed key stays out of durable state | PASS | **DB:**<ul><li>Across the check's runs, no fixture key (environment, `.env`, saved, replaced or saved Jina) appeared in any row of `app_private.tool_uses`, `app_private.tool_receipts`, `public.run_events`, `public.runs`, `app_private.run_jobs` or `agent_runtime.checkpoints`, nor in any log line captured at DEBUG.</li><li>The workspace's Tavily and Jina rows (at least 3) held no plaintext key in their ciphertext.</li><li>The check refuses to print output that contains a key.</li></ul>**Browser:** no API or BFF response contained a key |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile db` | 0 | Passed, with inputs stable. `app_db_qualification`: 523/523, including the 10 new tool-key cases and two role denials on `app_private.tool_key_settings`. `identity_qualification`: 670/670, including the two new browser tests |
| `python3.12 scripts/verify.py --profile fast` | 0 | Passed, after the last unit test was added |
| `python3.12 scripts/verify.py --profile harness` | 0 | Passed |
| `openspec validate us-14-17-tool-provider-keys-env` | 0 | Valid |

The first `db` run failed three browser tests:
- **Expert test:** `experts.spec.ts` still expected every keyed tool to be `key_missing`, but the arranged `.env` Jina key made two available. Its expectation now counts only keyed tools without a source.
- **afterAll timeout:** it timed out because of that first failure.
- **Member test:** `settings-tool-keys.spec.ts` signed in a member of two workspaces, so the API asked them to choose a workspace. It now uses the reader who belongs to workspace A only.

The second `db` run passed.

## Limits

- No live Tavily or Jina request was made. Every key is a fixture.
- Disposable evidence only. The persistent install needs the owner's `make migrate` (migration 51), then `make stop && make start`.
- Not H1 or product acceptance. No independent review ran.
