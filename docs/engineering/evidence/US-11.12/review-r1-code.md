# Independent review, round 1: EPIC-11 code

Saved as the reviewer returned it, at commit `5012235`. Read-only, and nothing was run.

# US-11.12 independent review: EPIC-11, US-11.1 to US-11.11

**Outcome: changes_required.** There are 2 blocking, 8 major and 9 minor findings. Nothing was run. "Confirmed by reading" means the code path was traced, not observed at runtime.

**Reviewer:** independent and read-only. I did not author this code and used only Read, Grep and Glob.
**Declared scope:** commit 5012235, manifest 4f1f26b965889cfef14be39591e3257950111b99f8715f67c93cf6632df186e8, `.checks/US-11.12/final-review/epic-11.diff`.
**Not established:** I could not compute the fingerprint, or confirm the working tree equals that commit. Surrounding code came from the working tree. Where I compared it with the diff, it matched.

## Blocking

**E-1. `goal`'s worker spends money the shared ledger never counts.**
- **Where:** `scripts/persistent_install.py:349` (Popen), `:361` and `:376` (totals filtered to this `run_id`); `services/agent/src/autobots/operations/worker.py:242-252`; `application/worker_leases.py:107-114`.
- **Cause:** the worker started with inference on calls `claim_next`, which takes any queued or expired job in any workspace with a key. It takes the oldest first. Its maintenance step can also admit due routines.
- **Consequence:** a goal the UI queued while no worker ran gets dispatched and billed. Only the `goal` run is settled to the ledger, so `shared_ledger_committed_micro_usd` understates spend and Decision 0009's US$1 cap can be passed. The watchdog is blind too, because it reads only this run. The runbook warns about this for workers in general, but `goal` has no guard.
- **Resolve:** before starting the worker, refuse if any other claimable run or enabled routine exists. Also add a `claim_run`-only mode for this path, and total all invocations created during the window.
- **Confidence:** confirmed by reading. Not exercised, because the US-11.3 install had no other queued run.

**E-2. The inspector states a false outcome and a false charge source for a reconciled call.**
- **Where:** `application/model_admission.py:276-283`; `run_projection.read_inspector`, which doesn't select `reconciled_at`; `contracts/run_workspace.py` `ModelCallView`; `apps/web/components/run-inspector.tsx:89` and `:105-109`.
- **Cause:** reconcile sets `status='succeeded'` and writes the typed amount to `charged_micro_usd`.
- **Consequence:** a call whose worker died mid-flight, with its reply lost, reads `executor, attempt 1: succeeded`. It also reads `Reported charge: US$0.00025`, a figure the owner typed, next to `Error: worker lost`. This is exactly the flow US-11.4 ships. It is false on a required audit screen and blurs MP-07's reported and estimated distinction.
- **Resolve:** expose a reconciled flag. Show the call as "outcome unknown, charge entered by the owner", and label the amount that way. Assert it in `slice-controls` or `slice-run-details`.
- **Confidence:** confirmed by reading.

## Major

**E-3. Idempotent replay ignores `run_profile`.**
- **Where:** `application/runs.py:177-187`; `api/run_routes.py:120-125`.
- **Consequence:** the fingerprint excludes `run_profile` and the policy. Reusing a key with a different model returns the earlier run, on the earlier model, as `replayed: true`, instead of `IdempotencyConflict`. The caller believes DeepSeek was frozen when Terra was. The UI isn't affected because it generates a fresh key per press, so this hits API clients.
- **Resolve:** add `run_profile` to the fingerprint and test it. Adding it only when set keeps existing receipts valid.
- **Confidence:** confirmed by reading.

**E-4. `schema_behind` can't see a column-only migration, so Operations can falsely read ready.**
- **Where:** `application/operations.py:67-68`, `REQUIRED_RELATIONS`.
- **Consequence:** the check only tests that relations exist. US-11.7's record says the real install stays at migration 32. Migration 33 only adds columns, so this release reports `schema_ready` and "Ready. New work can start." there. Meanwhile `/v1/approvals` and `approval_gate` would fail on the missing columns. `docs/engineering/runbooks/upgrade.md` says `schema_behind` means "migrations are still missing, and nothing is admitted", which isn't true here.
- **Resolve:** compare applied history with the release's expected newest migration, or check required columns. Also record whether the install has been migrated.
- **Confidence:** the code is confirmed by reading. The install's current state comes from the US-11.7 record and was not observed.

