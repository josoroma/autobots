# Independent review, round 1: earlier open findings

Saved as the reviewer returned it, at commit `5012235`. Read-only, and nothing was run.

# US-11.12 independent review: open findings at 5012235

**Reviewer context:** independent, read-only, using Read, Grep and Glob. I ran nothing, and I did not author this code.

**Scope:** the working tree at 5012235. Its uncommitted paths (README-QA.md, docs/diagrams, DOC-QA-001, the US-11.12 change, .env.example) were not in the code I reviewed. I computed no fingerprint, so this binds to the revision name only.

**Path prefixes in the tables:**
- `A/` = `/Users/josoroma/sites/autobots/services/agent/src/autobots/`
- `T/` = `/Users/josoroma/sites/autobots/tests/db/`
- `W/` = `/Users/josoroma/sites/autobots/apps/web/components/`
- `M/` = `/Users/josoroma/sites/autobots/supabase/migrations/` (by migration number)

## Summary

- **Count:** the Minors section has 41 bullets, as the record says, but they hold **73 separate statements**. US-11.12#3 should settle them by N-number.
- **Status of the 73:** 7 fixed, 1 no longer applies, 65 still present (6 of those narrowed or partly addressed: N-12, N-21, N-26, N-34, N-58, N-59).
- **Severity of the 73:** 5 blocking (N-2, N-8, N-9, N-41, N-71), 2 major (N-18, N-70), 59 minor, 7 none.
- **Recommendations for the 73:** 23 fix now, 7 later, 36 accept, 7 close.
- **Worker inference:** two items meet your blocking definition (WI-1, WI-2, money past a limit). Each overrun is limited to the excess on the run's last admitted call. Nothing else I read in that path is blocking, but evidence is unbound and compaction through it is unexercised.
- **Decisions:**
  - The WORKER-INFERENCE-001 fail behavior matches the code.
  - M30 and M32 match.
  - M33's behavior matches, but its deferral points at a finished story that never built it.
  - M8 is only half enforced, because a session pin bypasses it.

"Blocking" follows your definition literally. Most of these are narrow and small to fix, and each row says so.

## Table 1: Minors

Recommendations are Fix now, Accept or Later. "Later (LC-16)" means with member separation, which Decision 0009 moved to later scope.

