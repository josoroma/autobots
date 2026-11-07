# US-12.8 evidence summary: review and Gate 0 after the last decisions

The review of what changed since US-12.3's binding, and the repeated Gate 0, on 2026-11-06. Manifest: [gate-0.json](gate-0.json). Source fingerprint `51212ae1…`. Raw reports are in ignored `.checks`, and the results here stand without them.

**Result:** every portable gate below has passing evidence at its stated level, and DH-A03 stays partial by Decision 0012. **Nothing here is live. No paid call or persistent change was made, as Decision 0014 authorizes none, and the real install wasn't touched.** This doesn't claim H1 or product acceptance, which belong to [US-10.2's assessment](../US-10.2/summary.md).

**The H0 and H1 baseline:** US-1.3 to US-1.7 have no DH-W record, under Decision 0003. This record carries their baseline, as H1.3 allows by [Decision 0013](../../decisions/0013-release-closure.md), now that US-12.3's record is void.

## What ran earlier

The live and real-sleep evidence ran before this binding, and wasn't repeated.

| Evidence | Ran at |
|---|---|
| [US-12.4](../US-12.4/summary.md)'s two-call workload | Round 5 at `05916d5e…`. Rounds 1 to 4 at `09ea61fb…` |
| [US-12.5](../US-12.5/summary.md)'s third real sleep | `05916d5e…`, by the author's statement and the timeline |
| [US-12.6](../US-12.6/summary.md)'s real install and goal | `05916d5e…`, by the author's statement and the timeline |
| [US-11.11](../US-11.11/summary.md)'s 42 captures and the keyboard walk | `05916d5e…`'s tree, by the author's statement. US-12.7 changed no screen |

**The inputs that differ from `05916d5e…`**, by `git diff 70c5162`, leaving out records the fingerprint excludes:

- `PRD-Local-Mac-Deployment.md`, LM-07 and LM-A04
- `docs/engineering/decisions/0014-release-limits-accepted.md`
- `services/agent/src/autobots/adapters/loop_middleware.py` and `application/model_attempts.py`, the event and one optional field
- `services/agent/tests/test_worker_inference.py`, `tests/db/verification_check.py`, `tests/db/product_inference_worker.py` and `scripts/qualify_worker_inference.py`, the checks

The operations runbook changed too, and has its own revision hash. No migration, no screen. The new code path runs only when a call's outcome is unknown, so a successful goal does the same work as before, by reading, and no live run shows it.

## Gate 0 by DH-A gate

| Gate | State | Class, model transport | Observed |
|---|---|---|---|
| DH-A01 | Passed | static, none | `project_configuration` passes |
| DH-A02 | Passed | static and disposable, none | `operations`, `db`, `full`, `fast` and `harness` exit 0 under `env -i PATH HOME`. With `PATH=/usr/bin:/bin`, `full` exits 2, status error |
| DH-A03 | **Partial, by [Decision 0012](../../decisions/0012-unqualified-hooks-in-h1.md)** | mock, none | Script fixtures pass. Hook delivery isn't qualified |
| DH-A04 | Passed | mock and disposable | `fault_qualification` passes. A committed type fault in a disposable copy: `fast` exit 1 on `mypy` alone, with a clean Git tree. Corrected: exit 0 |
| DH-A05 | Passed, fixture level | mock, mock | The state fixture detects bad transitions, a wrong reducer and a private key in an event. Not linked to the product's machine |
| DH-A06 | Passed, synthetic | disposable, mock | Replay, repeated apply, rollback, upgrade with data, two seed runs. The persistent apply's refusals, 29 cases |
| DH-A07 | Passed, synthetic | disposable, mock | Real `anon` and `authenticated` roles, real Auth tokens and real `storage-api`, not a persistent target |
| DH-A08 | Passed | mock, mock | The real adapter over a fake transport, by `qualify_worker_inference.py` and the identity suite |
| DH-A09 | Passed, disposable | disposable, mock | Crash, duplicate and lease expiry are fenced |
| DH-A10 | Passed | disposable, none | Loopback only, labeled, digest-pinned. Other Docker resources unchanged, 45 before and after |
| DH-A11 | Passed | mock and disposable | An arranged skipped test fails `harness`, exit 1 with 284 executed and 1 skipped |
| DH-A12 | Passed | this report | Configuration, deterministic tests and event delivery are separate here |
| DH-A13 | This record | n/a | `scripts/evidence.py complete US-12.8` passing is the check. It shows consistency, not correctness |
| DH-A14 | Passed | mock | The validator's refusal cases, in the harness tests |
| DH-A15 | Passed | mock | Class and transport are the verifier's. `live` with a fake transport is refused |
| DH-A16 | Passed | disposable | Runbook exercised: a stale lock exits 2 and recovers, a killed run left 1 container and 1 volume, which `cleanup` removed. Arranged adapters read `inactive`, and the real client `configured_unqualified` |

## Results on these inputs

Bound to one source fingerprint, in the manifest. A reviewer can't compute a hash, so I bound it to the tree round 3 read, and compared the two: equal. `fast` also exited 0 under `env -i`, kept in the retained output.

| Check | Class, model transport | Result |
|---|---|---|
| `harness` | static and mock, none | exit 0, 284 harness tests |
| `full` | static, mock and disposable | exit 0, 24 checks, including `contract_drift`, 554 Python tests by collection, and 32 browser tests |
| `db` | disposable, mock | exit 0: `disposable_db` 44 cases, `supabase_stack` 18, `app_db` 449, `qualify_identity` 447, `qualify_persistent_apply` 29 |
| `operations` | disposable, scripted model | exit 0: operations 69 cases, backup 50, upgrade 45 |
| `qualify_worker_inference.py` | disposable, mock | exit 0, 55 of 55 cases. In no profile, so run here by hand |
| [US-10.2's closing checks](../US-10.2/closing-checks.json) | disposable, scripted model | Held, at this fingerprint: cancelling running runs, a cut stream, the secret scan |

## Mark on the hooks

Hooks fired throughout this delivery. That's an observation, not qualification. Nothing shows what Claude does when one crashes or times out, or how Stop recursion behaves. Script fixtures aren't reported as event delivery. The adapter reads `configured_unqualified`, `delivery_unverified`.

## Dispositions

Reports: [round 1](review-r1.md), [round 2](review-r2.md), [round 3](review-r3.md). Each was a fresh read-only context, and none ran anything.

| Finding | Outcome |
|---|---|
| RG-1 to RG-4, blocking | Fixed. RG-1 was a check of mine that couldn't fail, and its replacement showed the opposite of what the record said |
| RH-1 to RH-4, blocking | Fixed. Each behavior now has a check that fails without it, by the reviewer's reading. No mutation was run |
| RG-5 to RG-11, RH-5 to RH-10, RJ-1 to RJ-4 | Fixed, as each round's report sets out |

Round 3 approved, on the tree this binds.

## Failures, errors, skips and limitations

- **Not exercised:** anything live at this fingerprint, a real sleep or the real install on this code, and the new event catching a real pause.
- **Limits:**
  - **Reviewers read and don't run,** so what a mutation would do is from reading the code.
  - **The install is stopped at migration 35 of 35.** This story adds no migration, so it isn't behind.
  - **Earlier limits stand,** in [US-12.3's](../US-12.3/summary.md#failures-errors-skips-and-limitations) and [US-10.2's](../US-10.2/summary.md#limits-on-the-release-as-it-stands) records.
- **Spending:** none. The shared ledger stands at US$0.315650 of the US$1 cap.
- **Skips:** none. A skipped test fails the profile.

## Reproduction

```sh
python3.12 scripts/verify.py --profile harness
python3.12 scripts/verify.py --profile fast
python3.12 scripts/verify.py --profile full
python3.12 scripts/verify.py --profile db
python3.12 scripts/verify.py --profile operations
python3.12 scripts/qualify_worker_inference.py
python3.12 scripts/evidence.py validate US-12.8
```

`.checks/US-12.8/gate-0/` keeps the recovery and arranged-fault procedures, hashed in the manifest, with their output beside them. It's ignored and local, so the results above stand without it.
