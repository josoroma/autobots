# US-11.12 evidence summary: final review and Gate 0

The final review of EPIC-11 and the repeated Gate 0, on top of `5012235`, 2026-11-06. Manifest: [gate-0.json](gate-0.json). Raw reports are in ignored `.checks`, and the results here stand without them.

**Result:** every portable gate below has passing evidence at its stated level, and DH-A03 stays partial by Decision 0012. **Nothing here is live, no real model call was made, and the real install wasn't touched.** This leaves H1 and product acceptance to US-10.2's assessment, and establishes neither.

## Gate 0 by DH-A gate

| Gate | State | Class, model transport | Observed |
|---|---|---|---|
| DH-A01 | Passed | static, none | `project_configuration` passes: configuration, documents, rules and hook settings |
| DH-A02 | Passed | static and disposable, none | `harness`, `fast`, `full`, `db` and `operations` exit 0 under `env -i PATH HOME`, and those are the reports the manifest binds. With no `claude` on `PATH`, `harness` exits 0. With `PATH=/usr/bin:/bin`, `full` exits 2, status error |
| DH-A03 | **Partial, by [Decision 0012](../../decisions/0012-unqualified-hooks-in-h1.md)** | mock, none | Script fixtures pass for malformed input, metacharacters, symlinks, timeout and a missing library. Hooks are on as guardrails, configured and not qualified. **Claude's own crash, timeout and Stop recursion behavior is not qualified** |
| DH-A04 | Passed | mock and disposable | 21 of 21 fault cases as expected. A committed type fault: `fast` exit 1 on `mypy` alone, with 0 changed paths. Corrected: exit 0. Versions are in the manifest. The contract fault now runs the real checker on a tree that has drifted |
| DH-A05 | Passed, fixture level | mock, mock | Invalid transitions, a wrong reducer and a private key in a public event are detected. The fixture has its own transition table and isn't linked to the product's machine |
| DH-A06 | Passed, synthetic | disposable, mock | Fresh replay, repeated apply, rollback, upgrade with data, two seed runs. The persistent apply refuses its unsafe cases, on a disposable stack |
| DH-A07 | Passed, synthetic | disposable, mock | Real `anon` and `authenticated` roles, real Auth tokens and real `storage-api`, not a persistent target |
| DH-A08 | Passed | mock, mock | Both approved wire IDs through the real adapter over a fake transport. Unapproved model, fallback array and missing key refused |
| DH-A09 | Passed, disposable | disposable, mock | Crash, duplicate and lease expiry are fenced in the stub, and the real worker's checks run with short leases |
| DH-A10 | Passed | disposable, none | Loopback only, labeled, digest-pinned. Other Docker resources unchanged, in every qualifier's before and after |
| DH-A11 | Passed | mock and disposable | An untracked input makes a report stale. `docs/design` and `tests/qualification` are now inputs, and the persistent path is now a database change. A skipped test fails |
| DH-A12 | Passed | this report | Configuration, deterministic tests and event delivery are separate here. Nothing is marked activated, and no fixture is reported as event delivery |
| DH-A13 | This record | n/a | `scripts/evidence.py complete US-11.12` passing is the check. It shows consistency, not correctness |
| DH-A14 | Passed | mock | Rejects templates, a missing reviewer or runbook, changed fingerprints, inconsistent status, open blocking findings and results citing no run |
| DH-A15 | Passed | mock | The verifier assigns class and transport, and steps with a scripted model now say `mock`. `live` with a fake transport, and any manual `live`, are refused |
| DH-A16 | Passed | disposable | Runbook exercised on these inputs: a stale lock exits 2 and recovers, and a killed run left 1 container and 1 volume, which `cleanup` removed. Arranged adapters read `inactive`, and the real client reads `configured_unqualified`, `delivery_unverified`, CLI 2.1.314 |

## Results on these inputs

