# Independent review, round 1: Gate 0

Saved as the reviewer returned it, at commit `5012235`. Read-only, and nothing was run.

# US-11.12 Gate 0 review record

**Outcome: changes_required.** There are 3 blocking, 7 major and 7 minor findings. H1 and product acceptance are not assessed here.

**Reviewer context:** independent read-only context, not the author. I used Read, Grep and Glob only and executed nothing, so every result below is either my code reading or supplied `.checks` evidence, and I say which.

**Scope and fingerprint:** commit 5012235 plus the working tree.
- I could not recompute `4f1f26b9…186e8` with read tools, and no file holds it. Have the verifier confirm it with `scripts/evidence.py fingerprints`.
- That fingerprint cannot bind `docs/design/luma.css` or `tests/qualification/*` (G-3).

## Findings

### Blocking

**G-1. `identity_qualification` ignores Playwright's exit code and accepts an empty suite.**
- **Location:** `/Users/josoroma/sites/autobots/scripts/qualify_identity.py:254-303,377`
- **Problem:** all three Playwright runs use `returncode` only to print output. A pass needs only that the cases found in the reports passed, and a report that exists with no suites adds no cases.
- **Consequence:** per the code, a run with a non-zero exit but no failed case in its report still passes, for example a `-g` title that matches nothing or a spec load error. The `db` profile then reports 19 spec files as passing with some or all of them unexecuted. `qualify_web.py:168` already applies the correct rule.
- **Not observed:** the last supplied run recorded 76 browser cases, so this has not happened yet. I did not run Playwright to see what report it writes in those conditions.
- **Resolves:** fail on any non-zero exit, on zero cases and on top-level report errors, and add a negative test.

**G-2. The secret guard does not recognize the real install's secrets.**
- **Location:** `/Users/josoroma/sites/autobots/.claude/hooks/dispatch.py:38-42,102,115-116`; missing tests at `/Users/josoroma/sites/autobots/tests/harness/test_hooks.py:38`
- **Problem:** US-11.3 keeps `stack.env`, `app.env`, `owner.env` and `config/secrets/master.key` under `~/.local/share/autobots-install` (`/Users/josoroma/sites/autobots/scripts/persistent_install.py:191-201`).
  - `is_secret` matches none of those names, and the path check covers only `application support/autobots/secrets`.
  - The `Read` tool has no workspace limit, so these paths get no denial. They hold the service role key, the JWT secret, database passwords and the owner's password.
  - In the Bash patterns, `master.key` also escapes `provider-master\.key`.
- **Consequence:** the guard's stated rule, that secret files are outside ordinary agent access, does not hold for the only real secrets on disk. This also breaks the AGENTS.md boundary on secrets. I did not read those files.
- **Resolves:** deny the install directory's secret files and `master.key`, with fixtures for each, and honor `--install-dir` or state its limit.

**G-3. The freshness guard misses inputs that checks actually read.**
- **Location:** `/Users/josoroma/sites/autobots/scripts/harness_lib.py:43,112`
- **Problem:** two inputs sit outside the manifest:
  - `docs/design/luma.css` is imported by `/Users/josoroma/sites/autobots/apps/web/app/globals.css:3` and read by `appearance.spec.ts:8`.
  - `tests/qualification/tasks.json` is read by `/Users/josoroma/sites/autobots/tests/harness/test_release_qualification.py:13`.
- **Consequence:** editing either one leaves every report current, `evidence.py validate` passing and a reviewed fingerprint unchanged. This fails DH-A11 and DH-09.2.
- **Resolves:** add both to the manifest, plus a test that fails when a check reads a file outside it.

### Major

**G-4. The persistent apply path is classified as a harness-only change.**
- **Location:** `/Users/josoroma/sites/autobots/scripts/harness_lib.py:55`
- **Problem:** `scripts/persistent_install.py` and `scripts/qualify_persistent_apply.py` are not in `DB_CHECK_FILES`, so `check_domains` returns `{'harness'}`.
- **Consequence:** an edit to the only path that changes the persistent database gets a "run harness" diagnostic, and a harness report clears `Stop`. No harness test imports either script. This also contradicts `/Users/josoroma/sites/autobots/docs/engineering/runbooks/development-harness.md:55`.
- **Resolves:** add both, with a classification test.

**G-5. `db` completeness omits `persistent_apply_qualification`.**
- **Location:** `/Users/josoroma/sites/autobots/scripts/harness_lib.py:64,212`; the omission is pinned by `/Users/josoroma/sites/autobots/tests/harness/test_verify_profiles.py:195-197`
- **Consequence:** `report_state` accepts a passing `db` report without the step, for example if it is dropped from `tool_plan`. A real failed step still fails the report. `operations` has a per-qualifier test, and `db` has none.
- **Resolves:** add it to `DB_CHECKS`, and assert that the plan equals `DB_CHECKS`.

