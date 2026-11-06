# US-12.3 evidence summary: final review and Gate 0

The final review of EPIC-12 and the repeated Gate 0, on 2026-11-06. Manifest: [gate-0.json](gate-0.json). Raw reports are in ignored `.checks`, and the results here stand without them.

**Result:** every portable gate below has passing evidence at its stated level, and DH-A03 stays partial by Decision 0012. **Nothing here is live, no real model call was made, and the real install wasn't touched.** This leaves H1 and product acceptance to US-10.2, and establishes neither. Later source changes void this binding, as `scripts/evidence.py` decides, which leaves out `SPECS.md`, `CODEBASE.md` and evidence as records.

**The H0 and H1 baseline:** US-1.3 to US-1.7 have no DH-W record, under Decision 0003. This record carries their baseline, as H1.3 now allows by [Decision 0013](../../decisions/0013-release-closure.md).

## Gate 0 by DH-A gate

| Gate | State | Class, model transport | Observed |
|---|---|---|---|
| DH-A01 | Passed | static, none | `project_configuration` passes: configuration, documents, rules and hook settings |
| DH-A02 | Passed | static and disposable, none | `operations`, `db`, `full`, `fast` and `harness` exit 0 under `env -i PATH HOME`. With `PATH=/usr/bin:/bin`, `full` exits 2, status error. With no `claude` on `PATH`, `harness` exits 0 |
| DH-A03 | **Partial, by [Decision 0012](../../decisions/0012-unqualified-hooks-in-h1.md)** | mock, none | Script fixtures pass for malformed input, metacharacters, symlinks, timeout and a missing library. Hooks are on as guardrails, configured and not qualified. **Claude's own crash, timeout and Stop recursion behavior is not qualified** |
| DH-A04 | Passed | mock and disposable | 21 of 21 fault cases as expected. A committed type fault: `fast` exit 1 on `mypy` alone, with a clean Git tree. Corrected: exit 0. Versions are in the manifest |
| DH-A05 | Passed, fixture level | mock, mock | Invalid transitions, a wrong reducer and a private key in a public event are detected. The fixture isn't linked to the product's machine |
| DH-A06 | Passed, synthetic | disposable, mock | Fresh replay, repeated apply, rollback, upgrade with data, two seed runs. The persistent apply refuses its unsafe cases, on a disposable stack |
| DH-A07 | Passed, synthetic | disposable, mock | Real `anon` and `authenticated` roles, real Auth tokens and real `storage-api`, not a persistent target |
| DH-A08 | Passed | mock, mock | Both approved wire IDs through the real adapter over a fake transport. Unapproved model, fallback array and missing key refused. Guards on name lookups and Python's connects catch a stray dispatch, with controls |
| DH-A09 | Passed, disposable | disposable, mock | Crash, duplicate and lease expiry are fenced, and the real worker's checks run with short leases |
| DH-A10 | Passed | disposable, none | Loopback only, labeled, digest-pinned. Other Docker resources unchanged, in every qualifier's before and after |
| DH-A11 | Passed | mock and disposable | An untracked input makes a report stale. A skipped test fails |
| DH-A12 | Passed | this report | Configuration, deterministic tests and event delivery are separate here. Nothing is marked activated, and no fixture is reported as event delivery |
| DH-A13 | This record | n/a | `scripts/evidence.py complete US-12.3` passing is the check. It shows consistency, not correctness |
| DH-A14 | Passed | mock | Rejects templates, a missing reviewer or runbook, changed fingerprints, inconsistent status, open blocking findings and results citing no run |
| DH-A15 | Passed | mock | The verifier assigns class and transport, and steps with a scripted model say `mock`. `live` with a fake transport, and any manual `live`, are refused |
| DH-A16 | Passed | disposable | Runbook exercised: a stale lock exits 2 and recovers, and a killed run left 1 container and 1 volume, which `cleanup` removed. Arranged adapters read `inactive`, and the real client reads `configured_unqualified`, `delivery_unverified`, CLI 2.1.314 |

## Results on these inputs

Bound to one source fingerprint, in the manifest. A reviewer can't compute a hash, so I bound it to the tree round 3 read, and compared the two. `fast` also exited 0 under `env -i`, kept in the retained output and not in the manifest.

