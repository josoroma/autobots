# US-1.8 independent review, round 2

Persisted verbatim from the reviewer's final message.

**Reviewer:** the same separate read-only context, so independent of the author but not fresh. **Outcome: not approved.** One code item blocks (N-1). Any fix needs re-review of the affected scope. **No fingerprint established;** the coordinator must bind one.

**1. Prior findings**

| ID | State | Location and remainder |
|---|---|---|
| F-1 | Resolved | `evidence.py:204-215` |
| F-2 | Partly | `:218-249` works, but N-1 remains |
| F-3 | Partly | `:169-171,395,401`, but N-1 remains. A manual exercise stays self-asserted (disclosed) |
| F-4 | Resolved | `verify.py:32-43,144`; `evidence.py:243-244,358` |
| F-5 | Resolved | `harness_lib.py:152-174`, `verify.py:140` |
| F-6 | Mostly | `verify.py:76,80-96`. Unjudged: `toolchain_scope_tests` and pytest cases in fault qualification |
| F-7 | Partly | `dispatch.py:73` misses quoted and `$HOME` paths to the secret file. `:60` remains case-sensitive |
| F-8 | Resolved | `disposable_db.py:170,310-328,584-590` |
| F-9 | Partly | `disposable_db.py:562`, `qualify_faults.py:119,134`. Nothing compares the new fingerprint; see N-2 |
| F-10 | Resolved | `worker_fixture.sql:52,70`, `disposable_db.py:504,513,530`. The 1-second leases can flake, failing closed |
| F-11 | Resolved | `disposable_db.py:355,383,410,488`, `qualify_faults.py:62` |
| F-12 | Partly | `verify.py:192` still lists Docker and Supabase; see N-4 |
| F-13 | Partly | `harness_lib.py:77-79`: a symlink to an existing directory is invisible. `:115` still excludes `.envrc` |
| F-14 | Partly | Runbook `:61` ("Links count") and `:116` ("hand-written `passed` fails") are overstated. `:351` still points to US-1.2 |

**2. New defects**

- **N-1, blocking.** `evidence.py:191-200`, `:228` and `:169-170` accept a manual check whose artifact is never verified.
  - Trigger: `source.kind: manual`, `exercises_runbook: true`, any path under the expected root, `sha256: '0'*64`, `availability: deleted`, with an empty `.checks`. `complete` succeeds.
  - `test_evidence.py:220-224` enshrines the deleted-artifact state, and the docstring at `evidence.py:6` says a hand-written result cannot pass.
  - This needs no `.checks` edit, so the disclosed forgery limit does not cover it. `deleted` is also a documented, ordinary state.
  - IDs: DH-09.2, DH-A14, DH-A16, US-1.5. Fix: require `available` for manual checks and runbook exercise when completing, and correct the docstring.
- **N-2, nonblocking.** `test_disposable_guard.py:118-123` runs the real `qualify`, which unlinks the repository's `.checks/db/qualification.json` (`disposable_db.py:562`). Every later `harness`, `fast` or `full` run deletes it. Fix: unlink after the Docker check, or use a temporary root.
- **N-3, nonblocking.** `report_problem:208` allows a failed report, and `provenance_errors` doesn't require all its checks. A manifest trimmed of the failing check validates. Fix: require `status == 'passed'` in `provenance_errors`.
- **N-4, nonblocking.** `evidence.py:361` records `cwd: '.'` for steps run in `services/agent`, because `run_step` has no `cwd`. `tool_versions` (`:372-377,399`) reads versions at record time, overwrites the report's `python`, and has no positive test.
- **N-5, tests.**
  - The wiring at `verify.py:76` and `:148-149` is untested. Removing the `:148-149` pytest call would fail open.
  - No test picks between passing `fast` and `full`, so `max` at `harness_lib.py:158` could change undetected. No fail-open path found there.
  - `test_verify_profiles.py:239` uses a broken link, which hides the F-13 gap.

No fail-open path found in `scope_paths`, `needs_profile` or `evidence_state`: each passing `fast` verifies the domains changed since its base, a failed latest report drops that base, and scope falls back to full inputs.

**3. Disclosed limits**

None of the three should block, provided the Gate 0 report states them:

- Grep outside the hook matcher: hooks are declared guardrails, and Bash can already read files.
- `.checks` hand-editing: acceptable once N-1 is fixed.
- `validate` needing cited reports: it fails closed, and the summary must preserve results.

**Blocking Gate 0**

- N-1.
- Current evidence is also missing: no US-1.8 work record, manifest or Gate 0 table exists, only `review-r1.md`. Final-input `harness`, `full` and `db` results and the runbook exercise were not inspected, so DH-A12, A13, A16 and "Close Gate 0 honestly" stay unassessed.

The other open items may stay open if disclosed.

**Limits**

- I executed nothing. All triggers come from code tracing, and the claim that Docker, pytest and Compose behave as assumed is untested by me.
- The prior round's unread files were still not read.
- This round read `dispatch.py` and `harness_lib.py` only to the changed regions, `test_hooks.py` by search only, and the runbook through line 125 plus `:351`.
- Delegated claims were not taken as established.