**G-6. Model transport is misrecorded as `none` for steps that run scripted models.**
- **Location:** `/Users/josoroma/sites/autobots/scripts/verify.py:37-38`; `/Users/josoroma/sites/autobots/scripts/disposable_db.py:343`
- **Problem:** `app_db.py:339,355,441` state a fake or scripted model. `qualify_identity.py:279` starts `tests/web/fixture_worker.py`, described as "a real worker process around a scripted model".
- **Consequence:** evidence copies `none` for those runs, which breaks the DH-09.2 and DH-A15 classification. It does not create a false live claim.
- **Resolves:** record `mock` for these steps and cases, with a test.

**G-7. `full` claims "the browser suite" but runs 2 of 23 spec files.**
- **Location:** `/Users/josoroma/sites/autobots/scripts/qualify_web.py:157`; `/Users/josoroma/sites/autobots/scripts/verify.py:223`; `/Users/josoroma/sites/autobots/docs/engineering/runbooks/development-harness.md:47,57`
- **Where the 23 run:**

| Runner | Spec files |
|---|---|
| `full` (`qualify_web.py`) | 2 |
| `db` (`qualify_identity.py`) | 19 |
| `qualify_release.py` only | `release-latency` |
| By hand only | `install` |

- **Consequence:** `Stop` and `.claude/rules/nextjs.md` ask only `fast` or `full` for a web change, so most screen tests can be skipped with a clean gate. Runbook line 57 also presents only `tests/toolchain` as unrun by any profile.
- **Resolves:** correct the claims, and require `db` for web changes or run those specs where the claim says they run.

**G-8. The generated-contract fault gate no longer exercises the real checker.**
- **Location:** `/Users/josoroma/sites/autobots/tests/faults/contract/check.py`; `/Users/josoroma/sites/autobots/scripts/qualify_faults.py:68-69`; `/Users/josoroma/sites/autobots/scripts/generate_contracts.py:118-124`
- **Problem:** real contracts have existed since US-2.2, but `contract_bad` tests a local stand-in. The only harness test that runs `generate_contracts.py check` covers a missing environment (`test_generate_contracts.py:59-65`). I found no case that makes the real `check` fail on drift.
- **Consequence:** `app_db.py:494` has the same gap for database types. A broken comparison passes `contract_drift`, so DH-A04 is only fixture-level for this fault.
- **Resolves:** add a deliberately drifted-artifact case for both.

**G-9. The application upgrade case asserts something it no longer tests.**
- **Location:** `/Users/josoroma/sites/autobots/scripts/app_db.py:162-168`
- **Problem:** the expected text is "row kept, default added". `goal_summary` comes from migration 3, and the applied last migration, 33, only alters `approval_requests`. The supplied report shows `prior 1000, then 1000|`.
- **Consequence:** the `db` profile shows no real application upgrade with affected data. The real prior-release upgrade runs only in `operations`, which `Stop` never requires.
- **Resolves:** assert data the final migration actually touches, or generate the check per migration, and correct the case text.

**G-10. H1.3 and DH-A03 conflict with hooks that are configured and firing.**
- **Location:** `/Users/josoroma/sites/autobots/PRD-Development-Harness.md:31,292`; `/Users/josoroma/sites/autobots/PRD-LangChain-Deep-Agents.md:851`; `/Users/josoroma/sites/autobots/docs/engineering/decisions/0009-release-scope-from-blocking-findings.md:12`; `/Users/josoroma/sites/autobots/.claude/settings.json`
- **Problem:** the sources require an unqualified integration to be explicitly inactive, and delivery to be proven for any enabled adapter. In fact settings install the hooks, they have visibly fired, and the status is `configured_unqualified`.
- **What Decision 0009 covers:** it marks crash and timeout not qualified but revises neither gate. It and SPECS US-11.12 also omit Stop recursion, which DH-A03 names and US-1.8 included.
- **Consequence:** the later H1 assessment has no stated rule for this state.
- **Resolves:** record an owner decision on how H1 treats it, and include Stop recursion in the Gate 0 report's marking.

### Minor

**G-11. `db` documentation and prerequisite handling are out of date.**
- `/Users/josoroma/sites/autobots/docs/engineering/runbooks/development-harness.md:43-47,80,87` and AGENTS.md still describe synthetic-only behavior and two images. They omit the prepared Python, Node and browser needs, the identity suite and persistent apply.
- `tool_plan` has no preparation check for `db` (`verify.py:128-134`). A missing venv raises an uncaught `FileNotFoundError` in `app_db.py:241` and `qualify_persistent_apply.py:51`.
- Per the code, that gives exit 1 rather than 2, which blurs the distinction DH-A02 and H0.4 want.

