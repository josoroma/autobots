# US-1.8 evidence summary — gate-0

The Gate 0 report for the portable baseline, on top of revision `b94727d`, 2026-11-05. Manifest: [gate-0.json](gate-0.json). Raw reports are in ignored `.checks`, and the results here stand without them.

**Result:** every portable gate below has passing evidence at its stated level, except that DH-A03's Claude part and all real event delivery remain unqualified. This does not establish product acceptance, the persistent stack, or live inference.

## Gate 0 by DH-A gate

| Gate | State | Class, model transport | Observed |
|---|---|---|---|
| DH-A01 | Passed | static, none | `project_configuration` passes: configuration, documents, rules and hook settings |
| DH-A02 | Passed | static and disposable, none | `harness`, `fast`, `full` and `db` exit 0 under `env -i PATH HOME`. With no `claude` on `PATH`, `harness` exits 0. With `PATH=/usr/bin:/bin`, `full` exits 2. Retained in `portable.txt` |
| DH-A03 | **Partial** | mock, none | Script fixtures pass for malformed input, metacharacters, symlinks, timeout and a missing library. **Claude's own crash, timeout and Stop recursion behavior is not qualified** |
| DH-A04 | Passed | mock and disposable | 21 of 21 fault cases as expected. Committed type fault: `fast` exit 1 on `mypy`, corrected exit 0. Versions are in the manifest |
| DH-A05 | Passed, fixture level | mock, mock | Invalid transitions, a wrong reducer and a private key in a public event are detected. The product's state machine does not exist yet |
| DH-A06 | Passed, synthetic | disposable, none | Fresh replay, repeated apply, rollback, upgrade with data, two seed runs. Persistent target refused before any Docker call |
| DH-A07 | Passed, synthetic | disposable, none | Real `anon` and `authenticated` roles and real `storage-api`. Anonymous and cross-workspace access get 4xx or denial, with positive controls |
| DH-A08 | Passed | mock, mock | Both approved wire IDs through the real adapter over a fake transport. Unapproved model, fallback array and missing key refused. The real transport is blocked with an arranged placeholder key, not a real one |
| DH-A09 | Passed, stub | disposable, none | Crash, duplicate and lease expiry: fenced, no repeated effect, completes once. The real worker comes later |
| DH-A10 | Passed | disposable, none | Loopback only, labeled, digest-pinned. Other containers' IDs and times and volume names unchanged, 32 before and after. Generated secrets are not written by the code. No check asserts their absence; the reviewer's pattern search of reports found none, and it cannot recognize raw generated values |
| DH-A11 | Passed | mock and disposable | An untracked input makes a report stale. A committed change stays in scope. A skipped test fails |
| DH-A12 | Passed | this report | Configuration, deterministic tests and event delivery are separate here. Nothing is marked activated |
| DH-A13 | This record | — | `scripts/evidence.py complete US-1.8` passing is the check. It shows consistency, not correctness |
| DH-A14 | Passed | mock | Rejects templates, missing reviewer or runbook, changed fingerprints, inconsistent status, open blocking findings and results citing no run |
| DH-A15 | Passed | mock | The verifier assigns class and transport. `live` with a fake transport, and any manual `live`, are refused |
| DH-A16 | Passed | disposable | Runbook exercised, including stale lock and killed-run recovery. Retention below |

## Optional adapter

- **Real, observed:** `configured_unqualified`, `delivery_unverified`, CLI 2.1.314.
- **Arranged, unavailable:** `PATH=/usr/bin:/bin`: `harness` exit 0, `inactive`, `unavailable`.
- **Arranged, incompatible:** a stub reporting 2.1.200: `harness` exit 0, `inactive`, `version_below_minimum`. The real client is compatible by version, so this condition does not hold naturally.
- `not_tested` lists Claude event delivery in each report. `assistant.event_delivery_qualification` stays `not_tested`.
- **Incidental, not qualification:** project hooks visibly fired in this session. A syntax error in the dispatcher made `onFailure: block` refuse every matched tool. That is one observation of fail-closed behavior, and it does not qualify the adapter.

## Reproduction

