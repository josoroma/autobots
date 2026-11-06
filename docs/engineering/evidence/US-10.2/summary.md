# US-10.2: release record

**Verdict: not release-ready.** Each requirement is checked against its own acceptance text, as it stands after Decision 0009's revisions. [What stops a release](#what-stops-a-release-now) needs the owner, and US-10.2 stays `IN PROGRESS`.

- **H1: not claimed.** H1.1 and H1.2 have evidence, at disposable level. H1.3's review, runbook and DH-A01 to DH-A16 have evidence at [US-11.12's bound fingerprint](../US-11.12/summary.md), with DH-A03 partial as Decision 0012 allows. But H1.3 also asks that "DH-W01–06 records are complete". US-1.3 to US-1.7 have archived OpenSpec changes only, under Decision 0003, which says it leaves H1 claims unaffected, and US-1.8's approval is void. No decision relaxes that clause for H1, so it's decision 1 below.
- **H0: supported, not separately assessed.** DH-A01 to DH-A16 and the US-1.x records support it, and a disposable copy bootstrapped from the toolchain script. `tests/toolchain`'s reproducibility tests, apart from the scope test, are in no profile.
- **Product acceptance: not established.**

The first version of this record overclaimed, as [`review.md`](review.md) sets out. Its second version did too, in a way its [independent read](review-r2.md) caught. This is the third, corrected for those findings and not read again.

## Revisions