| ID | Statement | Status | Evidence | Severity | Recommendation |
|---|---|---|---|---|---|
| N-1 | "assignment writes are unfenced" | Present | `A/application/assignments.py:263-267`, `A/application/goal_loop.py:612-616` | Minor | Accept: writes the same child's result, and run transitions stay fenced |
| N-2 | "`_settle_children` records `cancelled` even for a child that succeeded" | Present | `goal_loop.py:588-616`, shown at `W/run-workspace.tsx:383` | Blocking: false outcome shown. Needs a parent dying before recording, then a cancel | Fix now: derive it from the child's status |
| N-3 | "a cancel between the gateway check and `hold_lease` orphans a new child" | Fixed | `assignments.py:95-102`, stray cancel at `goal_loop.py:591-593`, `T/assignment_check.py:229-249` | None | Close |
| N-4 | "`tools=["calculate"]` still grants delegation" | Present | `assignments.py:58-59` | Minor: tools can't widen, only shared limits are used | Fix now: one condition |
| N-5 | "versions come from the Expert's offer, not the parent's frozen grant" | Present | `assignments.py:49-53` | Minor | Accept: one version table, and a bump blocks saved runs (`A/domain/execution.py:44-51`) |
| N-6 | "a grandchild's path isn't under its parent's grant" | Present | `assignments.py:115-116` | Minor | Accept: files are keyed by the run's own ID (`A/application/tools.py:36-37`) |
| N-7 | "the `inputs` grant is empty in practice" | Present | `assignments.py:116`, `A/application/runs.py:231`, `tools.py:36-37` | Minor | Later: new post-release story on PRD 8.3 context passing |
| N-8 | "a child shows the Expert's own bindings" | Present | `A/application/run_projection.py:200-216`, shown at `W/run-workspace.tsx:303-310`. The child really uses the parent's snapshot (`assignments.py:128`, `T/assignment_check.py:99`) | Blocking: page can name the wrong model. The role map on the same page is right | Fix now: read the frozen snapshot |
| N-9 | "its spend shows 0" | Present | `run_projection.py:73-77` filters on `root_run_id = r.id`. Shown at `W/run-workspace.tsx:457-460, 471-473`, reachable from `W/run-list.tsx:81` | Blocking: false US$0 | Fix now: include `i.run_id = r.id` |
| N-10 | "a session-create retry after a new revision returns 409" | Present | `A/application/experts.py:192-200` | Minor | Accept: no duplicate, and a new key works |
| N-11 | "`expert_id` without a session is ignored silently" | Present, and `expert_version` too | `A/api/run_routes.py:102`, `A/contracts/run_commands.py:20-21`. The run gets default grants (`runs.py:248`) | Minor | Fix now: refuse with 422 |
| N-12 | "`assignment_check`... assert less than they claim" | Partly present | `T/assignment_check.py:111` names "no child" but asserts only the code. `:225` names "settles nothing" but asserts only generation. Old lines can't be mapped, as I couldn't read `dce9e19` | Minor | Fix now: the assertions |
| N-13 | "nothing covers a child hitting `budget_exceeded`" | Present | Grep of `tests/db` and `services/agent/tests`. `T/assignment_check.py:127-132` covers the call count only | Minor | Fix now: it's a money path |
| N-14 | "...or the time limit" | Present | `T/goal_loop_check.py:130` is root only | Minor | Fix now, with N-13 |
| N-15 | "`output_too_large` records `unknown` but doesn't stop the loop" | Present | `A/application/tool_gateway.py:401-404`, `A/adapters/loop_middleware.py:59-68` | Minor | Fix now: add it to `STOPPING` |
| N-16 | "during a cancel... relabelled `lease_lost`" | Fixed | `goal_loop.py:634-637`, `T/blocker_check.py:204-216` | None | Close |
| N-17 | "during a... pause... relabelled `lease_lost`" | Present | `A/domain/runs.py:37`, `goal_loop.py:674-675, 703-704` | Minor | Accept: the unknown stays visible and resume is refused (`run_routes.py:253, 263`) |
| N-18 | "a verdict binds to the operation, not the attempt" | Present | `A/application/reconciliation.py:75-94`. A ruling grants another try (`A/application/approvals.py:150-152`), and `failed` skips the readback (`tool_gateway.py:361-362`). The GitHub connector is real now | Major: a stale `not_delivered` ruling can resend. It takes a stale page and a new key | Fix now: the verdict carries the receipt's generation, and a mismatch is refused |
| N-19 | "opposite lock orders can deadlock" | Present | `approvals.py:94-97, 129` vs `runs.py:384-396, 415-419`. The docstring at `runs.py:371` overclaims | Minor | Accept: state stays consistent |
| N-20 | "the routes don't handle the error" | Present | `A/api/approval_routes.py:87-103`, `run_routes.py:194`, `A/api/errors.py:38-40` | Minor | Accept: retrying the same key is safe |
| N-21 | "`CommandRefused` and `LeaseLost` escape the pass" | Narrowed | `goal_loop.py:294, 500-509`, approval gate via `A/adapters/tool_middleware.py:39-42`. Others caught at `goal_loop.py:441-445, 703`. Worker survives (`A/operations/worker.py:143, 271`) | Minor | Accept: settles at lease expiry |
| N-22 | "no requester" | Present | `M/16`, `M/33` | Minor | Later (LC-16) |
| N-23 | "no... resource target" | Fixed | `M/33`, `tool_gateway.py:258`, `approval_routes.py:66` | None | Close |
| N-24 | "no... scope snapshot" | Present: hash only | `M/16:12`, checked at `approvals.py:138` | Minor | Later (LC-16) |
| N-25 | "no... policy version" | Present | `M/16`, `M/33` (reason text only) | Minor | Later (LC-16) |
| N-26 | "no human-readable diff" | Partly present | Whole arguments are shown (`approval_routes.py:59-62`), with no diff | Minor | Accept: the one connector only creates, so there's nothing to diff |
| N-27 | "the readback path ignores `too_large`" | Present | `tool_gateway.py:373` | Minor | Accept: readback output comes from the tool's own model, and I saw no harm |
| N-28 | "...and writes no event" | Present | `tool_gateway.py:374`. Only the operator path writes one (`reconciliation.py:95-99`) | Minor | Accept: the receipt shows in the inspector |
| N-29 | "Tests: no stale worker" | Fixed | `T/blocker_check.py:104-133` | None | Close |
| N-30 | "no... cancel during dispatch" | Present, as far as I found | Not in the checks I read or grepped. `T/blocker_check.py:176-202` is a pause. Unread cases can't be excluded | Minor | Accept: admission holds its lock and is tested |
| N-31 | "no... cancel during... readback" | Fixed | `T/major_check.py:87-105` | None | Close |
| N-32 | "no... decision racing a cancel" | Present | `T/approval_check.py:157-174` is sequential | Minor | Accept: row locks serialize it |
| N-33 | "`effect_check.py:130` uses a random UUID as 'another run'" | Present | `T/effect_check.py:130` | Minor | Accept: it still fails if the filter is removed |
| N-34 | "bad config values give untyped 500s" | Narrowed | Unhashable values raise at `A/domain/workflows.py:102, 104, 107, 115`. A bad `expert_id` raises at `A/application/workflows.py:172, 182` | Minor | Accept: nothing runs, API callers only |
| N-35 | "another workspace's Expert returns `internal_error` after the version is published" | Present | `workflows.py:125-128, 176-183`, `A/api/workflow_routes.py:215` | Minor | Accept: isolation holds, and it fails closed |
| N-36 | "`config` and `inputs` have no size limit" | No longer applies through the product path | Contract is still open (`A/contracts/workflows.py:19, 153`), but the BFF caps at 64 KiB (`/Users/josoroma/sites/autobots/apps/web/lib/bff.ts:9, 79-81`) | Minor | Accept |
| N-37 | "`authenticated` can read raw emissions" | Present. **I can't confirm reachability by reading** | `M/19:28, 35-37`, with no later revoke. PostgREST exposes `public` in the upstream compose (`infra/supabase/upstream/docker-compose.yml:43, 264`). Overlay not checked | Minor: same workspace only | Later (LC-16) |
| N-38 | "immutable by grant only" | Present | `M/18:42` | Minor | Accept: changing it needs the owner role |
| N-39 | "`run_workflow` doesn't recheck `graph_hash`" | Present | `A/application/workflow_runner.py:272-278` | Minor | Accept: same reason as N-38 |
| N-40 | "`workflow_executions.run_id` is nullable" | Present | `M/19:2`. Always set in `workflows.py:262-275` | Minor | Accept |
| N-41 | "a parse failure stops polling while the page says 'Live'" | Present | `W/workflow-monitor.tsx:45, 51, 93-96` | Blocking: false "Live". Needs a malformed reply | Fix now: catch it and show reconnecting |
| N-42 | "no reachability check" | Present | `domain/workflows.py:247-261`. Required links and no cycles leave only dead ends | Minor | Accept |
| N-43 | "never exercises `_commit`'s fence" | Present | `T/workflow_run_check.py:152-159` stops at `workflow_runner.py:242-244`, before `:130` | Minor | Fix now: call `_commit` with a stale scope |
| N-44 | "cancels a queued run with no worker" | Present | `T/workflow_run_check.py:193-198`. Its comment says "between instances" | Minor | Fix now: rename it or make it a real case |
| N-45 | "No kill during an effect" | Present for workflows | `T/workflow_worker.py:24, 33`. Goal loop is covered by `T/effect_check.py:103-114` | Minor | Accept: same gateway |
| N-46 | "no agent restart" | Present for workflows | `T/workflow_run_check.py:186-191`. Goal loop is covered by `T/assignment_check.py:272-292` | Minor | Accept: same assign tool |
| N-47 | "`store_summary` and `offload_large` have no fence" | Present | `A/application/compaction.py:78-81, 212-216` | Minor | Accept: no harm established here either |
| N-48 | "model policy and skill text are read at each occurrence" | Present | `A/application/routines.py:285-304`, `workflows.py:224-233`, docstring `routines.py:3-4` | Minor | Accept: each occurrence is a new admission that freezes then. Decision 0011 doesn't cover this, so tell the owner |
| N-49 | "non-UUID evidence ID likely gives a 500 and strands the candidate" | Present, not run | `A/contracts/improvements.py:17`, `A/application/improvements.py:68-71`. "Strands" overstates it: reject still works (`:205-206`) | Minor | Accept |
| N-50 | "concurrent promotions collide and return a 500" | Present | `improvements.py:210-230`, `A/api/improvement_routes.py:88-91` | Minor | Accept: fails safe, and a retry works |
| N-51 | "rollback records no actor" | Present | `improvement_routes.py:97-103` | Minor | Later (LC-16) |
| N-52 | "promoted memory's `created_by` is the workspace ID" | Present | `improvements.py:176-180`. `reviewed_by` is kept at `:226-228` | Minor | Later (LC-16) |
| N-53 | "'admitted work keeps its own' is untrue for memory" | Present | `improvements.py:246-247`, `A/application/memory.py:69-76` | Minor | Fix now: wording |
| N-54 | "`AUTHORITY_CLAIMS` is bypassed by rewording" | Present | `improvements.py:23-29` | Minor | Accept: a person decides, and nothing here grants anything |
| N-55 | "...or a newline" | Present: no `DOTALL` | `improvements.py:23-29` | Minor | Fix now: one flag |
| N-56 | "Tests: nothing covers workflow budgets" | Present | `T/major_check.py:388-395` checks the stored limit only | Minor | Fix now, with N-13 |
| N-57 | "...the 1,000 cap" | Fixed | `services/agent/tests/test_routines.py:101` | None | Close |
| N-58 | "...differing evaluation times" | Partly fixed | `T/major_check.py:437-440`, `routines.py:345-349`. The read under the lock is unproved, as fixes-majors admits | Minor | Accept |
| N-59 | "...read-back through the loop" | Partly fixed | `T/blocker_check.py:241-266` uses the gateway and `offload_large`, with no model or middleware | Minor | Accept |
| N-60 | "release is a bare DELETE with no audit" | Present | `docs/engineering/runbooks/backup-restore.md:84` | Minor | Accept: owner on their own Mac |
| N-61 | "...or verification" | Present | `backup-restore.md:81-87`. The hold is checked before release (`scripts/local_backup.py:373`) | Minor | Accept |
| N-62 | "Enabled routines catch up at once and can use the restored key" | Present | `routines.py:346-381`. Runbook line 87 mentions only queued jobs | Minor | Fix now: one runbook sentence |
| N-63 | "resume has no `require_ready`" | Present | `run_routes.py:235-265` vs `:78`, `backup-restore.md:79-81` | Minor | Accept: nothing is claimed until release (`A/application/worker_leases.py:73`) |
| N-64 | "`apply_all` has no per-workspace `try`" | Present | `A/application/retention.py:158-165`, `worker.py:216-219` | Minor: only with several workspaces | Fix now: its docstring says otherwise |
| N-65 | "a failed `docker stop` raises with nothing restarted" | Present | `scripts/local_backup.py:205-207` | Minor | Fix now: stop inside the `try` |
| N-66 | "a timeout is uncaught" | Present | `local_backup.py:55, 205, 443-448` | Minor | Fix now, with N-65 |
| N-67 | "a fixed key filename silently overwrites an earlier key copy" | Present | `local_backup.py:199-201` | Minor | Accept: I found no rotation path, and `:366-367` detects a mismatch |
| N-68 | "decrypted configuration is written into the backup directory" | Fixed | `local_backup.py:308-310, 376-378` (in memory), `scripts/supabase_stack.py:112` | None | Close |
| N-69 | "`_beat` catches only `OperationalError`" | Present | `worker.py:76-91` | Minor | Fix now: catch it, log it and go on |
| N-70 | "stop isn't propagated into the step... Not reachable from the shipped entry point" | Present, and **now reachable** | `worker.py:320-323, 266-274, 246-250, 106-122`. The qualifier stops only an idle worker (`scripts/qualify_worker_inference.py:297`) | Major: after SIGTERM a job can still be claimed, with paid calls for up to 30s. A cut call pauses for a person | Fix now: no new claim after stop, and stop at the next boundary |
| N-71 | "unhandled API exceptions likely print unredacted tracebacks" | Present, read and not run | `A/operations/logs.py:65-72` sets the root logger only. uvicorn doesn't propagate (`uvicorn/config.py:110`), and Starlette re-raises (`starlette/middleware/errors.py:183-186`). `docs/engineering/runbooks/operations.md:119` says "An exception logs its type, never its message" | Blocking if a run confirms it: false runbook claim | Fix now: give uvicorn's loggers the JSON handler, and assert it |
| N-72 | "tool and `GRAPH_STATE_VERSION` bumps depend on a person remembering" | Present | `services/agent/tests/test_execution_contract.py:23-29` | Minor | Accept: inherent, and a review matter |
| N-73 | "PRD 10.3's application revision isn't recorded" | Present. I did not re-read the PRD wording | `A/domain/execution.py:34-35` | Minor | Accept: compatibility rests on the recorded versions |