```sh
python3.12 scripts/verify.py --profile harness
python3.12 scripts/verify.py --profile fast
python3.12 scripts/verify.py --profile full
python3.12 scripts/verify.py --profile db
python3.12 scripts/qualify_faults.py
python3.12 scripts/evidence.py validate US-1.8
sh .checks/US-1.8/gate-0/exercise.sh
sh .checks/US-1.8/gate-0/committed_fault.sh
```

The last two are the recovery and arranged-fault procedures, retained and hashed. They are ignored local files, so `exercise.txt` keeps their results. The recovery steps: `echo <dead pid> > .checks/verify.lock`, see exit 2, confirm the PID is not running, remove the lock, rerun; and for a killed `qualify`, `python3.12 scripts/disposable_db.py cleanup --project autobots-disposable-<id>`.

Runtime versions are in the manifest's `tool_versions`, read at record time.

## Review dispositions

Rounds: [1](review-r1.md), [2](review-r2.md), [3](review-r3.md). The same context ran all three, so it was independent of the author but not fresh, and it executed nothing.

| Finding | Disposition |
|---|---|
| F-1 to F-6, N-1, blocking | Resolved. F-5 and F-6 also observed on real runs |
| F-7 hook guard gaps | Fixed for case, quotes and listed commands. Accepted: the `Grep` tool stays outside the matcher, and other shell forms get through. The hook is a guardrail, not a sandbox |
| F-8 to F-11 | Fixed |
| F-12 reporting | Fixed |
| F-13 fingerprints | Fixed for links, `.env.example`, the forward fixture, domains and `full` completeness. Accepted: every name starting `.env` except `*.example` stays excluded as secret-like, which also excludes a name such as `.environment.py` |
| F-14, N-3, N-5 | Fixed |
| N-2 | Changed: the report is removed only once Docker is reachable. Accepted: with Docker unreachable, an earlier `qualification.json` stays, so the runbook says to trust the exit code and `latest.json` |
| N-4 | Fixed for `cwd`. Versions are read at record time, and no test asserts them |

## Failures, errors, skips and limitations

- **Self-inflicted lockout.** A quoting error in a regex broke the dispatcher, which then blocked all my tools. Repaired by one terminal command that the user approved. The dispatcher's parse is covered by harness tests, which fail at import.
- **A scope test I broke.** US-1.7 broke `tests/toolchain/test_scaffold_scope.py`, unnoticed until this story, because no profile ran it. `full` now does. The rest of `tests/toolchain` needs registries and is not in any profile.
- **Vacuous pass caught in US-1.7.** A member at first read nothing, so the denials proved nothing. A positive control now exists.
- **Provenance is not forgery resistance.** Files in `.checks` can be edited by hand, a manual result is the author's assertion backed by its artifact, and `validate` needs the cited reports present.
- **R-1, open and nonblocking:** `validate` accepts `exercises_runbook` on a report-cited check, so a hand-added fake artifact there could claim an exercise. It should be restricted to manual checks. This manifest's exercise is on a manual check.
- **Review binding:** the reviewer accepted the fingerprint only while `fingerprints` still prints it and `validate` exits 0. A non-record input change voids the approval, and a runbook edit needs its own re-exercise.
- **Not covered:** generated contract and database type drift, as none exist; browser fixtures; the persistent stack and the release US-2.1 pins; real Auth tokens, as Storage tokens are fixture-signed; concurrency under load, as claims are sequential, and worker cases use 1-second leases, which fail closed if slow.
- **`Stop` and `db`:** database inputs now require a `db` report, so a machine without Docker gets one block per stop, then proceeds with the limitation stated.
- **Earlier routine stories** had no independent review, by Decision 0003. This review covers their baseline code as it stands now.
- **No skipped tests** in the final runs: 190 harness tests executed, 0 skipped.

## Raw artifacts

`.checks/US-1.8/gate-0/` holds `exercise.sh`, `exercise.txt`, `committed_fault.sh`, `committed_fault.txt` and `portable.txt`, hashed in the manifest and available. Keep them through acceptance. Removing them makes `validate` fail visibly, since the manual checks rely on them. Verifier reports in `.checks/<profile>/` are overwritten by later runs, so `validate` is expected to fail once inputs change.