| Check | Class, model transport | Result |
|---|---|---|
| `harness` | static and mock, none | exit 0, 284 harness tests |
| `full` | static, mock and disposable | exit 0, 24 checks, including 548 Python tests and 32 browser tests from `qualify_web.py` |
| `db` | disposable, mock | exit 0: `disposable_db` 44 cases, `supabase_stack` 18, `app_db` 449, `qualify_identity` 437, `qualify_persistent_apply` 29 |
| `operations` | disposable, scripted model | exit 0: operations 69 cases, backup 50, upgrade 45 |
| `qualify_worker_inference.py` | disposable, mock | exit 0, 50 of 50 cases. In no profile, so run here by hand |
| Visual, [US-11.11](../US-11.11/summary.md) and [US-12.2](../US-12.2/summary.md) | real browser, disposable, scripted | 42 captures, no findings, measured again on this tree |

## Mark on the hooks

Hooks fired throughout this delivery. That's an observation, not qualification. A hook is a guardrail here, and nothing shows what Claude does when one crashes or times out, or how Stop recursion behaves. Script fixtures aren't reported as actual event delivery.

## Dispositions

Reports: [round 1](review-r1.md), [round 2](review-r2.md), [round 3](review-r3.md). Each was a fresh read-only context, and none ran anything.

| Finding | Outcome |
|---|---|
| F-1 to F-5, blocking | Fixed, as round 1's record sets out, and each has a test |
| F2-1 to F2-3, blocking | Fixed. A disclosure that follows the server's rule and says the true way out, and guards with a control for each way out |
| F-6 to F-20 | Fixed, including the corrections to US-12.1's and US-12.2's records, appended to each |
| F2-4 to F2-9 | Fixed. A lone surrogate from a model was run, and the run ends `failed` with nothing reserved after it |
| F3-1 | Accepted: one half of a test doesn't reliably hold its fix. The product is right by reading |
| F3-2 | Accepted, and stated: a literal-address stray after the first read isn't caught, and a Unix socket isn't recorded. No code here opens either |
| F3-3 | Accepted: when both name DeepSeek, the page names the Expert's way out first, and the next page names the other |
| F3-4 | Accepted: a workflow with no agent step can show the frozen model. The line below it says data goes only if an agent step runs |
| F3-5 | Accepted: a stale docstring, which the record here corrects |

Editing any of the last five would void this binding, so they stay as they are.

## Failures, errors, skips and limitations

- **Failures on the way, each resolved:**
  - Two `identity` runs failed on a build error, from a type I'd got wrong, and one on a label matching two elements.
  - The walk's first control couldn't break the page the way it claimed, so it was rewritten. Its first clean read raced the page loading, and now waits for it.
  - The stronger walk flagged the Settings radio group, which is how the platform treats one, so my check was corrected.
  - The worker qualifier's existing guard case had to learn to leave out the arranged control.
- **Not exercised:**
  - Any live model call here. US-12.4 and US-12.6 are the live runs on this code.
  - A real sleep on this code, which is US-12.5.
  - Two workers at once, a lost lease and the network pause through the inference worker. US-12.4 is the first run of two workers.
- **Limits:**
  - **The real install is stopped at migration 32,** until US-12.6.
  - **What a test couldn't settle** is listed by row in [US-12.2's summary](../US-12.2/summary.md#what-stays-a-limit).
  - **Reservation size is a byte count,** an upper bound on tokens, and a request that could reach a higher tier is refused on that count, which can come before the rate would apply.
  - **A summary cut at 512 output tokens stops the run** as `compaction_failed`.
  - **A page reload loses Continue in a new run's kept key,** so a press after one can start a second paid run.
  - **No test covers** `goal`'s `run_not_finished` path, its stop-before-read order, or a discount that keeps failing while the lease survives.
- **Spending:** none in this story. The shared ledger stands at US$0.008174 of the US$1 cap.
- **Skips:** none. A skipped test fails the profile.

## Reproduction

```sh
python3.12 scripts/verify.py --profile harness
python3.12 scripts/verify.py --profile fast
python3.12 scripts/verify.py --profile full
python3.12 scripts/verify.py --profile db
python3.12 scripts/verify.py --profile operations
python3.12 scripts/qualify_worker_inference.py
python3.12 scripts/evidence.py validate US-12.3
```

`.checks/US-12.3/gate-0/` keeps the recovery and arranged-fault procedures, hashed in the manifest, with their output beside them. It's ignored and local, so the results above stand without it.