Bound to one source fingerprint, in the manifest. A reviewer can't compute a hash, so I bound it to the tree round 5 read. `fast` also exited 0 under `env -i`, kept in the retained output and not in the manifest.

| Check | Class, model transport | Result |
|---|---|---|
| `harness` | static and mock, none | exit 0, 280 harness tests |
| `full` | static, mock and disposable | exit 0, 24 checks, including 546 Python tests and 32 browser tests from `qualify_web.py` |
| `db` | disposable, mock | exit 0: `disposable_db` 44 cases, `supabase_stack` 18, `app_db` 449, `qualify_identity` 407 with 19 of 23 browser spec files, `qualify_persistent_apply` 29 |
| `operations` | disposable, scripted model | exit 0: operations 69 cases, backup 50, upgrade 45 |
| `qualify_worker_inference.py` | disposable, mock | exit 0, 45 of 45 cases. In no profile, so run here by hand |
| Visual, [US-11.11](../US-11.11/summary.md) | real browser, disposable, scripted | 42 captures, no findings, measured again on this tree |

## Mark on the hooks

Hooks fired throughout this delivery. That's an observation, not qualification. A hook is a guardrail here, and nothing shows what Claude does when one crashes or times out, or how Stop recursion behaves.

One real interaction was found: the delivery plugin's Stop hook rewrites `openspec/delivery/goal.md`, and that failed `full`'s non-mutation guard during a run. The guard now leaves that one record out.

## Dispositions

Round 1's reports, kept verbatim: [code](review-r1-code.md), [open findings](review-r1-open-findings.md), [Gate 0](review-r1-gate-0.md). Later rounds, in substance: [2](review-r2.md), [3](review-r3.md), [4](review-r4.md), [5](review-r5.md).

### What earlier reviews left open

| Item | Outcome |
|---|---|
| **M8** | Accepted by [Decision 0011](../../decisions/0011-review-dispositions.md). The review found it half built, as a member's session could still pin a version (N-new-1). Fixed: a non-owner naming a version gets `403 owner_required` |
| **M30** | Accepted by [Decision 0009](../../decisions/0009-release-scope-from-blocking-findings.md): a differing summarizer pauses with `route_not_bound`, and separate routes stay later scope under LC-01 and LC-25 |
| **M32** | Accepted by Decision 0011: `to_version` 0 means no active version |
| **M33** | Accepted by Decision 0011. The owner first accepted it on my statement that held-out replay stayed with US-10.1, which was false (N-new-2). Told so, the owner kept the gate, with replay as later scope and no story yet |
| **WORKER-INFERENCE-001** | Complete as built, on mock and disposable evidence only. See [its record](../../work-items/WORKER-INFERENCE-001.md). `rate_limited` and `provider_error` fail a run by Decision 0011, and **Continue in a new run** now exists on screen (N-new-3) |

### The 41 minors, itemized as N-1 to N-73

| Outcome | Findings |
|---|---|
| **Fixed, with the reviewer's blocking ones marked \*** | N-2\*, N-4, N-8\*, N-9\*, N-11, N-12, N-13, N-14, N-15, N-18, N-41\*, N-43, N-44, N-53, N-55, N-56, N-62, N-64, N-65, N-66, N-69, N-71\* |
| **Partly fixed** | N-70: after a stop the worker claims nothing new. A step already running can send further paid calls during the drain, and the runbook says so |
| **Already fixed before this review** | N-3, N-16, N-23, N-29, N-31, N-57, N-68 |
| **No longer applies** | N-36: not reachable through the product path |
| **Suggested for later, under the audit requirements, with no story and no owner's decision** | N-22, N-24, N-25, N-37, N-51, N-52. [US-10.2](../US-10.2/summary.md#what-stops-a-release-now) puts them to the owner |
| **Suggested for later, under PRD 8.3's context passing, with no story and no owner's decision** | N-7. The same |
| **Accepted, the state stays consistent or it fails closed** | N-1, N-5, N-6, N-10, N-17, N-19, N-20, N-21, N-30, N-32, N-34, N-35, N-49, N-50, N-63 |
| **Accepted, no harm found or a person decides** | N-26, N-27, N-28, N-33, N-38, N-39, N-40, N-42, N-45, N-46, N-47, N-54, N-58, N-59, N-60, N-61, N-67, N-72, N-73 |
| **Accepted, and reported to the owner since no decision covers it** | N-48: a routine reads model policy and skill text at each occurrence, and each occurrence freezes them at its own admission |