## Table 2: Majors and decisions

| ID | Decision | Status | Evidence | Severity | Recommendation |
|---|---|---|---|---|---|
| M8 | Only an owner can choose an earlier version (0011) | **Half enforced.** The run route is fixed, and the session route bypasses it. See N-new-1 | `run_routes.py:103-108`. No test: `owner_required` has no match under `tests/` or in `qualify_identity` | Major | Fix now |
| M30 | A differing summarizer pauses with `route_not_bound` (0009) | Present as decided, and the code matches. A resume re-pauses before any paid call | `goal_loop.py:98, 513-522`, `loop_middleware.py:295-297`, disclosed at `W/model-policy-panel.tsx:49-54` and `operations.md:52` | Minor | Accept: Decision 0009, to be built later under LC-01 and LC-25 |
| M32 | `to_version` 0 means no active version (0011) | Fixed, and it matches | `A/contracts/improvements.py:84`, `improvements.py:249-263`, `M/28:10`, `T/improvement_check.py:194`. Skill and memory reads exclude it (`improvements.py:299-303`, `memory.py:72`) | None | Accept: Decision 0011 |
| M33 | A reviewer's text checks gate promotion for now (0011) | Behavior matches. The deferral is wrong: see N-new-2 and N-new-5 | `contracts/improvements.py:92`, `improvements.py:100-124`, `T/improvement_check.py:183-189` | Minor as decided | Accept the gate. N-new-2 is separate |
| WI fail | `rate_limited` and `provider_error` fail after retries (0011) | **Confirmed by reading.** They are absent from `PAUSE_FOR`, so `_finish` issues FAIL. See the three limits below | `goal_loop.py:77-100, 674-677`, `A/application/model_attempts.py:33-35, 130-138`. Fake transport only: `T/goal_loop_check.py:158`, qualifier `:280-286` | Minor. The recovery step is N-new-3 | Accept: Decision 0011 |