**E-5. A database error silently kills the lease keeper, just after a sleep.**
- **Where:** `application/goal_loop.py:465-468` (`discount_sleep` outside any try), `:472-480` (only `LeaseLost` caught), `:306` and `:337` (task cancelled, never awaited); `application/workflow_runner.py:304` and `:314`.
- **Consequence:** an `OperationalError` on the keeper's connection ends the keeper, and the main loop isn't told. That produces the failures US-11.10 fixed:
  - no discount, so sleep counts as active time;
  - no revive, so the lease expires and `_guard` or the fence refuses work, losing a paid reply.

  A workflow's run has the same exposure. Both real sleeps kept the connection, so this path has no evidence, and it isn't listed in US-11.10's limits.
- **Resolve:** catch the error, reconnect with a bound, and retain the discount for retry. Add a `wake_check` case that drops the connection.
- **Confidence:** the path is confirmed by reading. How often the connection really drops is unknown.

**E-6. The page says a charge was recorded when nothing was.**
- **Where:** `apps/web/components/run-controls.tsx:108-110`, `:91-104`; `api/run_routes.py:336-345`.
- **Consequence:** the route answers 200 with `reconciled_calls: 0` when no open call remains, such as from a stale tab. The page ignores that and shows "The charge is recorded against the oldest open call", discarding the typed amount. I rated this major rather than blocking because the trigger is narrow and the call was already settled. Separately, `0` or a sub-micro amount rounds to 0 and closes the call's hold.
- **Resolve:** read `reconciled_calls` and say nothing was recorded when it's 0. Refuse an amount that rounds to 0 unless zero was explicitly entered.
- **Confidence:** confirmed by reading.

**E-7. The real install's database passwords go on a command line.**
- **Where:** `scripts/app_db.py:55`, reached through `persistent_install.py` `apply` and `goal`.
- **Consequence:** `-e PGPASSWORD={password}` puts the migrator and runtime passwords in `docker compose` argv, visible in the process list. `goal`'s polling repeats this about every 3 seconds. The helper was written for disposable stacks, and the persistent path inherited it.
- **Resolve:** set `PGPASSWORD` in the Compose process's environment and pass only `-e PGPASSWORD`.
- **Confidence:** confirmed by reading. I found no secret in logs or reports. The role bootstrap uses psql variables, and `run()`'s timeout message omits argv.

**E-8. The real install's wrong-password test can't fail, and US-11.3's record relies on it.**
- **Where:** `apps/web/tests/browser/install.spec.ts:19-22`; US-11.3 `verification.md`, `local-app.md` row.
- **Consequence:** `toHaveCount(0)` runs right after the click and passes before the sign-in reply arrives, so even a correct password would pass. The claim "a wrong password refused" on the install isn't established by this assertion. `identity.spec.ts:61` covers the behavior on a disposable stack only. The same record's "wrong password refused" on the restored copy has no assertion I could locate.
- **Resolve:** assert the sign-in failure message and the absence of a session, then re-observe or correct the record.
- **Confidence:** confirmed by reading.

**E-9. `goal` doesn't settle honestly on every path.**
- **Where:** `scripts/persistent_install.py:359`, `:376-380`, `:381-391`; `operations/worker.py:102-116`.
- **Consequence:**
  - On timeout, spend is read while the worker still runs. It can keep dispatching for up to 30 seconds of drain, yet the entry is settled from the earlier read. The 900-second active limit makes this path rare.
  - A run that exits the loop `paused` or `waiting_*` is settled as `settled`, though a later resume spends outside the ledger.
  - An exception before the report is written, including a failed `usage` or `leaks` helper after settlement, leaves no outcome report. The story requires one whether the goal succeeded or failed.
- **Resolve:** stop the worker first and then read. Keep the budget held while the run is non-terminal. Write the report in `finally`.
- **Confidence:** confirmed by reading.

**E-10. A model choice can pause a long run with no warning where the choice is made.**
- **Where:** `apps/web/components/expert-editor.tsx:92-93`; `application/goal_loop.py:513-522`; `apps/web/components/run-workspace.tsx:~427`; `apps/web/components/run-disclosure.tsx:117`.
- **Consequence:** "Model for its work" binds only `executor`, and an Expert's binding stays ahead of a per-run pick. So the summarizer can differ from the executor, and compaction then pauses with `route_not_bound`. Reading the code, a resume hits the same stop again, because the frozen policy doesn't change. The run page and disclosure say other roles "don't take effect", while only Settings mentions the pause, and only for workspace policy. Decision 0009 accepts the behavior, but these screens state it wrongly.
- **Resolve:** name the summarizer consequence wherever the frozen or disclosed map differs, or bind the summarizer along with the Expert's executor.
- **Confidence:** the code is confirmed by reading. Not observed, and US-11.6 records the pause as not exercised.

