# US-10.2: release record

**Verdict: not release-ready.** Requirements below are checked against their own acceptance text, and [11 blocking findings](#blocking-findings) are open. US-10.2 stays `IN PROGRESS`, and neither H1 nor product acceptance is claimed.

An independent reviewer found this record's first version overclaimed. [`review.md`](review.md) lists each finding and what was done with it. This corrected version hasn't been reviewed again.

## Revisions

| Source | Class | Revision |
|---|---|---|
| `full` 24 checks, `db` 8, `operations` 7, `harness`, each exit 0 on 2026-11-06 | Mixed, as each row says | `8ddec71` with this story's backlog status edit. All four report input fingerprint `a1117e0ad7bfd74a…`. An uncommitted `.env.example` line for `TAVILY_API_KEY`, not from this work, was also in the tree |
| [US-3.4](../US-3.4/summary.md) protocol corpus | Live, direct | `f96cfe2` and earlier, before the 130-second timeout fix |
| [LIVE-GOAL-1](../LIVE-GOAL-1/summary.md), DeepSeek goals | Live, product | `2e71720` and later. Its goals failed |
| [US-7.2](../../../../openspec/changes/archive/2026-11-06-us-7-2-select-qualify-first-consequential/verification.md) against GitHub | Live, direct | `f1bcedc` with that story's fix |
| [US-10.1](../US-10.1/summary.md) corpus | Live, product | `f563b7b` plus uncommitted work, fingerprinted in its raw report |
| [US-10.1](../US-10.1/summary.md) second run | Live, product | `a8a4c4d` plus that story's runner changes |

Raw reports are in `.checks/`, ignored and local. The product code at the final revision has had no independent review.

## How to read a row

| Class | Meaning |
|---|---|
| **Live, product** | Real OpenRouter through the product's API and worker, on a disposable stack |
| **Live, direct** | Real OpenRouter or GitHub through a runner, with no worker, ledger or approval around it |
| **Disposable** | Real local services on a disposable target, with a scripted or fake model |
| **Browser** | The real web app in Chromium, with no database or service stack |
| **Fixture** | Unit or static checks, with no real service |
| **Partial** | Part of the acceptance text wasn't observed. The row says which part |
| **Partial, accepted** | The same, and the owner has accepted it in a decision |
| **Not met** | The acceptance text is contradicted by what exists |
| **Replaced** | A decision by the owner put something else in its place for routine delivery |

Story records are at `openspec/changes/archive/*-<story>-*/verification.md`, and each states what it didn't exercise. Most were written by the session that built the story, under Decision 0003. No store means no persistent stack: there has never been one, so see [B1](#blocking-findings) for every row.

## LC: product requirements

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| LC-01 | **Partial** | US-2.6, Decision 0006, US-10.1 | 14 defaults resolve to Terra. Only `executor` dispatches, and no call in a live run reached compaction. See [B8](#blocking-findings) |
| LC-02 | Disposable | US-5.1 | |
| LC-03 | **Partial** | US-4.3, US-8.1 | Compaction used a scripted model. A person inspecting criteria after a real compaction wasn't observed |
| LC-04 | **Partial** | US-4.3, US-5.2 | Calls stop across a child. Partial results across descendants aren't asserted, and a child's time limit has no case |
| LC-05 | Disposable | US-4.4, US-5.2 | No MCP adapter exists, so MCP is only refused by name |
| LC-06 | Disposable | US-4.3 | |
| LC-07 | **Partial** | US-5.2 | Limits are enforced. "Visible" isn't: no browser test covers the Assignments card. Two levels with real children weren't run |
| LC-08 | Live, product | US-4.2, US-4.8, US-10.1 | A kill during a model call needs an owner's reconciliation, and no screen offers it. See [B9](#blocking-findings) |
| LC-09 | Disposable, Live direct for readback | US-5.4, US-7.2 | A real lost acknowledgment. An issue slower than the 15-second wait could still duplicate |
| LC-10 | Disposable | US-5.3, review fixes | |
| LC-11 | Disposable | US-4.7 | How fast a running call stops isn't measured |
| LC-12 | Disposable, one Live product case | US-4.8, LIVE-GOAL-1 run 4 | A failing content check never ran live, as the corpus scored with a hidden runner check, not product verification. A goal with no stated requirement succeeds once anything is published |
| LC-13 | **Partial** | US-4.6 | Status and event order rebuild across a disconnect on a queued run. Plan, approval and artifact reconstruction across one isn't observed, and neither is a cut TCP connection |
| LC-14 | Disposable | US-6.2 | The agent step has no iteration-specific test |
| LC-15 | **Partial** | US-7.1 | Times are injected, so real host downtime wasn't observed. No screen for routines |
| LC-16 | **Partial** | US-8.1, US-8.2 | Workspaces are isolated. A user's memory from another user's isn't, as a run records no owner. See [B11](#blocking-findings) |
| LC-17 | **Not met** | US-3.2, US-3.4 | See [B6](#blocking-findings) |
| LC-18 | Disposable, Live product for a key-string scan | US-3.1, US-7.2, US-9.1, LIVE-GOAL-1, US-10.1 | The live scan covers durable rows and logs, for the OpenRouter key only. Prompts sent and stored objects weren't scanned. Redaction matches patterns |
| LC-19 | Fixture, Live direct for routing | US-2.6, US-3.4 | The upstream provider is `null` in every live report |
| LC-20 | **Partial** | US-3.2 | Home and Settings stay usable with no key. Files and history weren't exercised, and no run list exists. Against a fake upstream |
| LC-21 | Disposable | US-3.1, US-3.2, US-9.2 | Recovery after real key loss isn't implemented, only a stated procedure |
| LC-22 | Disposable | US-3.1, US-9.2, WORKER-INFERENCE-001 | A real key has not been rotated. That work item is still `IN PROGRESS`, with a third fix round unreviewed |
| LC-23 | **Partial** | US-3.4, US-10.1 | Named choice, selection and SSE ran live. Preserved reasoning metadata has no code or test. See [B10](#blocking-findings). Terra missed one `tool_required` case in US-10.1 |
| LC-24 | Disposable | US-3.3, US-4.7, WORKER-INFERENCE-001 | Live 401, 402 and rollover weren't arranged |
| LC-25 | **Partial** | US-2.6, US-8.1 | A real summarization trigger in the SDK wasn't reached, and no instrumented inventory across all 14 roles exists. See [B8](#blocking-findings) |
| LC-26 | **Partial** | US-2.6 | Sampler flags are refused on a fake transport. "No reasoning-off" holds by absence, and `reasoning` has no shape check. Schema capability has no runtime gate, only a source check. Live reports don't record request bodies |
| LC-27 | Disposable | US-2.1, US-9.1, US-9.3 | |
| LC-28 | Disposable | US-2.3, US-2.5 | Expired tokens are a unit test with script-signed tokens. Realtime is removed, so it's refused by absence |
| LC-29 | **Partial** | US-2.4, US-4.2, US-9.3 | Worker and checkpointer are shown. No LangGraph store exists, and memory lives in `public.memory_items`. See [B10](#blocking-findings) |
| LC-30 | Disposable | US-4.5, US-9.1 | A wrapper raised the interruption during publication, with no real process death |
| LC-31 | **Partial** | US-9.2, US-4.7 | Restore is shown. Sleep isn't: `SIGSTOP` stood in, and wake detection isn't built. See [B2](#blocking-findings) |
| LC-32 | **Partial** | US-1.6 to US-1.8 | See [B5](#blocking-findings) |
| LC-33 | **Partial** | Archived OpenSpec changes | Decision 0003 replaced per-item review and records for routine delivery. See [B4](#blocking-findings) |
| LC-34 | **Partial** | US-2.5, browser suites | Axe covers some key flows, not sign-in or key setup. See DS-03 to DS-05 |

## MP: model providers

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| MP-A01 | Disposable | US-3.1 | Next.js's full dotenv grammar isn't matched, only a shared subset |
| MP-A02 | Disposable | US-3.2 | Against a fake upstream |
| MP-A03 | Disposable | US-3.1, US-3.2 | Against a fake upstream |
| MP-A04 | Disposable | US-3.2, US-2.6, WORKER-INFERENCE-001 | The outage was against a fake upstream. A stale-catalog block through the worker wasn't confirmed by the review |
| MP-A05 | Fixture | US-2.6 | |
| MP-A06 | **Partial, accepted** | US-3.4, US-10.1 | DeepSeek's strict nested schemas fail, Decision 0005. Terra refuses open objects with `400`. DeepSeek's real fragmentation is fake-only, and cancellation shows only our side stopping. DeepSeek has no run at the 130-second timeout |
| MP-A07 | Live, direct | US-3.4, US-10.1 | "Unsupported selectors fail honestly" was never exercised, as both routes honored the selector |
| MP-A08 | **Partial** | US-2.6, US-3.4, US-10.1 | The boundary and defaults hold. Child, reviewer and summary assignments can't differ from the executor's route. See [B8](#blocking-findings) |
| MP-A09 | Disposable | US-3.3, US-5.2 | Not on a live route |
| MP-A10 | Disposable | US-3.1, US-9.2, WORKER-INFERENCE-001 | A real key has not been rotated |
| MP-A11 | Disposable | US-3.1, US-3.2 | |
| MP-A12 | **Partial** | US-3.2, US-9.1 | Local files with no key weren't exercised |

## LM: local Mac deployment

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| LM-A01 | Disposable | US-2.1, US-9.1 | |
| LM-A02 | Disposable | US-2.1 | Persistent ports 54321 and 54322 were held by another project's stack when checked |
| LM-A03 | Disposable | US-2.1, US-2.6, US-9.1 | |
| LM-A04 | **Partial** | US-9.1, US-9.3 | Stop and start kept data on a disposable project |
| LM-A05 | Disposable | US-2.3, US-4.5 | |
| LM-A06 | **Partial** | US-3.1, US-3.2, US-10.1 | Local non-AI use with no key covers home and Settings only |
| LM-A07 | **Partial** | US-4.7, US-9.1 | Real sleep and network loss weren't observed. See [B2](#blocking-findings) |
| LM-A08 | Disposable | US-9.2 | A disposable source, with an arranged credential |
| LM-A09 | Disposable | US-2.1, US-2.4, US-10.1 | The resource envelope is one short sequential run |

## DS: design system

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| DS-01 | Browser | US-2.5 | |
| DS-02 | Browser | US-2.5 | That appearance can't alter execution state was observed before any run state existed, and hasn't been repeated |
| DS-03 | **Partial** | US-2.5, later browser suites | Named surfaces added later weren't inspected in both themes, no chart exists, and `components/ui/` holds only `button` and `card`, though shadcn is required. See [B7](#blocking-findings) |
| DS-04 | **Partial** | Axe in the operations, approvals, experts, slice, slice-workflows, appearance and run-workspace suites | No axe on sign-in or key setup. Contrast in actual states, including hover and disabled, zoom and reduced motion aren't measured for later screens |
| DS-05 | **Partial** | US-2.5 | Retained screenshots cover only the screens that existed at US-2.5 |

## DH: development harness

The Gate 0 review approved `b94727d`, and said any later source change voids it. `scripts/evidence.py validate US-1.8` now fails, with 31 problems, as it should. The checks below passed again on this revision, but the review didn't repeat. The reviewer checked these rows lightly, and DH-A01, A06, A07, A10 and A12 only against Gate 0's list.

| ID | Class | Observed in | Not observed, or limit |
|---|---|---|---|
| DH-A01 | Fixture | US-1.2, `project_configuration` | |
| DH-A02 | Fixture | US-1.4, US-1.6 | |
| DH-A03 | **Partial** | US-1.4, US-1.8, HARNESS-WORKTREE-ROOT-001 | Claude's crash and timeout behavior isn't qualified |
| DH-A04 | Fixture | US-1.6, `fault_qualification` | |
| DH-A05 | Fixture | US-1.6 | |
| DH-A06 | Disposable | US-1.7, US-2.4 | |
| DH-A07 | Disposable | US-1.7, US-2.3 | |
| DH-A08 | Fixture | US-1.6, US-2.6 | |
| DH-A09 | Disposable | US-1.8, US-4.2 | |
| DH-A10 | Disposable | US-1.7, US-2.1 | |
| DH-A11 | Fixture | US-1.6, US-1.8 | |
| DH-A12 | Fixture | US-1.8 | |
| DH-A13 | **Partial** | US-1.8 | The sample satisfied DH-W01–06 at `b94727d`, and its approval is now void |
| DH-A14 | Fixture | US-1.5, US-1.6 | |
| DH-A15 | Fixture | US-1.6, US-1.8 | |
| DH-A16 | Disposable | US-1.8 | Exercised at `b94727d` |
| DH-W01–02 | Replaced | Decision 0003 | An archived OpenSpec change is the record for routine delivery |
| DH-W03 | **Partial** | US-1.8, US-4.8, the US-5.1 to US-9.3 review | No review for most stories. See [B4](#blocking-findings) |
| DH-W04–06 | Replaced | Decision 0003 | Bound fingerprints and evidence directories exist only where a story asked for them |

## Blocking findings

Each stops a release claim, and none can be settled by another check. The owner has decided all 11, in [Decision 0009](../../decisions/0009-release-scope-from-blocking-findings.md), and they stay open until the work is delivered and this record is assessed again. Some requirement text has been revised since the rows above were written, so B8, B10, B11 and part of B6 now need evidence against the revised text.

| Finding | Now owned by |
|---|---|
| B1 | US-11.3 |
| B2 | US-11.10 |
| B3 | US-11.5 to US-11.9, with the rest revised |
| B4, B5 | US-11.12 |
| B6 | US-11.1, with LC-17 revised |
| B7 | US-11.11 |
| B8 | Revised, with US-11.6 and US-11.9 saying so on screen |
| B9 | US-11.4 |
| B10 | US-11.2 for reasoning, with the store revised |
| B11 | Revised |

| ID | Finding | Requirements | What resolves it |
|---|---|---|---|
| **B1** | **No persistent install path.** `scripts/app_db.py` refuses anything but a disposable target, and the operations runbook says the guarded persistent apply isn't implemented. US-9.1's scenario names the persistent stack, and closed on a disposable stand-in, as `PASS, arranged`. Every result here comes from throwaway stacks | LM-A01, LM-A04, LC-27, MP-A12, US-9.1 | Build the apply path and exercise a real install, or revise these requirements |
| **B2** | **Real Mac sleep is unobserved, and wake handling isn't built.** `SIGSTOP` stood in. Recheck on wake and a timed artifact reconciliation don't exist | LC-31, LM-A07 | The owner runs a real sleep test, and decides whether wake handling is required |
| **B3** | **Required screens are incomplete.** Absent from PRD 12.1's list: routines, skill and knowledge versions and a test run in the Expert editor. Chat, a model picker and the complete role map in the run workspace. Tool attempts, checkpoints, token counts and provider identity per role in the inspector. Reason and target in the approval inbox. Delayed schedules, OpenRouter availability, restore history and qualification evidence in Operations. Approved model identities and role policy in Settings, so a person can't choose DeepSeek or an override. Routines, memory and improvements have API routes and no screen. No run list exists | PRD 12.1, LC-15, LC-16 | Build them, or revise PRD 12.1 |
| **B4** | **Independent review.** LC-33 and DH-W03 still ask for it, Decision 0003 removed it for routine delivery, and US-10.2's own Given requires it. No review has seen the final code. The 41 minors from the US-5.1 to US-9.3 review have no disposition, majors M8, M30, M32 and M33 have open owner questions, and WORKER-INFERENCE-001 is `IN PROGRESS` with a fix round unreviewed | LC-33, DH-W03, US-10.2 | Run a final review and settle its findings, and decide whether LC-33 stands or is revised |
| **B5** | **H1 isn't established.** Gate 0's approval is void, and Claude's crash and timeout behavior isn't qualified | LC-32, DH-A03, DH-A13 | Repeat the review at the final revision, and qualify or formally drop that part |
| **B6** | **The UI misreports state.** Settings always says "Not qualified yet", and the contract's only value is `not_qualified`, so a test pins it. Both routes qualified with limits, which it can't express. An admitted goal says "No worker runs it yet, so no model has been called", which is false with inference on. Unqualified features aren't disabled at runtime, by Decision 0005's own account | LC-17 | A durable qualification record with date and configuration, a contract change and corrected text |
| **B7** | **Design is partly unimplemented and its evidence is old.** Forms use native inputs, and Operations' inputs lack the tokens. Later screens have no retained both-theme screenshots or measured contrast | DS-03 to DS-05, LC-34 | Move to the required components, then capture and review all named surfaces |
| **B8** | **Only one role runs.** `worker_inference.py` hard-codes `executor`, so the other 13 bindings are frozen and never dispatched. A run whose summarizer differs pauses with `route_not_bound` at its first compaction, review finding M30, unfixed. The 14-role design isn't exercised | LC-01, LC-25, MP-A08 | A worker holding several routes, or a revision to what the role map promises |
| **B9** | **A person can't control a run from a screen.** No page offers pause, cancel, resume or model-call reconciliation. PRD 10.3 makes cancellation available from every nonterminal state. A run killed during a model call can be recovered only through the API | PRD 10.3, LC-08, LC-11 | Add the controls |
| **B10** | **Two named mechanisms don't exist.** Reasoning metadata isn't preserved across continuation by any code or test, and no LangGraph store exists, though the PRD places one in `agent_runtime` | LC-23, LC-29 | Build each, or revise the requirement |
| **B11** | **Memory isn't scoped to a user.** Workspaces are isolated, but a run records no owner | LC-16 | Add it, or revise LC-16 to the workspace |

## Procedures

The reviewer checked `operations.md` only, so the rest of this table is unreviewed.

| Runbook | Exercised on | Not exercised |
|---|---|---|
| [`development-harness.md`](../../runbooks/development-harness.md) | Real checks, at US-1.8 and on this revision | Claude's crash and timeout behavior |
| [`local-supabase.md`](../../runbooks/local-supabase.md) | A disposable project | Its recovery rows and upgrade path |
| [`local-app.md`](../../runbooks/local-app.md) | Through qualification, with disposable values | Its persistent steps |
| [`first-slice.md`](../../runbooks/first-slice.md) | A disposable stack, with a scripted model | A person following it |
| [`operations.md`](../../runbooks/operations.md) | `qualify_operations.py`, on this revision | A persistent stack, real sleep, and its GitHub section apart from the qualifier |
| [`backup-restore.md`](../../runbooks/backup-restore.md) | `qualify_backup.py`, on this revision | A persistent source, or another machine |
| [`upgrade.md`](../../runbooks/upgrade.md) | `qualify_upgrade.py`, on this revision | A real image or framework change |

There's no user guide. A person can't yet follow these to install and use the product, because of B1.

## Limits on the release as it stands

- **Nothing here is about a real installation.** All results are from disposable stacks.
- **Task quality is unjudged by a person.** String checks scored an assistant-written corpus, at 86.7% with a narrow margin, as [Decision 0008](../../decisions/0008-us-10-1-limits-accepted.md) accepts.
- **One model ran the corpus.** DeepSeek ran the protocol fixtures, and [none of its goals succeeded](../LIVE-GOAL-1/summary.md), through the 512-token limit and through rejected plans.
- **Concurrent load is unmeasured.** Goals ran one at a time.
- **PRD 12.2's metrics aren't implemented,** such as queue wait, time to first token and cancellation delay.
- **Duplicate protection on GitHub is narrower, not gone.** The wait rests on one measurement of 8.9 seconds.
- **Mocked provider behavior isn't live qualification.** Credential failures, catalog outages and lost acknowledgments used fakes.