### Found by this review

| Finding | Outcome |
|---|---|
| E-1 to E-16, E-18, E-19 | Fixed |
| E-17 | Partly fixed. The inspector now says which lists include child runs, and the budget text says the workspace's limits apply too. Accepted: evidence links still match an artifact by name, as artifacts have no path, the effective limit isn't shown as one number, and tool attempts stay per run |
| G-1 to G-9, G-11 to G-14, G-16, G-17 | Fixed |
| G-10 | Resolved by [Decision 0012](../../decisions/0012-unqualified-hooks-in-h1.md) |
| G-15 | Accepted: the state fixture stays a fixture, so DH-A05 is fixture-level only |
| WI-1, WI-2, WI-3, WI-5 | Fixed. WI-5 added compaction and a child through the real SDK. Two workers, a lost lease and the network pause stay unexercised through this worker. A summary cut at 512 output tokens stops the run as `compaction_failed` |
| WI-4, WI-6, WI-7 | Accepted: read-only, or they fail closed and say what they don't know |
| N-new-1, N-new-3, N-new-4, N-new-6, N-new-8 | Fixed |
| N-new-2 | Corrected in Decision 0011. Held-out replay needs a new story, for the owner to plan |
| N-new-5, N-new-7 | Accepted |
| N-new-9 | Accepted: `qualify_worker_inference.py` stays out of the profiles because it's Docker-heavy, and was rerun by hand here |

### Found by the later rounds

| Finding | Outcome |
|---|---|
| R2-1, R2-2, R2-3, blocking | Fixed. A summary reserves from the same rate as other work, **Continue in a new run** repeats the stored goal whole, and a reconciled charge records who supplied it |
| R3-1, R3-2, blocking | Fixed. A row with no recorded source claims neither, and a request that could reach a higher long-prompt tier, such as Terra's at 272,000 tokens, is refused before sending |
| R2-4, R2-6 to R2-15 | Fixed, each as the next round read it |
| R2-5 | Recorded: the runbook now states that a running step can send further paid calls during the drain |
| R3-3 to R3-5, R3-7 to R3-14 | Fixed, apart from the test gaps under Limits |
| R3-6 | Accepted, and stated in `discount_sleep`: a connection lost just after a discount commits applies it twice, which at worst leaves that segment's active time uncounted. The money limits don't depend on it |
| R4-1 to R4-7 | Fixed, with the remainders below |
| R4-8 | Accepted as a narrow guard. See R5-7 |
| R5-1 | Accepted: a browser test's name says "linked" where it asserts the request. The stored link is proved in `tests/db/review_check.py` |
| R5-2 | **Accepted, and it corrects the runbook here.** The `cost_unavailable` row says "from 272,000 tokens", but the refusal counts bytes, one token each, so it can fire before the rate would apply. Its remedy isn't available for a child or workflow run, which can only be cancelled |
| R5-3 | Accepted: `calls_without_a_reported_charge` can read an unread count as 0, and `not_checked` misses a blank value. The shared ledger stays safe, as it depends on the spend read, not these |
| R5-4 | Accepted: a lone surrogate could raise before any reservation. Not shown to be reachable, and no money is at risk |
| R5-5 | Accepted: "may already be running" stays on screen after the outcome is known |
| R5-6 | Accepted: no test asserts the picker is hidden after a lost reply, or that a refusal clears the key |
| R5-7 | Stated here: the Bash guard stops common reads of a relative `master.key` or `backup.key`. `grep . master.key` and piped forms get through. Anything under the install's own folder is denied by path. A hook is a guardrail, not confinement |

