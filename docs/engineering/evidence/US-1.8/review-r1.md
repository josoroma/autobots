# US-1.8 independent review, round 1

Persisted verbatim from the reviewer's final message. Dispositions are in [summary.md](summary.md).

**Reviewer:** separate read-only context, Claude (claude-opus-5-5); not the author. **Outcome: not approved; 6 blocking.**
**Scope:** requested files as read from the working tree (branch `delivery/epic-1`, HEAD `b94727d` per the session snapshot, uncommitted changes included). **No fingerprint established**, because I cannot compute hashes. Findings come from code tracing only.

**Blocking**

- **F-1** `scripts/evidence.py:316-326`. `record` checks only the source digest, ignoring report `status`, `inputs_unchanged_during_check` and `schema_version`.
  - Trigger: edit an input during `verify --profile harness`. The report says `failed`/unstable, but each check says `passed` and `input_manifest` holds the post-edit state.
  - Consequence: the manifest validates, certifying inputs the checks never saw. `test_evidence.py:254` reports have no status at all.
  - IDs: DH-09.2, DH-A11. Fix: apply `report_state`'s rules, exempting record files.
- **F-2** `evidence.py:69-110`. `validate` never ties checks to a run.
  - Trigger: a hand-written `passed` check plus current `fingerprints` output, with empty `.checks`. `complete` succeeds; `test_evidence.py:81,107` requires this. `plan['manual_checks']` (`:331`) gives the same path.
  - Consequence: the proposal's "closing the hand-written gap" is untrue.
  - IDs: DH-09.2, DH-W06, SP-021. Fix: bind derived checks to a report hash and fingerprint; label manual checks.
- **F-3** `evidence.py:333`. `record` hardcodes `exercised_evidence_ids: [evidence_id]`.
  - Consequence: an unexercised runbook passes `runbook_errors`.
  - IDs: DH-W05, DH-A14, DH-A16. Fix: require plan-supplied exercise evidence and reject its absence.
- **F-4** `scripts/verify.py:121`, `evidence.py:300-301`. Every toolchain step is recorded `static_or_fixture`/`none`, including fake-transport `pytest` and `disposable_qualification`. `record` ignores those values, defaults to `static`/`none`, and lets the plan set anything.
  - Trigger: a plan marking `harness.backlog_validation` as `live`/`openrouter_live` validates.
  - IDs: DH-A15, DH-09.2. Fix: a per-step classification table in the verifier; refuse plan overrides and any `live` class without a live run record.
- **F-5** `scripts/harness_lib.py:128-142,188-190`, `verify.py:83`. Scope is relative to `HEAD`.
  - Trigger: commit broken `services/agent` code, then run `fast`. Every application step is `not_run`, exit 0.
  - Consequence: the `Stop` hook also accepts a harness report for that code.
  - IDs: DH-05 ("A clean Git diff… is not proof"), DH-A11. Fix: derive scope by diffing `input_manifest` against the last passing application report.
- **F-6** `verify.py:70-75`. `tests_executed` counts skipped tests, and `skipped=` is never read.
  - Trigger: `@unittest.skip` on guard test methods, or the real skip at `test_disposable_guard.py:63`. The result stays `passed`; the manifest says "N tests".
  - IDs: DH-A11, DH-A15, SP-021. Fix: parse the skip count, record it, and treat unexpected skips as failure.

**Nonblocking**

- **F-7** `.claude/hooks/dispatch.py:34-36,67-71`. Guard gaps:
  - Name matching is case-sensitive, so `.ENV` passes; on case-insensitive APFS that would open `.env`.
  - `cat .env.local`, `cat .env;`, `docker volume rm autobots_db-data` and `docker-compose down -v` all pass.
  - The `Grep` tool is outside the matcher.
  - IDs: DH-05, DH-A03, DH-A10. Fix: casefold names and add these patterns, keeping the "not a sandbox" statement.
- **F-8** `scripts/disposable_db.py:306-313,550`, runbook `:74`. `other_resources` claims "start times", but the format has none and status is stripped, so a stopped or restarted unrelated container passes. The author disclosed IDs-only in the US-1.7 record; the docstring and runbook still overstate it. `leftovers.returncode` is unchecked and leftover containers are never checked. Separately, `rendered_refusals` (`:160`) ignores `network_mode: host` from `--compose-file`.
  - IDs: US-1.7, DH-A10. Fix: compare container ID plus `State.StartedAt`; check return codes; refuse host networking.