**Limits on the fail behavior:**
- A `Retry-After` over 60 seconds fails at once.
- A pause landing just before FAIL is refused and relabelled `lease_lost`, so that run stays paused and can be resumed.
- A failed child returns to its parent's model, or fails a workflow node.

## Table 3: WORKER-INFERENCE-001

| ID | Item | Status | Evidence | Severity | Recommendation |
|---|---|---|---|---|---|
| WI-1 | A price rise during a job is under-reserved | Present. Author-recorded, and no decision accepts it | `A/application/worker_inference.py:175` discards the fresh worst case. `:255-257` sets it once per claim | Blocking (MP-07): past the limit by the last call's excess | Fix now: compare the fresh worst case with the reservation, and refuse before sending |
| WI-2 | "Worst case" assumes 32,000 prompt tokens | Present. Worse than recorded: see N-new-4 | `A/adapters/models/catalog.py:13-17`, `worker_inference.py:125` | Blocking: same bound as WI-1. Decision 0009 describes the ledger as holding a call's worst case | Fix now: reserve from an upper bound on the real request |
| WI-3 | Fingerprint and record | Unbound and stale. See the stale claims below | `docs/engineering/work-items/WORKER-INFERENCE-001.md:3-4, 18, 30`, `docs/engineering/evidence/WORKER-INFERENCE-001/summary.md:5-16` | Major: a false record, not false behavior | Fix now under US-11.12#3: rerun on the final tree, bind a manifest and settle the status |
| WI-4 | The third round, never reviewed | Read now, no defect found | Damaged key `A/application/provider_settings.py:148-150`. Retry cap `model_attempts.py:14, 134`. Slot wait `loop_middleware.py:302, 408-423`. Provider stop `:437-438`. Logging `worker_inference.py:73-75` | None | Accept: read only |
| WI-5 | Not exercised through this worker: compaction, a child, two workers, a lost lease, the network pause | Still open. Workflows are now covered (qualifier `:215-218`). **I can't tell from reading whether compaction works over the real SDK** | `summary.md:58`. Also, a summary cut at 512 tokens becomes `compaction_failed` and fails the run (`loop_middleware.py:303-304`, `goal_loop.py:674-677`) | Major | Fix now: add a compaction and a child case to the qualifier over the fake transport |
| WI-6 | Two `mark_invalid` races, and upstream provider recorded as `unknown` | Present, as recorded | `provider_settings.py:243-259`, `run_projection.py:396` | Minor | Accept: they fail closed and say what they don't know |
| WI-7 | Replies missing `system_fingerprint` would pause after being paid | **Can't tell from what I read.** That evidence search found it only in this summary, and I didn't read US-3.4's evidence | `summary.md:58` | Minor | Accept: reservation is kept and a person decides. Check US-3.4's evidence during US-11.12 |