**G-12. `test_shared_form_controls.py` can pass vacuously.**
- **Location:** `/Users/josoroma/sites/autobots/tests/harness/test_shared_form_controls.py:14-19`
- It never asserts that files were scanned or that `field.tsx` exists, so moved folders pass.
- It misses `createElement` and aliased tags. My grep found neither in use, and raw controls appear only in `field.tsx`.
- It proves no raw control appears, at static level, and does not show that a form uses the shared components.

**G-13. R-1 from US-1.8 is still open.**
- **Location:** `/Users/josoroma/sites/autobots/scripts/evidence.py:169-170`
- `exercises_runbook` is accepted on a report-cited check, so a hand-added artifact there could claim a runbook exercise.
- **Resolves:** require `source.kind == 'manual'`.

**G-14. Persistent-path coverage has gaps.**
- `/Users/josoroma/sites/autobots/scripts/qualify_persistent_apply.py:104-105`: the normal path runs only with `expected_class='disposable'`. The real path's success branch, `InstallStack` and `up` have no regression check, only the one US-11.3 live run.
- `/Users/josoroma/sites/autobots/scripts/persistent_install.py:264`: an edited `bootstrap/storage.sql` is skipped silently, with no checksum refusal.
- `qualify_persistent_apply.py:76` passes `--paid` with the default `.env` key file. Two guards stop it first, but overriding the key file would add a third.

**G-15. The state fixture stands apart from the product.**
- **Location:** `/Users/josoroma/sites/autobots/tests/faults/state/check.py:3,11-19`
- It holds its own transition table, and its docstring says the product machine comes later.
- I did not compare the table with the product's. This remains fixture evidence for DH-A05 only.

**G-16. Rule scope does not match the layout.**
- `/Users/josoroma/sites/autobots/.claude/rules/infrastructure.md:7` scopes to `scripts/operations/**`, which does not exist, so no path-scoped rule covers `persistent_install.py`. Line 15 still says host `54322`, while the install uses `55322`.
- `tests/harness/test_assistant_assets.py:62` uses that absent path as a representative.
- DH-03's `scripts/db/` does not exist either.

**G-17. Several records are stale.**
- `/Users/josoroma/sites/autobots/docs/engineering/work-items/US-1.8.md:3` says `COMPLETE`, and the US-1.8 summary has no void notice, while US-10.2 reports `validate` failing. Runbook line 407 still points to it.
- `/Users/josoroma/sites/autobots/CODEBASE.md:5` names `5587a9f` (US-1.3), though the file describes US-11.11. Line 105's "actual Claude event delivery have separate evidence" reads as if qualification evidence exists.
- README line 23 and the PRD status line under-claim. Decision 0003 line 13 is outdated now that DH-W03 has been revised.
- `test_no_persistent_start_exists` (`test_supabase_stack.py:120`) checks only that one file's CLI.

## DH-A gates at this revision

"Level" is what the code and tests can show. No report matches the reviewed tree, so none of these has current execution evidence yet.

| Gate | Supported? | Level | Not supported |
|---|---|---|---|
| A01 | Yes | Fixture (static) | Required skill names are only counted; G-16 |
| A02 | Yes | Fixture | `env -i` and `PATH` arranged runs are from `b94727d`; G-11 |
| A03 | **Partial** | Fixture (script) | Claude crash, timeout and Stop recursion not qualified; G-2, G-10 |
| A04 | **Partial** | Fixture | Real contract and database-type drift, G-8; versions not recorded at this revision |
| A05 | Yes, fixture only | Fixture | Fixture is not linked to the product machine; G-15 |
| A06 | Yes | Disposable | Weak application case, G-9; persistent reset refused in code and on disposable, with two live refusals reported by US-11.3 |
| A07 | Yes | Disposable | Real roles and Auth tokens, sampled from the report. Not a persistent target |
| A08 | Yes | Fixture | Socket block plus reduced environment. Live paid paths sit outside all profiles |
| A09 | Yes | Disposable | Stub, plus real-worker checks whose source I did not read; 1-second leases |
| A10 | Yes | Disposable | Redaction asserted in `operations` and backup, not in `db`; other projects' data not compared |
| A11 | **Partial** | Fixture | G-3, G-4 |
| A12 | Code yes, report **no** | Fixture | US-11.12 report not published; breakdown below |
| A13 | **No** | None current | US-1.8's approval is void, and no `docs/engineering/evidence/US-11.12/` exists |
| A14 | Yes | Fixture | G-13 |
| A15 | **Partial** | Fixture | Live and fake separation holds; G-6 breaks transport accuracy; summary content is not validated |
| A16 | **No** | Last at `b94727d` | Runbook changed since, recovery paths not re-exercised; G-11 |