- **F-9** `disposable_db.py:520-564`, `scripts/qualify_faults.py:126-133`. These reports carry no input fingerprint, and a run ending in `Unavailable` writes nothing. Runbook `:71` then shows an earlier `passed` after an exit 2.
  - ID: DH-A11. Fix: delete the report at start and include the fingerprint.
- **F-10** `tests/db/worker_fixture.sql:47-73`. `apply_effect` and `complete` check neither lease nor status, so an expired, unreclaimed worker can complete, and `apply_effect(1,2,'new')` after success returns `applied`. Heartbeat has no positive control (`disposable_db.py:486-488`); `select false` would pass.
  - IDs: DH-A09, SP-010.
- **F-11** Tests that survive broken behavior (DH-A06, DH-A07, US-1.6):
  - `disposable_db.py:365`: the failing migration uses `apply_sql_file`, so removing the transaction at `:246` still passes.
  - `:387-391`: seed stability hashes only `app.notes`, and identical `ERROR:` strings compare equal.
  - `:460-466`: `status >= 400` counts a 500 as denial.
  - `test_disposable_guard.py:141-142` is vacuous; `:147` ignores `0.0.0.0:8080:8080`.
  - `qualify_faults.py:62`: marker `assert` may match a pytest crash's `_pytest/assertion` frames, contradicting its docstring.
- **F-12** Reporting (DH-09.2, DH-A04, DH-A12):
  - `verify.py:168`: the `db` report lists Docker and Supabase as `not_tested` although it ran them.
  - `report_check` drops `cwd`.
  - Tool versions beyond Python are hand-supplied.
  - Adapter status and `not_tested` never reach the manifest.
- **F-13** `harness_lib.py:97,100,105,117-125,167`:
  - Fingerprints skip symlinks, `.env.example`/`.envrc`, and `evidence/HARNESS-ADAPT-001/forward-fixture`, which `tests/harness` reads.
  - `tests/db`, `infra` and `scripts/disposable_db.py` map to `harness` only; the `Stop` part was disclosed in US-1.7.
  - A `full` report missing `mypy` or `pytest` stays current (`test_verify_profiles.py:137`).
  - IDs: DH-09, DH-09.2.
- **F-14** Runbook mismatches:
  - `:5` says no Docker is needed; `:67` needs it.
  - `:83` says `DATABASE_URL` naming another target is refused, but only the port is compared, so `postgres://u@prod.example:55400/p` passes (`disposable_db.py:147-151`).
  - `:116` is misleading given F-1.
  - `:137` is overstated given F-7.
  - `:61` ("any change") is overstated given F-13.
  - `:351` points exercise status only to US-1.2.

**Inspected, no defect found**

- Identity refusal before Docker, and label checks before `down`.
- Marker gating of `reset`/`migrate`; no path found from the default Compose file to an unmarked target. Verdict limited to wrapper logic.
- `exit_code_for` precedence and `operations` exit 2.
- Fail-closed dispatcher exits; `TimeoutError` is swallowed at several `except OSError` sites, but the traced paths still deny or block.
- `adapter_status` states: never `active`, and incompatible stays `inactive`.
- State transition table against SP-010.
- Socket block and fake transport, within their disclosed limit: the approved-model policy lives in the fake, not product code.
- No `{{` in the runbooks.

**Limitations**

- I executed nothing. Every trigger above is unexecuted, and the verification records remain author claims I did not reproduce.
- APFS case sensitivity on this machine and pytest's crash output are unconfirmed.
- Docker Compose and storage-api behavior is inferred.
- Not read: `scripts/specs.py`, `test_assistant_assets.py`, `tests/toolchain/**`.
- Read only as far as needed: the runbook's forward-ingestion section.

**Unresolved acceptance**

- `docs/engineering/work-items/US-1.8*` and `docs/engineering/evidence/US-1.8*` do not exist, so DH-A12, DH-A13 and DH-A16 and the "Close Gate 0 honestly" scenario cannot be assessed.
- Tasks 2.1 and 2.2 are ticked, but no retained evidence for them was inspected.
- Claude event delivery stays unqualified, so DH-A03's Claude part is not established.
- Any fix invalidates this review for the affected scope. Author self-review does not replace re-review.