## Review

| Round | Reviewer | Reviewed | Outcome |
|---|---|---|---|
| 1 | Three `autobots-reviewer` contexts, read-only | The code, the open findings and Gate 0 | `changes_required` from all three |
| 2 | Fresh `autobots-reviewer` context | Everything since round 1's base | `changes_required`: 3 blocking, 12 nonblocking |
| 3 | Fresh context | The edits for round 2, and the source around them | `changes_required`: 2 blocking, 12 nonblocking |
| 4 | Fresh context | The edits for round 3 | `approved`: 8 nonblocking |
| 5 | Fresh context | The edits for round 4, on the bound tree | `approved`: 7 nonblocking |

The reviewers can't compute hashes, so the coordinator bound the fingerprint to the final inputs they read. They ran nothing.

## Failures, errors, skips and limitations

- **Failures on the way, each resolved:**
  - `fast` failed on a test calling `check_domains` with a list, and on rule globs with no representative path. Both fixed.
  - `full` failed once on `non_mutation_guard`, because the delivery plugin's Stop hook rewrote `openspec/delivery/goal.md` during the run. The guard now leaves that record out.
  - The first run of the new database cases failed, as round 3 had predicted by reading: a wrong column, a grant the runtime role lacks, and a run limit below the reservation. Three cases then showed my expectations were wrong, and the product right: a child past the money pauses for more budget and doesn't fail, a workflow step has no instance when its run pauses, and an expired parent lease was claimed ahead of the arranged run. The cases now assert what happens, and drive the exact run.
  - The first committed-fault run failed before any fault was arranged, as its copy left out `research/`, which tests read. The procedure was fixed and rerun alone, as it's a disposable copy with its own reports. Those are the results here.
- **Not exercised:**
  - Any live model call here. Live evidence is in the verification records of US-11.2, US-11.3 and US-11.10, and in [US-3.4](../US-3.4/summary.md), [LIVE-GOAL-1](../LIVE-GOAL-1/summary.md) and [US-10.1](../US-10.1/summary.md).
  - A second real Mac sleep after `_keep_lease` changed. US-11.10's real sleep ran before the reconnection and the fenced discount were added, and they have database cases only.
  - Two workers at once, a lost lease and the network pause through the inference worker.
- **Limits:**
  - **The real install is stopped at migration 32.** Migrations 33, 34 and 35 need the owner's authorization for `scripts/persistent_install.py apply`. Until then, Operations would read `schema_behind` once started.
  - **LC-23 stays partial on Terra.** The pinned SDK removes Terra's encrypted reasoning `id`, in 3 of 3 trials that returned metadata, and no source decides whether to build it or revise LC-23. The owner hasn't chosen.
  - **N-70 and E-17 are partly fixed,** as stated above.
  - **A page reload loses the kept key.** After a lost reply, **Continue in a new run** keeps its key in memory only, so a press after a reload can start a second paid run, under its own limits.
  - **No test covers** `goal`'s `run_not_finished` path or its stop-before-read order, a discount that keeps failing while the lease survives, the failure-path report, or the inspector's `unattributed` text. Their behavior here comes from reading. `goal`'s call to `refuse_other_work` and two wiring points are held by text-only tests, which say so.
  - **Reservation size is a byte count,** which is an upper bound on tokens for the request, not a tokenizer's figure.
  - **A summary cut at 512 output tokens stops the run** as `compaction_failed`. Nothing shows how often a real model would reach that.
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
python3.12 scripts/evidence.py validate US-11.12
```

`.checks/US-11.12/gate-0/` keeps the recovery and arranged-fault procedures, hashed in the manifest, with their output beside them. It's ignored and local, so the results above stand without it.