No gate has live-level support from the harness. US-11.3's live install run is separate supplied evidence, not a profile result.

## DH-A12 separation

- **Installed configuration:** `.claude/settings.json` has five events, with `onFailure: block` on `PreToolUse`. `autobots.json` holds the allowlisted unqualified values. The last supplied adapter state is `configured_unqualified`, `delivery_unverified`, which is a configuration and version check only.
- **Deterministic tests:** `test_hooks.py` and `test_assistant_assets.py` feed synthetic stdin and stub CLIs. They show script behavior only.
- **Actual assistant event delivery:** not qualified. The record holds only incidental observations: one plugin `PreToolUse` event, one `Stop` in HARNESS-WORKTREE-ROOT-001 and the US-1.8 dispatcher incident. Claude's crash, timeout and Stop recursion behavior is not qualified.
- **Document check:** I found no document claiming delivery is proven or reporting script fixtures as delivery. `CODEBASE.md:105` is the one ambiguous sentence (G-17). The search was by pattern across `README*`, `CODEBASE.md`, SPECS, AGENTS, CLAUDE, `.claude`, `docs/engineering` and the two PRDs, and I read the long matches individually.
- **Marking still to do:** SPECS US-11.12 task 4 is TODO. US-10.2 marks crash and timeout, but no Gate 0 report exists at this revision.

## Persistent install and ordinary checks

The rule holds by code reading.
- `qualify_persistent_apply.py` uses its own `autobots-disposable-*` project. Its CLI cases use a temp directory and a project with no containers.
- `remove_stack` requires the disposable identity and labels first.
- `persistent_install.py` has no `down` or volume removal, and `reset` is always refused.

The rule depends on those guards, and only the disposable side is regression-checked (G-14).

## Delivery records

Routine stories are not faulted for lacking DH-W records, by Decision 0003, and AGENTS.md describes that exception. US-11.12's own acceptance does require them.

## Evidence limitations

- **Supplied reports predate this tree:**

| Report | Input fingerprint | Completed (UTC) |
|---|---|---|
| `full`, `db` | `6a46fed0…` | 15:36, 15:43 |
| `harness` | `7f80bd0e…` (manifest lacks Decision 0011) | 15:44 |
| `operations` | `6372cf85…` | 12:20 |

- **Rerun needed:** all profiles and the runbook exercise must be repeated after the fixes, and this review refreshed for the changed scope.
- **Validator vocabulary:** `evidence.py:139` accepts only `blocking` and `nonblocking`, so major and minor findings need mapping in the manifest. It also needs `outcome: approved` at the current fingerprint.

## Inspected

**Read in full:**
- Scripts: `verify.py`, `harness_lib.py`, `evidence.py`, `specs.py`, `disposable_db.py`, `app_db.py`, `persistent_install.py`, `qualify_persistent_apply.py`, `supabase_stack.py`, `toolchain.py`, `qualify_web.py`, `qualify_faults.py`
- Config and hooks: `.claude/settings.json`, `.claude/hooks/dispatch.py`, `.claude/autobots.json`
- Tests: `test_hooks.py`, `test_verify_profiles.py`, `test_assistant_assets.py`, `test_fault_fixtures.py`, `test_shared_form_controls.py`
- Documents: the harness PRD through DH-10, the harness runbook, the US-1.8 and US-10.2 summaries, Decisions 0003, 0009 and 0011

**Read in part:**
- `qualify_identity.py`, `qualify_upgrade.py`, `test_supabase_stack.py`
- `.claude/rules`: all eight, either read or seen in the injected context, except `contracts.md`, for which I saw only its path
- By test name only: `test_evidence.py`, `test_disposable_guard.py`, `test_app_db.py`, `test_generate_contracts.py`
- By grep only: `test_release_qualification.py`, `test_specs.py`, `generate_contracts.py`
- Supplied `.checks` reports, by grep

## Not inspected

- Full `qualify_operations.py`, `qualify_backup.py`, `local_backup.py` and `tests/db/*` check bodies, so their case logic is unreviewed
- Product code beyond the lines cited, and the spec files beyond `install.spec.ts`'s header
- `~/.local/share/autobots-install`, deliberately
- The 41 minors, majors M8, M30, M32 and M33, and WORKER-INFERENCE-001 dispositions
- Nothing was executed, so no fingerprint or runtime behavior was confirmed by me

**Overall outcome: changes_required.**
