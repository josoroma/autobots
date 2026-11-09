# Verification — us-14-18-settings-keys-vars-github

Change: us-14-18-settings-keys-vars-github
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension | Status |
|---|---|
| Completeness | 10/10 tasks, 9 reqs |
| Correctness | 9/9 scenarios observed. An empty recorded approval target is checked at function level, since the approval table is immutable and no live path records one now |
| Coherence | Followed the proposal. Two additions, recorded in Decision 0025 V8 and V9:<ul><li>An approval for an unconfigured GitHub destination is no longer requested. It is refused `connector_not_configured` before any approval.</li><li>A write with a receipt (sent, or possibly sent) is left to its receipt. Its handler and readback use the repository the approval recorded, so a changed setting can't redirect a retry or readback either.</li></ul> |

## Scenarios

"DB" rows come from `tests/db/keys_and_vars_check.py` (11 cases) and `tests/db/tool_keys_check.py` (10 cases). `scripts/app_db.py` runs both in the `db` profile, on a disposable database, through the real gateway, approvals and leases. Each fake transport records every request. "Browser" rows come from `settings-keys-and-vars.spec.ts`, `settings-sections.spec.ts` and `experts.spec.ts` on the identity qualification's disposable stack, and from `tools.spec.ts` in `scripts/qualify_web.py`.

| Scenario | Result | Observed in |
|---|---|---|
| Settings → Keys & vars replaces Tool keys | PASS | **Browser:**<ul><li>Settings' nav lists "Keys & vars" at `/settings/keys-and-vars`, which opens with the heading "Keys & vars". It lists `tavily`, `jina` and `github_token` as secrets and `github_repository` and `browser_executor` as values. axe passes.</li><li>`/settings/tool-keys` and `/api/settings/tool-keys` answer 404.</li><li>`tavily_search`'s repair reads "Save a Tavily key in Settings → Keys & vars, or set TAVILY_API_KEY in .env, …".</li><li>The GitHub and browsing repairs name Keys & vars (`tools.spec.ts`, 41/41 in `qualify_web.py`).</li></ul> |
| Settings, then the environment, then .env, for all five | PASS | **DB:**<ul><li>With nothing saved, the repository read `environment owner/environment` and the token `environment` with no value.</li><li>A blank process value fell through to the configuration root's `.env` (`owner/dotenv`).</li><li>Saved values won, and the Tavily and Jina order cases from US-14.17 still pass.</li></ul>**Offline:** `test_the_view_holds_values_and_markers_and_a_saved_switch_wins` shows a saved `disabled` beating an environment `enabled`, a saved repository beating the environment's, and the token as a marker only.<br>**Browser:** the reader, a member of workspace A only, saw `owner/visible` and the token's source `settings` with value `null`. No response contained any fixture secret |
| Owner-only versioned save and removal, checked without a provider request | PASS | **DB:**<ul><li>A token with a space, `not a repository`, a URL as repository and `on` as the switch were refused, and so was a stale version (`stale_version`). No request reached the fake GitHub.</li><li>Saves advanced each version, and a removal fell back with `.env` byte-for-byte unchanged.</li></ul>**Browser:**<ul><li>The same refusals answered 422, with `invalid_key` or `invalid_value`, and a stale version 409.</li><li>Form saves showed "Saved." and cleared the secret field.</li><li>The reader's PUT and DELETE on all four tried items answered 403 `owner_required`.</li></ul>**Offline:** `test_each_item_has_its_own_check` (11 cases) and `test_saving_seals_the_key_and_opens_no_connection` |
| GitHub tools resolve the token and repository per attempt from the run's workspace | PASS | **DB:**<ul><li>`github_list_pull_requests` in workspace A went to `owner/saved` with the saved token. In the other workspace it went to `owner/environment` with the environment token.</li><li>After A's two items were removed, A's next call, in the same registry with no restart, used the environment's pair.</li></ul> |
| A saved disabled switch turns browsing off for its workspace | PASS | **DB, with the executor reporting qualified (arranged in-process) and `AUTOBOTS_BROWSER_EXECUTOR=enabled`:**<ul><li>Workspace A, with `disabled` saved, read `browse_goal` as `disabled_by_policy`. Admission was refused `tool_unavailable` and the real `create_expert` `expert_tool_unavailable`, and the real `InferenceSource._browsing` bound nothing for its job.</li><li>The other workspace read `available`, admitted, saved and bound it.</li></ul> |
| A saved enabled switch turns browsing on for its workspace | PASS | **DB, with no switch in the environment:**<ul><li>A, with `enabled` saved, read `available`, saved its Expert and bound `browse_goal` for its job. The other workspace read `disabled_by_policy` and bound nothing.</li><li>Once the executor reported not qualified, A also read `disabled_by_policy` and bound nothing.</li></ul> |
| An approved GitHub write keeps its repository | PASS, empty target at function level | **DB, with repository `owner/a`:**<ul><li>`create_github_issue` and `github_open_pull_request` each returned `approval_pending`, and both approvals recorded `GitHub repository owner/a`.</li><li>After the owner saved `owner/b`, both approved calls were refused `approval_target_changed`, and the fake GitHub received no request.</li><li>With the repository left at `owner/a`, an approved issue ran and sent `POST` to `owner/a` only.</li></ul>**Offline:**<ul><li>`test_an_approved_write_runs_only_against_its_recorded_target` (6 cases): an empty or null recorded target fails closed, as does a failed receipt with a changed target, and a sent receipt is left to reconciliation.</li><li>`test_a_write_uses_the_repository_its_approval_recorded`.</li></ul> |
| make start passes only the listed variables, as data | PASS | `tests/harness/test_tool_keys_env.py`, 4/4. It runs the Makefile's own lines in `/bin/sh` against fixture `.env` files in a temporary directory:<ul><li>The four variables and an exact `enabled` passed, including a token holding `; touch`, taken literally with no file created.</li><li>`OPENROUTER_API_KEY`, `OTHER` and `AUTOBOTS_WORKER_INFERENCE` didn't pass.</li><li>Blank values and any other switch value passed nothing.</li></ul> |
| The sealed secrets stay out of durable state | PASS | **DB:** neither the saved nor the environment GitHub token appeared in any of these, across 91 rows:<ul><li>tool uses, receipts and events;</li><li>runs and jobs;</li><li>approval requests and `tool_key_settings`;</li><li>the captured logs.</li></ul>The `github` credential row held no plaintext, and the US-14.17 scan still passes for the Tavily and Jina keys.<br>**Browser:** no Keys & vars or catalog response contained a fixture secret |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile db` | 0 | Passed with inputs stable. `app_db_qualification` 534/534, and `identity_qualification` 670/670 |
| `python3.12 scripts/qualify_web.py` | 0 | 41/41 browser tests, `tools.spec.ts` included |
| `python3.12 scripts/verify.py --profile fast` | 0 | Passed. One earlier run failed on `test_hanging_command_returns_promptly_and_leaves_nothing_running`, a timing test this change doesn't touch. Run alone it failed once in three, so it is flaky by itself. The rerun passed |
| `python3.12 scripts/verify.py --profile harness` | 0 | Passed |
| `openspec validate us-14-18-settings-keys-vars-github` | 0 | Valid |

## Limits

- No GitHub, Tavily or Jina request and no model call. Every token is a fixture.
- The executor's qualification was arranged in the check's process.
- Disposable evidence only. The persistent install needs the owner's `make migrate` (migrations 51 and 52), then `make stop && make start`.
- Not H1 or product acceptance. No independent review ran.