**Stale claims in the WI-3 record:**
- "Uncommitted".
- "Evidence: none".
- Astra, where the code now uses Terra.
- 34 cases, where fixes-majors reports 36.
- 345,600 reserved, where the qualifier now expects 34,560.
- Workflows "not exercised".

**Answer to your question 3:** apart from WI-1 and WI-2, reading found nothing blocking in `worker_inference.py`, `worker.py`, `loop_middleware.py` or the two check scripts. These held in reading:
- Refusals land before sending and are classed correctly.
- Uncertain calls keep their reservation.
- Keys stay per workspace, and an installation key needs its grant (`A/application/credentials/store.py:180`).
- A cancel or candidate settles ahead of a refusal.

N-70 and WI-5 are the next most serious. All of this comes from reading and fake-transport fixtures, not live behavior.

## New findings

| ID | Finding | Evidence | Severity | Recommendation |
|---|---|---|---|---|
| N-new-1 | **A member can still pin an earlier Expert version.** A member creates a session with `version: 1`, then runs with no `expert_version`, so the owner check is skipped and the removed tools return. Decision 0011's "A member can't reach an earlier Expert version" is false | `A/api/expert_routes.py:124-135` (Member), `A/contracts/experts.py:67`, `experts.py:192-194, 263`, `run_routes.py:103-116`. Not reachable through the product today: the only insert I found in the service source is `'owner'` (`A/operations/bootstrap_owner.py:46-47`) | Major | Fix now: refuse a non-null `version` from a non-owner |
| N-new-2 | **M33's "held-out replay stays with US-10.1" points at nothing.** US-10.1 is DONE and says "No product behavior changes". The owner accepted the gate on that premise | `SPECS.md:209`, `openspec/changes/archive/2026-11-06-us-10-1-held-out-task-policy/proposal.md:25`. No promotion terms in `scripts/qualify_release.py` or `docs/engineering/evidence/US-10.1/summary.md` | Major | Later: new post-release story under SP-016. Correct Decision 0011 now and have the owner reconfirm |
| N-new-3 | **The linked new run has no screen.** No web component sets `continues_run_id`, only a browser test posts it, and the runbook doesn't say how. A linked run also gets new operation IDs, so it can repeat earlier effects (behind a new approval if consequential) | `W/` grep, `apps/web/tests/browser/runs.spec.ts:204-212`, `operations.md:64`, `runs.py:195-202`, `tool_gateway.py:164` | Major | Fix now: add a "continue in a new run" action, and state the repeat risk in the runbook |
| N-new-4 | **The system prompt and tool schemas aren't in the compaction count.** Expert instructions plus up to 50 skills of 20,000 characters can far exceed the 32,000-token reservation, and the runbook names only non-Latin text. Needs owner-promoted skills | `loop_middleware.py:270`, `compaction.py:41-50`, `experts.py:278`, `A/contracts/experts.py:19, 21`, `contracts/improvements.py:33` | Blocking, as part of WI-2 | Fix now, with WI-2 |
| N-new-5 | The self-citation check covers only the exact run and its own artifacts. A parent, child or sibling run passes | `improvements.py:100-114` | Minor | Accept: an owner reviews the evidence |
| N-new-6 | `_keep_lease` dies silently on any error but `LeaseLost`, including a failed connect or a database blip. The lease then lapses mid-call, and the settled reply may be paid for again on replay. That second step is reasoned, not traced through the checkpointer | `goal_loop.py:461-480` | Minor | Fix now: reconnect and continue |
| N-new-7 | A malformed reply cost raises outside the handlers, including inside the `except ValueError` branch. The call stays `dispatched`, and its slot is held until lease expiry. Safe direction | `loop_middleware.py:141-143, 364, 394-397` | Minor | Accept |
| N-new-8 | The worker docstring says "no live route is qualified yet (US-3.4)", but US-3.4 is DONE | `worker.py:8-9`, `SPECS.md:133` | Minor | Fix now: wording |
| N-new-9 | `qualify_worker_inference.py` is in no verify profile, so its result goes stale unnoticed | No match in `scripts/verify.py` | Minor | Accept: Docker-heavy. Rerun by hand under US-11.12#2 |

