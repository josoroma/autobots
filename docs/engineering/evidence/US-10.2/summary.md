# US-10.2: release record

**Verdict: every mandatory item has evidence or a decision, except six that are the owner's, [below](#what-needs-the-owner).** Each requirement is checked against its own acceptance text, as it stands after Decisions 0009 and 0013. US-10.2 stays `IN PROGRESS` until those are answered.

- **H1: met today, with its stated limits, at [US-12.3's binding](../US-12.3/summary.md), and answering the owner's items will void that binding.** H1.1 and H1.2 have evidence at disposable level. H1.3's review, runbook and DH-A01 to DH-A16 have evidence at that fingerprint. DH-A03 stays partial, by Decision 0012, so Claude's own crash, timeout and Stop recursion behavior isn't qualified.
  - **Records:** US-12.3's record carries the baseline for US-1.3 to US-1.7, as H1.3 allows by Decision 0013. Decision 0003's clause is met by US-1.5 and US-1.8 being `DONE`, with US-12.3 in place of US-1.8's void approval. US-1.1 and US-1.2 predate Decision 0003, and `validate US-1.2` fails on the older schema, as US-1.5 records. US-12.3's review covers what changed since US-11.12, which reviewed the whole, so the two read as a chain.
  - **What voids it:** decisions and PRDs are inputs to the fingerprint, so recording any answer as a decision voids the binding, as Decision 0013 voided US-11.12's. So the answers go in together and the binding is made once more, with a review of what changed and a new Gate 0. The live runs would then sit on an earlier fingerprint, which would differ only by those texts.
- **H0: supported, not separately assessed.** DH-A01 to DH-A16 and the US-1.x records support it, and a disposable copy bootstrapped from the toolchain script. `tests/toolchain`'s reproducibility tests, apart from the scope test, are in no profile.
- **Product acceptance: not established.** It waits on the six items below, and accepting them is the owner's call.

Earlier versions of this record overclaimed, as [`review.md`](review.md) and [`review-r2.md`](review-r2.md) set out. This version's first draft did too, as [`review-r3.md`](review-r3.md) sets out, and the correction hasn't been read again.

## Revisions

| Source | Class | Revision |
|---|---|---|
| [US-12.3's Gate 0](../US-12.3/summary.md): `harness`, `full` 24 checks, `db` 9, `operations` 7, each exit 0 under `env -i` on 2026-11-06, in [its manifest](../US-12.3/gate-0.json). `fast` also exit 0, in its retained output only | Mixed, as each row says | Source fingerprint `05916d5e…`, committed in `70c5162`. The reviewers can't compute hashes, so the coordinator bound it to the tree the last round read |
| `qualify_worker_inference.py`, 50 cases | Disposable, mock | The same fingerprint |
| [US-11.11](../US-11.11/summary.md)'s 42 captures, and [US-12.2](../US-12.2/summary.md)'s walk | Browser, on a disposable stack | Measured again on that tree. Their records bind a base commit and a hash of the screens, so the link to the fingerprint rests on the author's statement |
| [US-12.6](../US-12.6/summary.md)'s real install and one goal | Live, install | The same fingerprint, by the author's statement and the timeline, as its report holds no hash. **The install is stopped, at migration 35 of 35** |
| [US-12.5](../US-12.5/summary.md)'s third real sleep | Real sleep, disposable stack, scripted model | The same fingerprint, by the author's statement and the timeline, as its report holds no hash |
| [US-12.4](../US-12.4/summary.md)'s two-call workload | Live, product | Round 5 at the same fingerprint. Rounds 1 to 4 at the binding before it, which differs by the sleep fix. Rounds 2 to 5 ran a logging wrapper kept with that evidence. Only round 1, the one that paused, ran the product's own entry point |
| [This record's closing checks](closing-checks.json): cancelling a running run, a cut stream, the secret scan | Disposable, scripted model | The same fingerprint, recorded in the report by `evidence.py`. Its runner is kept beside it, as a file under `scripts/` would void the binding |
| US-11.3's earlier install exercise | Live, install | Run before its delivery commit `ff7407f` |
| US-11.2's reasoning trial | Live, direct | Run before its delivery commit `a3ad745`, with only a line wrap changed after |
| [US-3.4](../US-3.4/summary.md) protocol corpus | Live, direct | `c7034f1` with the `--only` runs, `60b5b5c` with its fixtures, and a scratch worktree at `415eaf0` for the 2,048-token trial |
| [LIVE-GOAL-1](../LIVE-GOAL-1/summary.md), DeepSeek's goals | Live, product | `2e71720` and later. Its goals failed |
| [LIVE-GOAL-1](../LIVE-GOAL-1/summary.md), Terra's goals | Live, product | A scratch worktree at `e83bfd9` with a 2,048-token limit that isn't in this repository, for run 4 and its missing-artifact observation. Then `ecb3490` and `d4c1c22`, where most succeeded |
| [US-7.2](../../../../openspec/changes/archive/2026-11-06-us-7-2-select-qualify-first-consequential/verification.md) against GitHub | Live, direct | `f1bcedc` with that story's fix, by this record's first assessment. Its verification names no revision |
| [US-10.1](../US-10.1/summary.md) corpus and second run | Live, product | `f563b7b` plus uncommitted work, and `a8a4c4d` plus that story's runner changes |

Raw reports are in `.checks/`, ignored and local. The live runs on the bound code are US-12.4's round 5 and US-12.6's goal, and only the goal ran the product's own entry point. US-3.4, US-7.2, US-10.1 and LIVE-GOAL-1 predate many later changes, including to admission and reservation, and weren't repeated.

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
| **Mock** | A fake provider or arranged reply, with the code around it real |
| **Static** | Reading configuration or text, with nothing run |
| **Partial** | Part of the acceptance text wasn't observed. The row says which part |
| **Partial, accepted** | The same, and the owner has accepted it in a decision |
| **Partial: the owner's** | The same, and no decision has settled it yet |
| **Not met** | The acceptance text is contradicted by what exists |
| **Replaced** | A decision by the owner put something else in its place for routine delivery |

Story records are at `openspec/changes/archive/*-<story>-*/verification.md`, and each states what it didn't exercise. US-12.3's and US-12.4's predate later rounds, so their summaries are the current account. Most were written by the session that built the story, under Decision 0003. Unless a row says **Live, install**, it comes from a disposable stack.

## LC: product requirements

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| LC-01 | Disposable, Live product | US-2.6, US-11.6, US-11.9, US-10.1, US-11.3 | Revised by Decision 0009: one route per run. 14 bindings resolve and freeze, and only `executor` dispatches, which the screen says. No call in a live run reached compaction |
| LC-02 | Disposable | US-5.1 | |
| LC-03 | **Partial, accepted** | US-4.3, US-8.1, US-11.12, US-12.2 | The goal and criteria read the same on screen after a scripted compaction, and through the API after one on the real SDK with a fake transport. A live compaction wasn't reached. Decision 0013 leaves what a test can't settle as a limit |
| LC-04 | Disposable | US-4.3, US-5.2, US-11.12, US-12.2, US-12.3 | A child's money and time limits have cases. A limit across the tree stops at it, no later child makes a tool call, and a finished child's result reads through the run's own view |
| LC-05 | Disposable | US-4.4, US-5.2 | No MCP adapter exists, so MCP is only refused by name |
| LC-06 | Disposable | US-4.3 | |
| LC-07 | Disposable, Browser | US-5.2, US-11.12, US-12.2 | Limits are enforced. The Assignments card shows a child's Expert and outcome, its link opens the child, and the child links back, which didn't exist before |
| LC-08 | Live product, Browser | US-4.2, US-4.8, US-10.1, US-11.4 | US-10.1 ran 9 kills during real paid calls, each reconciled at the worst case by its runner, with no charge looked up. The screen's reconciliation ran on an arranged kill with a scripted worker |
| LC-09 | **Partial, accepted** | US-5.4, US-7.2, US-11.12, Decision 0007 | Disposable, and live direct for readback. A real lost acknowledgment wasn't arranged. A call that fails after GitHub accepted it, whose issue isn't yet visible, could be created twice, which Decision 0007 states. A ruling on a changed attempt is now refused |
| LC-10 | **Partial, accepted** | US-5.3, US-11.7 | Tampering and replay hold on a disposable stack. PRD 9.2's requester, scope snapshot and policy version aren't stored on a request, and [US-13.1](../../../../SPECS.md#us-131-requester-scope-snapshot-and-policy-version-on-an-approval-request) schedules them after release, by Decision 0013 |
| LC-11 | Disposable, Browser | US-4.7, US-11.4 | How fast a running call stops isn't measured. A worker's drain can still send paid calls for up to 30 seconds |
| LC-12 | Disposable, Live product and install | US-4.8, LIVE-GOAL-1 run 4, US-11.3, US-12.6 | US-12.6's goal passed product verification with a required artifact on the final code. A failing content check never ran live. A goal with no stated requirement succeeds once anything is published |
| LC-13 | Disposable, Browser | US-4.6, US-11.12, US-12.2, US-12.3, [closing checks](closing-checks.json) | With the browser offline, an approval is decided, and back online its event appears, and a reload rebuilds the plan, approval, artifact and status from the server. The API's stream was also cut by TCP reset 5 times in one run, with events committing during each gap, and rebuilt from the cursor: 5 delivered in order against 5 stored. Chromium's offline mode stood in for a cut between the browser and the web app |
| LC-14 | Disposable | US-6.2 | The agent step has no iteration-specific test |
| LC-15 | **Partial, accepted** | US-7.1, US-11.8 | A missed occurrence shows on Operations, arranged. Times are injected, so real host downtime wasn't observed, which Decision 0013 leaves as a limit. Routine screens are later scope, by Decision 0009 |
| LC-16 | Disposable | US-8.1, US-8.2 | Revised by Decision 0009: one workspace can't read another's memory. Separation between users in a workspace is later scope |
| LC-17 | Disposable, Browser | US-3.2, US-3.4, US-11.1 | Revised by Decision 0009. Settings shows each route's stored date, configuration and limits, and a route with no record reads not qualified. `test_no_application_code_asks_for_strict_output` is the enforcing test, a pattern over three strict-output call forms in the source, so it covers that feature and not every unqualified one |
| LC-18 | Disposable, Live product and install for a key-string scan | US-3.1, US-7.2, US-9.1, LIVE-GOAL-1, US-10.1, US-11.3, [closing checks](closing-checks.json) | Nine secrets of a disposable stack, the provider key among them, were found nowhere in 29 whole request bodies, headers other than Authorization, events, application rows, stored objects or logs. A canary shows prompts, rows and objects were really read, and an artifact's name shows events were. On a scripted model, so a real model's replies weren't in it. The live scan covers durable rows and logs, for the OpenRouter key only. Redaction matches patterns, and the canary shows a value in a goal does reach prompts and rows |
| LC-19 | Fixture, Live direct for routing | US-2.6, US-3.4 | The upstream provider is `null` in every live report |
| LC-20 | Disposable, Browser | US-3.2, US-11.5, US-11.11, US-12.2, WORKER-INFERENCE-001 | With no key: Home, Settings, the run list, and a run's artifact listed and downloaded. A new run is refused, with no call added, against a fake upstream. A run already going without a key is WORKER-INFERENCE-001's, on mock and disposable evidence |
| LC-21 | Disposable, Live install for setup | US-3.1, US-3.2, US-9.2, US-11.3 | Recovery after real key loss isn't implemented, only a stated procedure |
| LC-22 | Disposable | US-3.1, US-9.2, WORKER-INFERENCE-001 | A real key has not been rotated. That work item is now complete as built, on mock and disposable evidence |
| LC-23 | **Partial, accepted** | US-3.4, US-10.1, US-11.2, US-11.12, Decision 0013 | Revised: preserved where the pinned SDK passes it on. Named choice, selection and SSE ran live. On Terra, the SDK removes the encrypted reasoning `id`, in 3 of 3 trials that returned metadata, and continuations still worked, which is what Decision 0013 accepts. Separately, Terra missed one `tool_required` case, 99 of 100 against the 98% gate in US-10.1 |
| LC-24 | Disposable | US-3.3, US-4.7, WORKER-INFERENCE-001, US-11.12 | Live 401, 402 and rollover weren't arranged |
| LC-25 | Disposable | US-2.6, US-8.1, US-11.6, US-11.12, US-12.2, US-12.3 | Revised by Decision 0009. The dispatch inventory matches the frozen role map on the real SDK with a fake transport, by role, route and each request's model, and guards catch a stray client by name, on loopback and by literal address. Live compaction wasn't reached, which this row doesn't ask for, where LC-03's does. Background learning has no dispatch to inventory. A connection made inside a C library wouldn't show, Unix sockets aren't recorded, and a stray by literal address after the first read isn't caught, which US-12.3 accepted as F3-2 |
| LC-26 | **Partial, accepted** | US-2.6, US-11.1, US-12.2, US-12.3 | Requests on a fake transport carry only the fields observed, with exact routing flags, and the check fails on a sampler flag. No request sets `reasoning`, so its shape check runs on the harness test's inputs only. Live reports don't record request bodies, which Decision 0013 leaves as a limit |
| LC-27 | Disposable, Live install | US-2.1, US-9.1, US-9.3, US-11.3, US-12.6 | |
| LC-28 | Disposable | US-2.3, US-2.5 | Expired tokens are a unit test with script-signed tokens. Realtime is removed, so it's refused by absence |
| LC-29 | Disposable, Live install | US-2.4, US-4.2, US-9.3, US-11.3, US-12.6 | Revised by Decision 0009: the worker and checkpointer pass in `agent_runtime`, and a LangGraph store is later scope |
| LC-30 | Disposable | US-4.5, US-9.1 | A wrapper raised the interruption during publication, with no real process death |
| LC-31 | Real sleep, Disposable, Live install | US-9.2, US-4.7, US-11.3, US-11.10, US-12.5, US-12.6 | Restore ran from the real install, to a disposable copy, twice. On the final code a real sleep of 988 seconds across 20 wakes ended `succeeded`, with no step sent twice. The model was scripted, so a real provider's connection dropped across a sleep isn't observed. The install's restore didn't run per-owner reads, a checkpoint read through the saver, or credential decryption, which ran on disposable stacks with an arranged credential |
| LC-32 | **Partial, accepted** | US-1.6 to US-1.8, US-12.3, Decisions 0012 and 0013 | Gate 0 repeated at the bound fingerprint. DH-A03's Claude part stays partial |
| LC-33 | Review | US-11.12, US-12.3 | Revised by Decision 0009: routine delivery follows Decision 0003, with independent review of the final code. US-11.12 took five rounds and US-12.3 four. Stories' own records were mostly written by the session that built them |
| LC-34 | **Partial, accepted** | US-2.5, US-11.11, US-12.2 | Axe at WCAG 2.1 AA with 0 violations across 42 captures in both themes, by Decision 0010. Tab reaches each control in order on every surface, in both themes, with each check shown failing on a page broken on purpose. No screen reader or person used it, which Decision 0013 leaves as a limit |

## MP: model providers

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| MP-A01 | Disposable | US-3.1 | Next.js's full dotenv grammar isn't matched, only a shared subset |
| MP-A02 | Disposable | US-3.2 | Against a fake upstream |
| MP-A03 | Disposable | US-3.1, US-3.2 | Against a fake upstream |
| MP-A04 | Disposable, Fixture | US-3.2, US-2.6, WORKER-INFERENCE-001 | The outage was against a fake upstream. The stale-catalog block through the worker is a unit test |
| MP-A05 | Fixture | US-2.6 | |
| MP-A06 | **Partial: the owner's** | US-3.4, US-10.1, Decision 0005 | DeepSeek's strict nested schemas fail, which Decision 0005 accepts, and DeepSeek is no longer offered, so its other limits don't reach new work. Terra refuses open objects with `400`. Cancellation shows only our side stopping. See [item 3](#what-needs-the-owner) |
| MP-A07 | **Partial: the owner's** | US-3.4, US-10.1 | Live, direct. "Unsupported selectors fail honestly" was never exercised live, as both routes honored the selector. A fake 404 is recorded as `unsupported` in `test_route_qualification.py`. See [item 3](#what-needs-the-owner) |
| MP-A08 | Disposable, Live direct and product | US-2.6, US-3.4, US-10.1, US-11.6, US-11.9 | Revised by Decision 0009: one route per run. The boundary and defaults hold |
| MP-A09 | Disposable, Live product | US-3.3, US-5.2, US-11.12, US-12.3, US-12.4 | Calls overlapped on a live route in a workspace with two slots. Round 5 refused nothing, so the cap under contention is disposable evidence only, and rollover wasn't live. A request that could reach Terra's long-prompt tier, counted in bytes, is refused before sending, which can come before the rate would apply |
| MP-A10 | Disposable | US-3.1, US-9.2, WORKER-INFERENCE-001 | A real key has not been rotated |
| MP-A11 | Disposable | US-3.1, US-3.2 | |
| MP-A12 | Disposable, Browser | US-3.2, US-9.1, US-11.5, US-12.2, WORKER-INFERENCE-001 | A workspace with no key lists and downloads its files, and inference is refused with no call added. A run already going without a key is WORKER-INFERENCE-001's, on mock and disposable evidence |

## LM: local Mac deployment

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| LM-A01 | Disposable, Live install | US-2.1, US-9.1, US-11.3, US-12.6 | Stopped after the exercise, with its data kept, at migration 35 of 35 |
| LM-A02 | Disposable, Live install | US-2.1, US-11.3, US-12.6 | Its own loopback ports, as others were held. Other projects, including `finance` and `mentor`, were identical before and after. Studio authentication was seen only on a disposable stack, as a redirect with the page not rendered |
| LM-A03 | Disposable, Live install | US-2.1, US-2.6, US-9.1, US-11.3 | |
| LM-A04 | **Partial: the owner's** | US-9.1, US-9.3, US-11.3, US-12.6 | `compose stop` and `up` kept the owner, runs and artifacts, on disposable stacks and the install. Four real migrations were applied, from a restored copy first. Restarting Docker itself or the Mac wasn't run. See [item 4](#what-needs-the-owner) |
| LM-A05 | Disposable | US-2.3, US-4.5 | |
| LM-A06 | Disposable, Browser | US-3.1, US-3.2, US-10.1, US-11.5, US-12.2, WORKER-INFERENCE-001 | Local non-AI use with no key: home, Settings, the run list, and a run's files |
| LM-A07 | **Partial: the owner's** | US-4.7, US-9.1, US-11.10, US-12.5 | A real sleep on the final code came through clean, with a scripted model. Network loss and a real provider across a sleep weren't observed. See [item 2](#what-needs-the-owner) |
| LM-A08 | Disposable, Live install | US-9.2, US-11.3, US-12.6 | Backup from the real install, restored to a disposable copy, its checks passing. Credential decryption ran on a disposable stack, with an arranged credential. Not to another machine |
| LM-A09 | **Partial, accepted** | US-2.1, US-2.4, US-10.1, US-12.4, US-12.7, Decision 0014 | Resources measured with two calls at once, on short goals. One of five rounds paused a run with no recorded cause, and that pause stays a limit by Decision 0014. US-12.7 now logs why a call's outcome is unknown, which explains the next one and doesn't fix it |

## DS: design system

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| DS-01 | Browser | US-2.5, US-11.11 | |
| DS-02 | Browser | US-2.5, US-11.11 | Changing appearance sends no request, and runs, approvals and workflows read the same afterward |
| DS-03 | Browser | US-2.5, US-11.11 | 21 surfaces in both themes, on shared components, which a harness test enforces. Eight named surfaces don't exist in the app, such as charts and a workflow canvas, so they pass by absence, with no decision naming them. [The summary](../US-11.11/summary.md) lists them |
| DS-04 | **Partial, accepted** | US-11.11, US-12.2, Decision 0010 | WCAG 2.1 AA measured in both themes: lowest text 4.74:1, boundaries 4.74:1, focus 14.5:1, hover 5.21:1. `--input` and light `--ring` stay below 3:1 alone, corrected by pairing. On every surface in both themes: keyboard reach and order, disabled controls named, no sideways scrolling on the page, with overflow inside elements unmeasured, and nothing moving when reduced, as nothing moves by default either. No person or screen reader, which Decision 0013 leaves as a limit. Zoom is a viewport width |
| DS-05 | Browser | US-2.5, US-11.11, US-12.2 | Screenshots for all 42 captures retained on the final tree, and the walk's results in [`results.json`](../US-11.11/results.json). `US-12.2/walk.json` is an earlier run of it. Storage and first paint come from US-2.5. No person looked, and browser zoom stands in as a viewport width |

## PRD 13.1: nonfunctional targets

These can change only by a documented revision. US-10.1's figures come from one client, and predate EPIC-11 and EPIC-12, so [item 6](#what-needs-the-owner) asks whether they carry over.

| Target | Status | Observed |
|---|---|---|
| Non-inference API, p95 below 300 ms | Met, in those conditions | 3.7 and 4.7 ms, in US-10.1, sequentially, with the worker stopped |
| Durable event in the UI, p95 below one second | Met, in those conditions | 492 ms, in US-10.1, on queued runs |
| Cancellation acknowledged within one second, dispatch stopped at the next boundary | Disposable | [12 of 12 running runs](closing-checks.json), each with a call in flight, at most 12.1 ms and a median of 10.1 ms. No call went out after the answer, all ended `cancelled`, and nothing stayed reserved. On a scripted model at the bound fingerprint. Queued runs: 8.1 and 9.5 ms in US-10.1, 20.2 ms through the web app |
| Recovery within 60 seconds of lease expiry | Met, in those conditions | 2.3 to 3.2 s, 3 kills, in US-10.1 |
| Stable during the two-call workload, with resources measured | **Partial: the owner's** | LM-A09 and [item 1](#what-needs-the-owner) |
| Reconstructible after backup and restore | Disposable, Live install | LC-31 and LM-A08 |
| Zero unauthorized effect in the security and replay suite | Met, by that runner's checks | 0 in US-10.1, with the database suites at the bound fingerprint |
| Model latency and capacity as measured outputs | Later scope | PRD 12.2's fields, by Decision 0013. US-3.4 and US-10.1 have what their runners measured |

## DH: development harness

From [US-12.3's Gate 0](../US-12.3/summary.md), at its bound fingerprint. US-1.8's and US-11.12's approvals are void.

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| DH-A01 | Static | US-12.3, `project_configuration` | |
| DH-A02 | Static and disposable | US-12.3 | Under `env -i`, with no `claude` on `PATH`, and exit 2 with tools missing |
| DH-A03 | **Partial, accepted** | US-1.4, US-1.8, US-12.3, Decision 0012 | Claude's crash, timeout and Stop recursion behavior isn't qualified. Script fixtures aren't reported as event delivery |
| DH-A04 | Mock and disposable | US-12.3, `fault_qualification` | 21 of 21, and a committed fault in a disposable copy |
| DH-A05 | Fixture | US-12.3 | The state fixture has its own table, not linked to the product's machine |
| DH-A06 | Disposable | US-1.7, US-11.3, US-12.3 | |
| DH-A07 | Disposable | US-1.7, US-2.3, US-12.3 | |
| DH-A08 | Mock | US-1.6, US-2.6, US-12.3 | |
| DH-A09 | Disposable | US-1.8, US-4.2, US-12.3 | |
| DH-A10 | Disposable | US-1.7, US-2.1, US-12.3 | |
| DH-A11 | Mock and disposable | US-1.6, US-12.3 | |
| DH-A12 | Report | US-12.3 | |
| DH-A13 | Report | US-12.3 | `scripts/evidence.py complete US-12.3` passes, which shows consistency, not correctness. Its work item says "on top of `37d0c73`", while the bound tree's sleep fix landed in `70c5162` |
| DH-A14 | Mock | US-1.5, US-12.3 | |
| DH-A15 | Mock | US-1.6, US-12.3 | |
| DH-A16 | Disposable | US-12.3 | Stale-lock and killed-run recovery, and arranged adapter states |
| DH-W01–02 | Replaced, for routine delivery | Decisions 0003 and 0013 | An archived OpenSpec change is the record. US-12.3 keeps a full one, which carries the baseline for US-1.3 to US-1.7 |
| DH-W03 | Review | US-12.3, Decision 0009 | Revised: independent review of the final code before a release |
| DH-W04–06 | Replaced, for routine delivery | Decisions 0003 and 0013 | Bound fingerprints and evidence directories exist only where a story asked for them, as US-12.3 did |

## What needs the owner

[Decision 0013](../../decisions/0013-release-closure.md) settled what it was asked. EPIC-12 delivered it, and these came out of that work or weren't in it. No source decides them.

| # | Item | What's known | Choices |
|---|---|---|---|
| **1** | **A run can pause with no recorded cause** (LM-A09, PRD 13.1) | In one of five rounds of two goals at once, a run's first call paused as `uncertain_acceptance`, apparently at no charge, and a person would have to rule on it. Nothing crashed. Nine of ten goals succeeded. Four rounds were clean, but those four ran a logging wrapper, and the paused one was the only round on the product's own entry point. The product records no cause, so it's unknown whether two calls at once has anything to do with it | Accept it as a limit and schedule recording the cause after release. Or record the cause now, a source change |
| **2** | **Network loss, and a real provider across a sleep** (LM-A07) | Neither was observed through this worker. A dropped connection has database cases, and the real sleeps used a scripted model, the method Decisions 0009 and 0013 chose, though neither states this limit | Accept both as limits. Or arrange network loss on a disposable stack, which may need a fix |
| **3** | **Two route behaviors** (MP-A06, MP-A07) | "Unsupported selectors fail honestly" was never exercised live, as both routes honor the selector, so it can't be arranged while they do. A provider's own stop on cancel isn't shown, only ours | Accept them as limits. Or measure the provider's stop, which would be paid |
| **4** | **Restarting Docker itself** (LM-A04, LM-07) | The containers were stopped and started, on disposable stacks and the install. A restart of Docker would also stop `finance` and `mentor`, so it wasn't run, and LM-07 names it | Read "Docker" as the containers, which revises the text. Or restart Docker yourself once, with the install running |
| **5** | **Active time can go uncounted** (PRD 6.5) | If a clock never catches up after a wake, a wall clock steps forward by more than 20 seconds, or a discount applies twice, the 15-minute budget can undercount. A cap that closed this is the defect a real sleep found. Model-call, tool and money limits don't depend on it. Only the delivery session has accepted this | Accept it as a limit. Or schedule a better rule after release |
| **6** | **What only the delivery session has accepted** | After a stop, a step already running can send further paid calls (N-70). A page reload losing Continue's kept key, so a later press can start a second paid run. And US-10.1's gates, which predate EPIC-11 and EPIC-12: Decision 0008 lets its result stand, and nothing carries it across those changes | Accept all three. Or repeat US-10.1's corpus at a cost like its US$1.22, under a new authorization |

**Answering these changes the binding.** Recording any answer as a decision or a PRD revision voids US-12.3's binding, so accepting isn't free of work: all of them go in together, followed by one review of what changed and one new Gate 0.

## Held out of this release, by decision

- **DeepSeek isn't offered for new runs,** by Decision 0013, until a recorded qualification and a decision bring it back.
- **PRD 9.2's approval fields and held-out replay** wait for [EPIC-13](../../../../SPECS.md#epic-13-after-release), for the owner to schedule.
- **PRD 12.2's timing metrics** are later scope, by Decision 0013.
- **PRD 8.3's `inputs` grant, `authenticated` reading raw emissions, a rollback's actor, a promoted memory's `created_by`, and routines reading policy and skill text at each occurrence** are accepted as limits for a single-owner release, by Decision 0013.

## Blocking findings

The 11 from the first assessment, as [Decision 0009](../../decisions/0009-release-scope-from-blocking-findings.md) decided them.

| ID | Finding | Now |
|---|---|---|
| **B1** | No persistent install path | **Done** in US-11.3, and the final code ran on it in US-12.6 |
| **B2** | Real Mac sleep unobserved, and wake handling not built | **Done** in US-11.10 and on the final code in US-12.5, where a real sleep found and then proved the fix for a defect |
| **B3** | Required screens incomplete | **Done** in US-11.4 to US-11.9, with the rest revised to later scope |
| **B4** | Independent review | **Done** in US-11.12 and US-12.3, with every open minor and major given an outcome |
| **B5** | H1 not established | **Met, with its stated limits,** by US-12.3 and Decisions 0012 and 0013 |
| **B6** | The UI misreports state | **Done** in US-11.1, with LC-17 revised |
| **B7** | Design partly unimplemented, evidence old | **Done** in US-11.11, and measured again on the final tree |
| **B8** | Only one role runs | **Revised:** one route per run, and US-11.6 and US-11.9 say so on screen |
| **B9** | No run controls on a screen | **Done** in US-11.4 |
| **B10** | Two named mechanisms missing | The store is **revised** to later scope. Reasoning has **its check**, which found the loss, and LC-23 is revised by Decision 0013 |
| **B11** | Memory not scoped to a user | **Revised:** scoped to the workspace in this single-owner release |

## Procedures

| Runbook | Exercised on | Not exercised |
|---|---|---|
| [`development-harness.md`](../../runbooks/development-harness.md) | Real checks and recovery, at US-12.3's fingerprint | Claude's crash and timeout behavior. Forward ingestion was last exercised in US-1.2 |
| [`local-supabase.md`](../../runbooks/local-supabase.md) | The real install, at US-11.3 and US-12.6 | Its recovery rows, a pinned-release upgrade |
| [`local-app.md`](../../runbooks/local-app.md) | The real install, at US-11.3 and US-12.6 | Studio |
| [`first-slice.md`](../../runbooks/first-slice.md) | A disposable stack, with a scripted model | A person following it |
| [`operations.md`](../../runbooks/operations.md) | The real install at US-11.3 and US-12.6, and `qualify_operations.py` at the final fingerprint | A drain cut short, reconciling a real uncertain call, retention, its GitHub section on the install, a run paused for a key or a stale catalog there, real sleep on the install |
| [`backup-restore.md`](../../runbooks/backup-restore.md) | The real install at US-11.3 and US-12.6, to a disposable copy, and `qualify_backup.py` at the final fingerprint | Another machine |
| [`upgrade.md`](../../runbooks/upgrade.md) | Four real migrations on the install, at US-11.3 and US-12.6, and `qualify_upgrade.py` at the final fingerprint | A real image or framework change, a failed migration on the install |
| [`mac-sleep.md`](../../runbooks/mac-sleep.md) | Real sleeps by the owner, at US-11.10 and US-12.5. Its failure list doesn't name `sleep_counted_as_work` | A real provider across a sleep |
| [`toolchains.md`](../../runbooks/toolchains.md) | Bootstrap, in US-12.3's disposable copy | A new machine |
| [`ohmyorch-delivery.md`](../../runbooks/ohmyorch-delivery.md) | This delivery itself | Not a user procedure |

There's no user guide apart from these runbooks. They were followed by the delivery session and, for sleep, the owner, and not by a person new to them.

## Limits on the release as it stands

- **The live evidence on the final code is small:** one goal on the install and one round of two goals. Task quality was measured earlier, in US-10.1, and not repeated.
- **Task quality is unjudged by a person.** String checks scored an assistant-written corpus, at 86.7% with a narrow margin, as [Decision 0008](../../decisions/0008-us-10-1-limits-accepted.md) accepts.
- **One model for new work.** Terra's goals succeeded 104 of 120 in US-10.1 and 9 of 10 in US-12.4. DeepSeek ran the protocol fixtures, none of its goals succeeded, and it isn't offered.
- **Promotion gates on a reviewer's text checks,** by Decision 0011, until US-13.2.
- **A rate limit ends a run,** by Decision 0011, and a person starts a linked new one. A page reload loses the kept key for that, so a press after one can start a second paid run.
- **Responsiveness:** [PRD 13.1's targets](#prd-131-nonfunctional-targets) were measured on disposable stacks, one client at a time. Under two calls at once, resources were measured and responsiveness wasn't.
- **A long workload is unmeasured.** Goals of about 15 seconds.
- **Duplicate protection on GitHub is narrower, not gone.** The wait rests on one measurement of 8.9 seconds.
- **Mocked provider behavior isn't live qualification.** Credential failures, catalog outages, lost acknowledgments, and compaction and children through the worker used fakes.
- **Review's open nonblocking items** are in [US-11.12's](../US-11.12/summary.md#dispositions) and [US-12.3's](../US-12.3/summary.md#dispositions) dispositions.