## Minor

**E-11. The active-time discount is unfenced and unbounded.**
- **Where:** `application/run_usage.py:76-83`; `application/goal_loop.py:465-468`.
- **Consequence:** it has no generation check and runs before the heartbeat. A worker that has lost the run can move the new owner's segment forward, and a wall-clock step counts as sleep. The segment can pass the current time, making `active_seconds` shrink or go negative, since no constraint stops it. US-11.10 records only the "Docker's clock doesn't catch up" case.
- **Resolve:** condition on current ownership and cap the discount at elapsed segment time.
- **Confidence:** confirmed by reading.

**E-12. "A bad line is skipped" is only partly true.**
- **Where:** `application/operations.py:138-152`; `api/operation_routes.py:131-134`.
- **Consequence:** valid JSON of the wrong shape, an extra field (the contract forbids extras) or non-UTF-8 bytes raises, and the whole Operations response becomes a 500.
- **Resolve:** validate per line inside the loop.
- **Confidence:** confirmed by reading.

**E-13. A failed restore record can lose the result.**
- **Where:** `scripts/local_backup.py:420-423`, `:439-441`, `:443-448`.
- **Consequence:** an `OSError` from `record_restore` is uncaught and happens before the print, so `verify` loses its cases and `restore` loses its ports. A `Refused` or failed `verify` records nothing, so Operations keeps showing the last entry. `restores.jsonl` itself holds nothing identifying.
- **Resolve:** print first and treat the record write as a separate, reported failure.
- **Confidence:** confirmed by reading.

**E-14. The reasoning trial can spend and leave no report.**
- **Where:** `services/agent/src/autobots/operations/reasoning_trial.py:363-366`, `:292`.
- **Consequence:** a `Refused` or `ModelUnavailable` on a later route returns before `write_report`, and a non-JSON 200 from `/key` raises uncaught. Earlier trials' results are lost, though the ledger keeps their spend.
- **Resolve:** catch per trial and always write the report.
- **Confidence:** confirmed by reading.

**E-15. The ledger has no lock.**
- **Where:** `operations/route_qualification.py:113-118`, `:127-135`.
- **Consequence:** `goal` holds the entries in memory for its whole run. A concurrent trial or goal is overwritten at settle, which undercounts the cap.
- **Resolve:** take a file lock and re-read before each write.
- **Confidence:** confirmed by reading, with a single operator making this unlikely.

**E-16. The apply guard has small gaps, and none of them reaches another project.**
- **Where:** `scripts/persistent_install.py:221-224`, `:250`, `:264`, `:147`.
- **Consequence:**
  - `first_setup` doesn't check the published port.
  - A changed `bootstrap/storage.sql` is silently never reapplied.
  - An applied migration missing from the folder, as with an older checkout, isn't refused, and that checkout's seed still runs.
  - The port check is a substring match, so an extra wildcard publication beside the recorded one would pass it. `up`'s render check still guards that.
- **Resolve:** tighten each check to match what the runbook describes.
- **Confidence:** confirmed by reading.

**E-17. The inspector and budget views are inconsistent.**
- **Where:** `run_projection.py` `read_inspector` and `_evidence`; `apps/web/components/run-workspace.tsx`, the Budgets card; `application/model_admission.py:147`.
- **Consequence:**
  - Model calls include child runs, but tool attempts, checkpoints and evidence don't.
  - Evidence links match on basename only, so a reference can link to a different same-named artifact in the run.
  - "Spend limit" shows `r.limit_micro_usd`, while admission enforces the lesser of that and the workspace limit, and the US$5 daily cap isn't shown anywhere.
- **Resolve:** apply the same tree scope to all three lists, match evidence on the full path, and show the effective limit.
- **Confidence:** confirmed by reading.

**E-18. Some tests and evidence assert less than they appear to.**
- **Where:** `apps/web/tests/browser/operations-history.spec.ts:30-35`, `:55`; `apps/web/tests/browser/slice-visual.spec.ts:144-145`, `:613`; `.checks/mac-sleep-second-report.json`; `docs/engineering/runbooks/operations.md`, Mac sleep section.
- **Consequence:**
  - The browser `/chat/completions` listener can never fire, since model calls are server-side. The upstream log check in `qualify_identity` is the real evidence, and it spans the whole run.
  - Radios and checkboxes are excluded from boundary contrast, and US-11.11's limits don't say so.
  - The "every control" keyboard title covers only the goal and model fields. The summary is honest about this.
  - The second sleep report shows generation 1 and `lease_lost: 0`, but no event records whether `revive_lease` ever ran in a real sleep. It may only be proven by arranged clocks.
  - `operations.md` states the `uncertain_acceptance` wake path flatly, though US-11.10 says it wasn't exercised.