## What I did and didn't inspect

**Read in full:**
- review-r1, fixes-majors, Decisions 0009 and 0011, the WORKER-INFERENCE-001 record and summary, the US-10.1 proposal and spec.
- `A/application`: assignments, goal_loop, worker_inference, tool_gateway, run_projection, experts, reconciliation, approvals, improvements, runs, model_attempts, model_admission, provider_settings, worker_leases, recovery, workflow_runner, workflows, compaction, memory, retention, routines, credentials/store and credentials/precedence.
- `A/domain`: runs, workflows, execution.
- `A/operations`: worker, logs.
- `A/adapters`: loop_middleware, tool_middleware, models/catalog, models/factory, openrouter_metadata.
- `A/api`: run_routes, approval_routes, expert_routes, improvement_routes, workflow_routes, errors.
- `A/contracts`: improvements, experts, workflows.
- Tests and scripts: `T/assignment_check.py`, `T/effect_check.py`, `T/workflow_run_check.py`, `T/product_inference_worker.py`, `scripts/qualify_worker_inference.py`.
- Web: `W/workflow-monitor.tsx`.
- Migrations 16, 18, 19, 28, 33.

**Read in part or by search:**
- `T/major_check.py`, `T/blocker_check.py`, `T/improvement_check.py`, `T/approval_check.py`, `T/goal_loop_check.py`.
- `local_backup.py`, `run-workspace.tsx`, the two runbooks, `SPECS.md`, the PRD and `github_issues.py`.
- uvicorn and Starlette source.
- `.checks/worker-inference/qualification.json`, header fields only: passed at 2026-11-06T13:23Z, fingerprint `dd7322d7…`. **I can't establish that this fingerprint matches the current tree.**