| Source | Class | Revision |
|---|---|---|
| [US-11.12's Gate 0](../US-11.12/summary.md): `harness`, `full` 24 checks, `db` 9, `operations` 7, each exit 0 under `env -i` on 2026-11-06, in [its manifest](../US-11.12/gate-0.json). `fast` also exit 0, in its retained output only | Mixed, as each row says | Committed as `5135601`. Source fingerprint `3ea96bac…`. The reviewers can't compute hashes, so the coordinator bound it to the tree the last round read |
| [US-11.12](../US-11.12/summary.md)'s `qualify_worker_inference.py`, 45 cases | Disposable, mock | The same fingerprint |
| [US-11.11](../US-11.11/summary.md)'s 42 captures | Browser, on a disposable stack | Measured again on that tree. `revision.json` binds a base commit and a hash of the screens, so the link to the fingerprint rests on the author's statement |
| US-11.3's real install | Live, install | Run before its delivery commit `ff7407f`. **The install is stopped, at migration 32 of 35** |
| US-11.2's reasoning trial | Live, direct | Run before its delivery commit `a3ad745`, with only a line wrap changed after |
| US-11.10's two real sleeps | Real sleep, disposable stack, scripted model | Run before its delivery commit `b4f5394`. **`_keep_lease` changed in US-11.12** |
| [US-3.4](../US-3.4/summary.md) protocol corpus | Live, direct | `c7034f1` with the `--only` runs, `60b5b5c` with its fixtures, and a scratch worktree at `415eaf0` for the 2,048-token trial |
| [LIVE-GOAL-1](../LIVE-GOAL-1/summary.md), DeepSeek's goals | Live, product | `2e71720` and later. Its goals failed |
| [LIVE-GOAL-1](../LIVE-GOAL-1/summary.md), Terra's goals | Live, product | A scratch worktree at `e83bfd9` with a 2,048-token limit that isn't in this repository, for run 4 and its missing-artifact observation. Then `ecb3490` and `d4c1c22`, where most succeeded |
| [US-7.2](../../../../openspec/changes/archive/2026-11-06-us-7-2-select-qualify-first-consequential/verification.md) against GitHub | Live, direct | `f1bcedc` with that story's fix, by this record's first assessment. Its verification names no revision |
| [US-10.1](../US-10.1/summary.md) corpus and second run | Live, product | `f563b7b` plus uncommitted work, and `a8a4c4d` plus that story's runner changes |

Raw reports are in `.checks/`, ignored and local. No live result ran on the final code: the bound fingerprint has no live run behind it. US-11.12's fixes changed admission, reservation and the lease keeper since the live runs above.

## How to read a row

| Class | Meaning |
|---|---|
| **Live, product** | Real OpenRouter through the product's API and worker, on a disposable stack |
| **Live, install** | The real persistent install on this Mac, with real OpenRouter calls for its one goal |
| **Live, direct** | Real OpenRouter or GitHub through a runner, with no worker, ledger or approval around it |
| **Real sleep** | This Mac really asleep, on a disposable stack with a scripted model |
| **Disposable** | Real local services on a disposable target, with a scripted or fake model |
| **Browser** | The real web app in Chromium, with no service stack unless the row or its story says it ran on a disposable one |
| **Review** | An independent reader, who executes nothing |
| **Report** | What a validated record itself shows, which is consistency, not correctness |
| **Fixture** | Unit or static checks, with no real service |
| **Partial** | Part of the acceptance text wasn't observed. The row says which part |
| **Partial, accepted** | The same, and the owner has accepted it in a decision |
| **Not met** | The acceptance text is contradicted by what exists |
| **Replaced** | A decision by the owner put something else in its place for routine delivery |

Story records are at `openspec/changes/archive/*-<story>-*/verification.md`, and each states what it didn't exercise. Most were written by the session that built the story, under Decision 0003. Unless a row says **Live, install**, it comes from a disposable stack.

## LC: product requirements

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| LC-01 | Disposable, Live product | US-2.6, US-11.6, US-11.9, US-10.1, US-11.3 | Revised by Decision 0009: one route per run. 14 bindings resolve and freeze, and only `executor` dispatches, which the screen says. No call in a live run reached compaction |
| LC-02 | Disposable | US-5.1 | |
| LC-03 | **Partial** | US-4.3, US-8.1, US-11.12 | Compaction now ran through the real SDK on a fake transport, and still never live. A person inspecting criteria after a real compaction wasn't observed |
| LC-04 | **Partial** | US-4.3, US-5.2, US-11.12 | A child's money and time limits now have cases. Partial results across descendants aren't asserted |
| LC-05 | Disposable | US-4.4, US-5.2 | No MCP adapter exists, so MCP is only refused by name |
| LC-06 | Disposable | US-4.3 | |
| LC-07 | **Partial** | US-5.2, US-11.12 | Limits are enforced, and a child ran through the product worker. "Visible" isn't: no browser test covers the Assignments card |
| LC-08 | Live product, Browser | US-4.2, US-4.8, US-10.1, US-11.4 | US-10.1 ran 9 kills during real paid calls, each reconciled at the worst case by its runner, with no charge looked up. The screen's reconciliation ran on an arranged kill with a scripted worker |
| LC-09 | **Partial, accepted** | US-5.4, US-7.2, US-11.12, Decision 0007 | Disposable, and live direct for readback. A real lost acknowledgment wasn't arranged. A call that fails after GitHub accepted it, whose issue isn't yet visible, could be created twice, which Decision 0007 states. A ruling on a changed attempt is now refused |
| LC-10 | **Partial** | US-5.3, US-11.7 | Tampering and replay hold on a disposable stack. PRD 9.2's requester, scope snapshot and policy version aren't stored on a request: decision 7 |
| LC-11 | Disposable, Browser | US-4.7, US-11.4 | How fast a running call stops isn't measured. A worker's drain can still send paid calls for up to 30 seconds |
| LC-12 | Disposable, Live product and install | US-4.8, LIVE-GOAL-1 run 4, US-11.3 | US-11.3's goal passed product verification with a required artifact. A failing content check never ran live. A goal with no stated requirement succeeds once anything is published |
| LC-13 | **Partial** | US-4.6, US-11.12 | Status and event order rebuild across a disconnect on a queued run, and a malformed reply no longer reads as live. Plan, approval and artifact reconstruction across one isn't observed, and neither is a cut TCP connection |
| LC-14 | Disposable | US-6.2 | The agent step has no iteration-specific test |
| LC-15 | **Partial** | US-7.1, US-11.8 | A missed occurrence shows on Operations, arranged. Times are injected, so real host downtime wasn't observed. Routine screens are later scope, by Decision 0009 |
| LC-16 | Disposable | US-8.1, US-8.2 | Revised by Decision 0009: one workspace can't read another's memory. Separation between users in a workspace is later scope |
| LC-17 | Disposable, Browser | US-3.2, US-3.4, US-11.1 | Revised by Decision 0009. Settings shows each route's stored date, configuration and limits, and a route with no record reads not qualified. `test_no_application_code_asks_for_strict_output` is the enforcing test, a pattern over three strict-output call forms in the source, so it covers that feature and not every unqualified one |
| LC-18 | Disposable, Live product and install for a key-string scan | US-3.1, US-7.2, US-9.1, LIVE-GOAL-1, US-10.1, US-11.3 | The live scan covers durable rows and logs, for the OpenRouter key only. Prompts sent and stored objects weren't scanned. Redaction matches patterns |
| LC-19 | Fixture, Live direct for routing | US-2.6, US-3.4 | The upstream provider is `null` in every live report |
| LC-20 | **Partial** | US-3.2, US-11.5, US-11.11 | Home, Settings and the run list stay usable with no key, against a fake upstream. Files with no key weren't exercised |
| LC-21 | Disposable, Live install for setup | US-3.1, US-3.2, US-9.2, US-11.3 | Recovery after real key loss isn't implemented, only a stated procedure |
| LC-22 | Disposable | US-3.1, US-9.2, WORKER-INFERENCE-001 | A real key has not been rotated. That work item is now complete as built, on mock and disposable evidence |
| LC-23 | **Partial: the owner's decision** | US-3.4, US-10.1, US-11.2, US-11.12 | Named choice, selection and SSE ran live. **On Terra, the pinned SDK removes the encrypted reasoning `id`, in 3 of 3 trials that returned metadata**, and continuations still worked. DeepSeek's survived 4 of 4. Terra missed one `tool_required` case in US-10.1. Decision 2 |
| LC-24 | Disposable | US-3.3, US-4.7, WORKER-INFERENCE-001, US-11.12 | Live 401, 402 and rollover weren't arranged |
| LC-25 | **Partial** | US-2.6, US-8.1, US-11.6, US-11.12 | Revised by Decision 0009: a differing summarizer pauses with `route_not_bound`. The text still asks for an instrumented dispatch inventory, and none exists: a static factory check and a fake-transport compaction under `summarizer` stand in. Background learning has no dispatch to inventory |
| LC-26 | **Partial** | US-2.6, US-11.1 | Sampler flags are refused on a fake transport. "No reasoning-off" holds by absence, and `reasoning` has no shape check. Live reports don't record request bodies |
| LC-27 | Disposable, Live install | US-2.1, US-9.1, US-9.3, US-11.3 | |
| LC-28 | Disposable | US-2.3, US-2.5 | Expired tokens are a unit test with script-signed tokens. Realtime is removed, so it's refused by absence |
| LC-29 | Disposable, Live install | US-2.4, US-4.2, US-9.3, US-11.3 | Revised by Decision 0009: the worker and checkpointer pass in `agent_runtime`, and a LangGraph store is later scope |
| LC-30 | Disposable | US-4.5, US-9.1 | A wrapper raised the interruption during publication, with no real process death |
| LC-31 | **Partial** | US-9.2, US-4.7, US-11.3, US-11.10 | Restore ran from the real install, to a disposable copy. A real sleep ran twice: the first failed, which is why wake handling was built, and the second, with it, came through clean. The model was scripted, so a real provider's connection dropped across a sleep is unexercised. **That proof predates US-11.12's change to `_keep_lease`,** which has database cases and no third sleep |
| LC-32 | **Partial, accepted** | US-1.6 to US-1.8, US-11.12 | Gate 0 repeated at the bound fingerprint. DH-A03's Claude part stays partial, by Decision 0012 |
| LC-33 | Review | US-11.12 | Revised by Decision 0009: routine delivery follows Decision 0003, with one independent review of the final code. It took five rounds, and rounds 4 and 5 approved. Stories' own records were mostly written by the session that built them |
| LC-34 | **Partial** | US-2.5, US-11.11 | Axe at WCAG 2.1 AA with 0 violations across 42 captures in both themes, by Decision 0010. It asks for accessible key flows in both modes: keyboard order was walked only on Home, and no screen reader was used |

## MP: model providers

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| MP-A01 | Disposable | US-3.1 | Next.js's full dotenv grammar isn't matched, only a shared subset |
| MP-A02 | Disposable | US-3.2 | Against a fake upstream |
| MP-A03 | Disposable | US-3.1, US-3.2 | Against a fake upstream |
| MP-A04 | Disposable, Fixture | US-3.2, US-2.6, WORKER-INFERENCE-001 | The outage was against a fake upstream. The stale-catalog block through the worker is a unit test |
| MP-A05 | Fixture | US-2.6 | |
| MP-A06 | **Partial** | US-3.4, US-10.1, Decision 0005 | DeepSeek's strict nested schemas fail, which Decision 0005 accepts. It says the rest stay open: DeepSeek's real fragmentation is fake-only, cancellation shows only our side stopping, and DeepSeek has no run at the 130-second timeout. Terra refuses open objects with `400` |
| MP-A07 | **Partial** | US-3.4, US-10.1 | Live, direct. "Unsupported selectors fail honestly" was never exercised, as both routes honored the selector |
| MP-A08 | Disposable, Live direct and product | US-2.6, US-3.4, US-10.1, US-11.6, US-11.9 | Revised by Decision 0009: one route per run. The boundary and defaults hold |
| MP-A09 | Disposable | US-3.3, US-5.2, US-11.12 | Not on a live route. A request that could reach Terra's long-prompt tier, counted in bytes, is refused before sending, which can come before the rate would apply |
| MP-A10 | Disposable | US-3.1, US-9.2, WORKER-INFERENCE-001 | A real key has not been rotated |
| MP-A11 | Disposable | US-3.1, US-3.2 | |
| MP-A12 | **Partial** | US-3.2, US-9.1, US-11.5 | Local files with no key weren't exercised |

## LM: local Mac deployment

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| LM-A01 | Disposable, Live install | US-2.1, US-9.1, US-11.3 | **The install is at migration 32, and stopped** |
| LM-A02 | Disposable, Live install | US-2.1, US-11.3 | Its own loopback ports, as others were held. `finance` and `mentor` were identical before and after. Studio authentication was seen only on a disposable stack, as a redirect with the page not rendered |
| LM-A03 | Disposable, Live install | US-2.1, US-2.6, US-9.1, US-11.3 | |
| LM-A04 | Disposable, Live install | US-9.1, US-9.3, US-11.3 | `compose stop` and `up` kept the owner, run, artifact, checkpoints, events and all five volumes. One real migration was applied, from a restored copy first. A restart of Docker or the Mac wasn't run |
| LM-A05 | Disposable | US-2.3, US-4.5 | |
| LM-A06 | **Partial** | US-3.1, US-3.2, US-10.1, US-11.5 | Local non-AI use with no key covers home, Settings and the run list |
| LM-A07 | **Partial** | US-4.7, US-9.1, US-11.10 | Real sleep observed twice, with a scripted model, and only the second with the fix, before `_keep_lease`'s later change. Network loss wasn't observed |
| LM-A08 | Disposable, Live install | US-9.2, US-11.3 | Backup from the real install, restored to a disposable copy, 14 of 14 checks. Not to another machine |
| LM-A09 | **Partial** | US-2.1, US-2.4, US-10.1 | The resource envelope is one short sequential run. The two-call workload wasn't measured: decision 5 |

## DS: design system

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| DS-01 | Browser | US-2.5, US-11.11 | |
| DS-02 | Browser | US-2.5, US-11.11 | Changing appearance sends no request, and runs, approvals and workflows read the same afterward |
| DS-03 | Browser | US-2.5, US-11.11 | 21 surfaces in both themes, on shared components, which a harness test enforces. Eight named surfaces don't exist in the app, such as charts and a workflow canvas, and [the summary](../US-11.11/summary.md) lists them |
| DS-04 | **Partial** | US-11.11, Decision 0010 | WCAG 2.1 AA measured in both themes: lowest text 4.74:1, boundaries 4.74:1, focus 14.5:1, hover 5.21:1. `--input` and light `--ring` stay below 3:1 alone, corrected by pairing. Not observed: disabled controls, keyboard order beyond Home, and zoom on more than 8 screens or reduced motion on more than 4, neither in both themes. No screen reader |
| DS-05 | **Partial** | US-2.5, US-11.11 | Screenshots retained for all 42 captures, on the final tree. Storage and first paint come from US-2.5. Keyboard and responsive layouts on the named surfaces have DS-04's gaps |

## DH: development harness

From [US-11.12's Gate 0](../US-11.12/summary.md), at its bound fingerprint. US-1.8's approval stays void.

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| DH-A01 | Static | US-11.12, `project_configuration` | |
| DH-A02 | Static and disposable | US-11.12 | Under `env -i`, with no `claude` on `PATH`, and exit 2 with tools missing |
| DH-A03 | **Partial, accepted** | US-1.4, US-1.8, US-11.12, Decision 0012 | Claude's crash, timeout and Stop recursion behavior isn't qualified. Script fixtures aren't reported as event delivery |
| DH-A04 | Mock and disposable | US-11.12, `fault_qualification` | 21 of 21, and a committed fault in a disposable copy |
| DH-A05 | Fixture | US-11.12 | The state fixture has its own table, not linked to the product's machine |
| DH-A06 | Disposable | US-1.7, US-11.3, US-11.12 | |
| DH-A07 | Disposable | US-1.7, US-2.3, US-11.12 | |
| DH-A08 | Mock | US-1.6, US-2.6, US-11.12 | |
| DH-A09 | Disposable | US-1.8, US-4.2, US-11.12 | |
| DH-A10 | Disposable | US-1.7, US-2.1, US-11.12 | |
| DH-A11 | Mock and disposable | US-1.6, US-11.12 | |
| DH-A12 | Report | US-11.12 | |
| DH-A13 | Report | US-11.12 | `scripts/evidence.py complete US-11.12` passes, which shows consistency, not correctness |
| DH-A14 | Mock | US-1.5, US-11.12 | |
| DH-A15 | Mock | US-1.6, US-11.12 | |
| DH-A16 | Disposable | US-11.12 | Stale-lock and killed-run recovery, and arranged adapter states |
| DH-W01–02 | Replaced, for routine delivery | Decision 0003 | An archived OpenSpec change is the record, and US-11.12 keeps a full one. US-1.3 to US-1.7 have no DH-W record, and H1.3's clause isn't relaxed: decision 1 |
| DH-W03 | Review | US-11.12, Decision 0009 | Revised: one independent review of the final code before a release |
| DH-W04–06 | Replaced, for routine delivery | Decision 0003 | Bound fingerprints and evidence directories exist only where a story asked for them, as US-11.12 did. Decision 1 again |

## What stops a release now

**[Decision 0013](../../decisions/0013-release-closure.md) has since decided all of these, and [EPIC-12](../../../../SPECS.md#epic-12-release-closure) delivers what it chose.** This record is assessed again after that.

### For the owner

No source decides these, or they need authority only the owner has.

| # | Decision | Why it's open | Choices |
|---|---|---|---|
| **1** | **H1.3's records clause** | It asks for complete DH-W01–06 records. US-1.3 to US-1.7 have none under Decision 0003, and that decision says it leaves H1 claims unaffected | Accept US-11.12's record as carrying the baseline, and revise H1.3 with its ID kept. Or write the missing records |
| **2** | **LC-23 on Terra** | The pinned SDK removes Terra's encrypted reasoning `id` on continuation, in 3 of 3 trials that returned metadata. Continuations still worked. LC-23 asks for it preserved | Build preservation, or revise LC-23 with its ID kept |
| **3** | **The real install at the final code** | It's stopped at migration 32 of 35, so the code released has never run on it, and no live run has run on the final code. US-11.3's authority ended with that story | Authorize `scripts/persistent_install.py apply` for 33 to 35 and a start, with or without one more goal under the remaining spend (US$0.008174 of US$1 used). Or accept the limit |
| **4** | **DeepSeek, selectable with no task qualification** | PRD 6.4 runs gates per enabled model, and PRD 15 keeps a failing binding unavailable. Decision 0006 keeps DeepSeek selectable, and it has no corpus result and none of its goals succeeded | Disable the route, qualify it (paid), or accept and revise |
| **5** | **The two-call workload** | PRD 13.1 asks for stable operation under it, and SP-021 says meet or explicitly revise. Goals ran one at a time, and Decision 0008 doesn't cover this | Measure it (paid, on a disposable stack), or revise the target |
| **6** | **PRD 12.2's metrics** | It says to record queue wait, time to first token, cancellation delay and others. None exists in the service, and no decision revises this | Build them, or revise or defer by decision |
| **7** | **Review items marked later, with no story and no decision** | A reviewer's suggestion I adopted, not an owner's choice. PRD 9.2's requester, scope snapshot and policy version on an approval (N-22, N-24, N-25). PRD 8.3's empty `inputs` grant (N-7). A rollback's actor and a promoted memory's `created_by` (N-37, N-51, N-52). Routines reading policy and skills at each occurrence (N-48). Held-out replay (N-new-2) | Accept each, or schedule it |
| **8** | **A third real sleep** | US-11.10's proof predates `_keep_lease`'s change, and only the owner can sleep this Mac | Repeat it, or accept the database cases |

### Engineering can close these, with no paid call or persistent change

No story owns them, so each needs scheduling, or accepting as a stated limit:

- **LC-03, LC-04, LC-07, LC-13, LC-15, LC-20, LC-25, LC-26, LC-34, MP-A12, LM-A06.** Examples: a browser test of the Assignments card, partial results across descendants, reconstruction across a disconnect, files with no key, a dispatch inventory.
- **DS-04, DS-05.** Keyboard order, disabled controls, and zoom and reduced motion in both themes.

**Partly the above, and partly live or owner's:** LC-10 (decision 7), LC-31 and LM-A07 (decision 8, and network loss), LM-A09 (decision 5), MP-A06 and MP-A07 (live behavior of the routes, which would be paid).

## Blocking findings

The 11 from the first assessment, as [Decision 0009](../../decisions/0009-release-scope-from-blocking-findings.md) decided them.

| ID | Finding | Now |
|---|---|---|
| **B1** | No persistent install path | **Built and exercised** in US-11.3, on a real install. The final code isn't on it: decision 3 |
| **B2** | Real Mac sleep unobserved, and wake handling not built | **Done** in US-11.10, with two real sleeps. The proof predates a later keeper change: decision 8 |
| **B3** | Required screens incomplete | **Done** in US-11.4 to US-11.9, with the rest revised to later scope |
| **B4** | Independent review | **Done** in US-11.12, with every open minor and major given an outcome |
| **B5** | H1 not established | **Gate 0 repeated** in US-11.12, and Decision 0012 settles the hook limit. H1 isn't claimed: decision 1 |
| **B6** | The UI misreports state | **Done** in US-11.1, with LC-17 revised |
| **B7** | Design partly unimplemented, evidence old | **Done** in US-11.11, and measured again on the final tree |
| **B8** | Only one role runs | **Revised:** one route per run, and US-11.6 and US-11.9 say so on screen |
| **B9** | No run controls on a screen | **Done** in US-11.4 |
| **B10** | Two named mechanisms missing | The store is **revised** to later scope. Reasoning has **its check**, which found the loss: decision 2 |
| **B11** | Memory not scoped to a user | **Revised:** scoped to the workspace in this single-owner release |

## Procedures

| Runbook | Exercised on | Not exercised |
|---|---|---|
| [`development-harness.md`](../../runbooks/development-harness.md) | Real checks and recovery, at US-11.12's fingerprint | Claude's crash and timeout behavior. Forward ingestion was last exercised in US-1.2 |
| [`local-supabase.md`](../../runbooks/local-supabase.md) | The real install, at US-11.3 | Its recovery rows, a pinned-release upgrade |
| [`local-app.md`](../../runbooks/local-app.md) | The real install, at US-11.3 | Studio |
| [`first-slice.md`](../../runbooks/first-slice.md) | A disposable stack, with a scripted model | A person following it |
| [`operations.md`](../../runbooks/operations.md) | The real install at US-11.3, and `qualify_operations.py` at the final fingerprint | A drain cut short, reconciling a real uncertain call, retention, its GitHub section on the install, a run paused for a key or a stale catalog there, real sleep on the install. Its `cost_unavailable` row says tokens where the refusal counts bytes |
| [`backup-restore.md`](../../runbooks/backup-restore.md) | The real install at US-11.3, to a disposable copy, and `qualify_backup.py` at the final fingerprint | Another machine |
| [`upgrade.md`](../../runbooks/upgrade.md) | One real migration on the install at US-11.3, and `qualify_upgrade.py` at the final fingerprint | A real image or framework change, a failed migration on the install, migrations 33 to 35 there |
| [`mac-sleep.md`](../../runbooks/mac-sleep.md) | Two real sleeps, by the owner, at US-11.10 | The changed `_keep_lease` |
| [`toolchains.md`](../../runbooks/toolchains.md) | Bootstrap, in US-11.12's disposable copy | A new machine |
| [`ohmyorch-delivery.md`](../../runbooks/ohmyorch-delivery.md) | This delivery itself | Not a user procedure |

There's no user guide apart from these runbooks. They were followed by the delivery session, not by a person new to them.

## Limits on the release as it stands

- **No live run on the final code,** on the install or anywhere. US-11.12's fixes to admission, reservation and the lease keeper have disposable evidence only.
- **The real install exists, and is stopped at migration 32.**
- **Task quality is unjudged by a person.** String checks scored an assistant-written corpus, at 86.7% with a narrow margin, as [Decision 0008](../../decisions/0008-us-10-1-limits-accepted.md) accepts.
- **One model ran the corpus.** DeepSeek ran the protocol fixtures, and [none of its goals succeeded](../LIVE-GOAL-1/summary.md), through the 512-token limit and through rejected plans: decision 4. Terra's one goal on the install succeeded.
- **Promotion gates on a reviewer's text checks,** by Decision 0011. Real held-out replay has no story yet: decision 7.
- **A rate limit ends a run,** by Decision 0011, and a person starts a linked new one. 
- **Responsiveness:** US-10.1's targets were met on disposable stacks, one client at a time, with cancellation measured on queued runs only. Concurrent load is decision 5.
- **Duplicate protection on GitHub is narrower, not gone.** The wait rests on one measurement of 8.9 seconds.
- **Mocked provider behavior isn't live qualification.** Credential failures, catalog outages, lost acknowledgments, and compaction and children through the worker used fakes.
- **Review's open nonblocking items** are in [US-11.12's dispositions](../US-11.12/summary.md#dispositions), including that a page reload loses **Continue in a new run**'s kept key.