- **Resolve:** remove or fix the listener, measure or disclose the excluded controls, log a revive event, and qualify the runbook sentence.
- **Confidence:** confirmed by reading.

**E-19. Stored qualification text is faithful to US-3.4, but omits two things.**
- **Where:** `supabase/migrations/20261106000031_route_qualifications.sql:20-26`.
- **Consequence:** dates, configuration, pins and listed limits all match. US-3.4's open item on concurrent admission (MP-A09) isn't listed. DeepSeek reads "Qualified, with the limits below", and the US-11.9 picker offers it, while nothing on those screens mentions that `operations.md` records it failing real goals 0 of 5, from reasoning consuming the 512 tokens. The story sourced only US-3.4, so this is an omission rather than a mismatch.
- **Resolve:** add both through a new migration, never by editing an applied one.
- **Confidence:** confirmed by reading.

## Checked, with no finding in this scope

- **Reviving a lease and SP-012:** `_claim` raises the generation under a row lock, and revive requires the same generation and owner. A race resolves to one owner. Writes check that the lease is live. I found no path to two owners acting.
- **Wrong-target apply:** I found no path to another project. The name, label, port and identity row are all read before any write, and migration files are checked before the first one applies. `reset` is refused. A restored copy needs the `autobots-disposable-*` prefix, the identity row and the hold.
- **SQL built from strings:** values are validated filenames, UUIDs from the application, or the record's own fields. An unvalidated `--project` is refused by the Docker lookup before any SQL. I found no reachable injection.
- **Workspace isolation and private fields:** all the new reads go through `_require_run` or a workspace filter. The inspector selects typed columns only, with no checkpoint content, tool arguments or partial output.
- **Reasoning metadata:** only paths, counts and truncated kinds reach reports and logs.
- **Trial cap:** the check happens before the first call, and each call is reserved at its worst case before dispatch. `max_tokens` is 512, matching the worst-case figure.
- **Role checks:** reconcile and `put_model_policy` need an owner, and Operations needs an owner while the database is up.
- **Unapproved models:** an unknown `run_profile` gets a 422.
- **Disclosure:** its precedence matches `resolve_role_policy`.
- **CSRF:** all new mutations use `csrfFetch`, and the BFF guards them.
- **Backup age:** `restores.jsonl` doesn't affect it, because age comes from the manifest.
- **Reconcile coverage:** the form's `unreported_charges` are `status='uncertain'`, so the route does handle them. I had suspected otherwise.
- **Records that check out:**
  - US-11.2's and US-11.3's spend arithmetic is correct: 17 calls, US$0.002201, then US$0.008174 across 18 entries.
  - The ledger file shows committed 8174.
  - The second sleep report shows 540.4 seconds, no repeated steps and no failures.

## Inspected and not inspected

**Inspected:**
- the whole diff, all 8,054 lines;
- SPECS EPIC-11;
- Decisions 0009, 0010 and 0011;
- the 11 verification records, plus the US-3.4, US-11.11 and the start of the LIVE-GOAL-1 summaries;
- surrounding code in `worker_leases`, `goal_loop`, `workflow_runner`, `worker`, `run_usage`, `recovery`, `model_admission`, `runs`, `run_routes`, `settings_routes`, `operation_routes`, `operations`, `route_qualification`, `openrouter_metadata`, `local_backup`, `app_db`, `disposable_db`, `supabase_stack`, `bff`, `session-panel` and `approvals-panel`;
- the SP-010 and SP-012 contract sections, MP-07, and PRD 12.1 by grep.

**Not inspected:**
- generated clients and screenshots;
- `live_goal_helper.py`;
- `compose.overlay.yaml`;
- the Local Mac and Design System PRDs in full;
- most raw `.checks` reports, including qualifier case counts and "checks exit 0" claims, which I treated as supplied claims;
- the install's actual state.

Dispositions for the 41 minors, M8, M30, M32, M33 and WORKER-INFERENCE-001 are the coordinator's and weren't part of this request. H1 and product acceptance are not assessed.

**Overall: changes_required.** E-1 and E-2 must be resolved, the affected scope reviewed again and the fingerprint bound anew, per US-11.12's third scenario.