**Not inspected:**
- `plans.py`, `run_usage.py`, `verification.py`, `artifacts.py`, `domain/workflow_execution.py`, and `checkpoints.py` beyond `is_stale_owner`.
- `services/agent/tests/test_worker_inference.py`, `T/product_inference_check.py`, `T/wake_check.py`, `qualify_operations.py`, `qualify_backup.py`.
- Evidence for US-3.4 and for US-11.1 to US-11.11.
- The Supabase overlay.
- The `dce9e19` baseline, which read tools can't reach.

**Not done:** I ran no tests, stack, browser or model, and computed no fingerprint. Every result quoted from a check is supplied evidence, not my observation. Any fix made after this needs its affected review and checks refreshed. Nothing here establishes H1 or product acceptance.

**Key files, absolute:**
- `/Users/josoroma/sites/autobots/services/agent/src/autobots/api/expert_routes.py`
- `/Users/josoroma/sites/autobots/services/agent/src/autobots/application/worker_inference.py`
- `/Users/josoroma/sites/autobots/services/agent/src/autobots/application/run_projection.py`
- `/Users/josoroma/sites/autobots/services/agent/src/autobots/operations/worker.py`
- `/Users/josoroma/sites/autobots/apps/web/components/workflow-monitor.tsx`
- `/Users/josoroma/sites/autobots/docs/engineering/decisions/0011-review-dispositions.md`
- `/Users/josoroma/sites/autobots/docs/engineering/work-items/WORKER-INFERENCE-001.md`
