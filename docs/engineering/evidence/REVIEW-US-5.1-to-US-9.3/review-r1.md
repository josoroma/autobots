# Independent review of US-5.1 to US-9.3, round 1

Target: `delivery/epic-1` at `dce9e19`, the commits after `e99143f`. Five `autobots-reviewer` agents, one per story group, read the code and requirements without the author's conclusions. The coordinating session then re-traced the strongest findings and ran the pure domain functions it could. Nothing was repaired and no story status changed.

**Result: 10 blockers, 33 majors, 41 minors.** No finding has a disposition yet. The user decides what gets fixed.

This is a review record, not completion evidence. It has no `autobots.work-evidence/v1` manifest, and it doesn't establish H1 or product acceptance.

## How far to trust each finding

- **Probe**: the pure domain function ran from a frozen copy of HEAD, and the result was seen.
- **Read**: the coordinating session traced the path itself in that frozen copy.
- **Reviewer**: traced by one reviewer agent only.

Nothing ran against a database, Docker, a worker or a model. Timing windows are reasoned from the code, not observed.

## Read this first

- **No production worker runs this code at HEAD.** `process_next` has no caller under `services/agent/src`, and `operations/worker.py` serves maintenance only. So every runtime finding on goals, assignments, approvals and workflows is reachable only through the fixture workers in `tests/db`. Routines, retention and approval expiry do run in the maintenance worker.
- **A live worker would make these reachable.** While this review ran, another session had uncommitted edits, including a new `application/worker_inference.py` and changes to `goal_loop.py` and `loop_middleware.py`. Those edits aren't reviewed here, and any fix in them needs checking against this list.
- Paths are under `services/agent/src/autobots/` unless they start with another top-level folder. Line numbers are from `dce9e19`, so they may have moved since.

## Severity

A blocker is a false result, a duplicate or unauthorized effect, a state with no way out, or a story scenario that can't be met as written. Under this rule, B2, B7 and B8 were raised from the reviewers' major, in line with the US-4.8 findings on unfenced dispatch, self-attested success and a stuck `cancelling`.

## Blockers

### B1. A reviewer can approve content they never saw (US-5.3, exact proposed action; SP-013)
`api/approval_routes.py:23,53`, `application/run_projection.py:64`, `apps/web/components/approvals-panel.tsx:128-130`. **Read.**
1. A model or a workflow approval step proposes arguments over 4,000 characters, with the consequential part after that point.
2. `public_text(..., limit=4000)` cuts the text with no marker, and the panel shows the cut text as if complete.
3. The reviewer approves. The hash covers the full arguments, and the full payload is dispatched.

The hash proves the approval matches the stored proposal, not what the reviewer read.
Suggested fix: refuse to approve a truncated payload, or show all of it.

### B2. A stale worker can admit an effect, and a late failure can overwrite a success (US-5.4; SP-012)
`application/tool_gateway.py:252-267, 346-353`. **Read** for the unconditional writes. The interleavings aren't exercised, and `tests/db/effect_check.py` has no stale-worker case.
1. W1 passes the ownership check at line 195, then stalls. Mac sleep is a named SP-012 case.
2. W2 claims the job, marks the receipt `started` and sends.
3. W1 wakes. Its insert conflicts, `_replay` sees `started`, and the readback finds nothing yet, so W1 sends too.
4. A destination that doesn't dedupe gets two effects.

Separately, W1's late `ToolFailed` writes `failed` over W2's `succeeded`. The next replay takes the `failed` branch and dispatches again. A late W1 can overwrite an operator verdict the same way.
Latent until a real consequential tool exists (US-7.2).
Suggested fix: admit in one transaction with `hold_lease`, and allow only legal receipt transitions.

### B3. A cancelled parent can strand its child for good (US-5.2; SP-010)
`application/goal_loop.py:473-475`, `application/worker_leases.py:77`. **Read**, except the inference-slot leak, which is **Reviewer** (`application/model_admission.py:9,133`).
1. A worker dies inside a child's model call. Parent and child leases expire at different times.
2. The user cancels, and the child becomes `cancelling`.
3. The parent is claimed first. `claim_run(child)` returns None because the child's lease is still live, so `_settle_children` skips it.
4. The parent reaches `cancelled`. Nothing can reclaim the child, because `claim_next` excludes children and a repeat cancel changes nothing.
5. Its call stays `dispatched` and holds one of the workspace's two inference slots. Two occurrences give the workspace `no_inference_slot` with no recovery route.

`tests/db/assignment_check.py:177` expires both leases together, which hides this.
Suggested fix: wait out the child's lease, and don't send FINISH_CANCEL while a child is unsettled.

### B4. A replay can't read a finished child's result (US-5.2 "Reattach after replay", US-6.2 Restart; PRD 8.3)
`application/assignments.py:148-157, 172-177, 199`. **Read.**
1. The child reaches a terminal state and its job becomes `done`.
2. The parent dies before the assignment is marked `finished` at line 199. A user cancelling a paused child directly reaches the same state with no crash.
3. On replay the assignment is `open`. `_claim` takes only queued jobs or expired claims, so `_claim_child` spins for about 61 seconds and raises `assignment_busy`.
4. The receipt becomes `failed`. In a goal run the model continues, and a reworded goal creates a duplicate child. In a workflow the agent node is permanently `failed` even though the child succeeded.

Suggested fix: if the child is terminal, build the result from it without claiming.

### B5. A settled workflow can stay in `verifying` or `cancelling` forever (US-6.2 Restart)
`application/workflow_runner.py:287-313`, `domain/runs.py:126`. **Probe** for the refusals, **Read** for the rest.
- **Verifying:** a worker dies after `VERIFY` commits and before `COMPLETE`. The next claim sends `VERIFY` from `verifying`, which is refused. `_complete` catches only `LeaseLost`, so the error escapes. This repeats on every lease expiry, because claims have no attempt cap.
- **Cancelling:** a cancel lands after the last commit. `VERIFY` or `FAIL` is refused, and `FINISH_CANCEL` is never reached.

Suggested fix: check run status before finishing, and route refusals to `_finish("run_not_running")`.

### B6. A pause during a node permanently fails it and discards its result (US-6.2 Restart)
`application/workflow_runner.py:75, 133-136, 231-233`, `application/tool_gateway.py:334-336`. **Read.**
1. A user pauses while an artifact upload is running.
2. The receipt is recorded `succeeded`, then the gateway returns `DENIED run_not_running`.
3. `run_not_running` isn't in `STOPS`, so `_tool` raises `BlockFailed` and the instance commits as `failed`.
4. On resume the instance is terminal and never retried. Downstream nodes block, and the run ends `failed`.

Suggested fix: add `run_not_running` and `run_not_found` to `STOPS`.

### B7. A stalled workflow reports success, and joins silently drop data (US-6.2; LC-14)
`domain/workflow_execution.py:176-191`, `application/workflow_runner.py:279, 289-292`, `domain/workflows.py:117-147`. **Probe** for validation and `next_steps`, **Read** for the runner treating an empty result as finished.
- The validator returned no errors for two foreach regions feeding one join.
- **Lists of 3 and 1:** `next_steps` returned nothing, with the join and output never run. The runner treats that as finished, so the run would be `succeeded`.
- **Lists of 1 and 3:** the join ran and emitted `['1', 'x']`. Items `y` and `z` were dropped.

Suggested fix: reject the shape at publication, and fail the run when nothing can move but instances remain unsettled.

### B8. An incompatible run being cancelled never settles (US-9.3 "blocked honestly")
`application/goal_loop.py:312-315, 494, 517-518, 546`, `domain/runs.py:126`, `tests/db/upgrade_check.py:102`. **Probe** for the refusal, **Read** for the rest.
1. A worker dies on the old release with unsettled work.
2. After a version bump, `_drive` returns INCOMPATIBLE before `classify_interrupted` runs, so the call never becomes `uncertain`. The run pauses.
3. The owner cancels, as the runbook says, and the run becomes `cancelling`.
4. `_drive` issues SUSPEND, which is refused and recoded `lease_lost`. This repeats on every lease expiry.

The check accepts `cancelling`, which hides this.
Suggested fix: in `_drive`, when the status is `cancelling`, call `_finish(..., "run_not_running")`.

### B9. Stored evidence can't be read back (US-8.1, "citations point to retrievable original evidence")
`application/compaction.py:56-63`, `application/memory.py:98-110`. **Read.**
1. A 10K-character tool result becomes a pointer and a preview.
2. The model calls `read_offload`, whose result is also over 4,000 characters and has no exemption or paging.
3. It is offloaded again as a new row, with another pointer.

Nothing over about 4,000 characters ever reaches the model, and each retry costs a call. The US-8.1 `verification.md:16` admits read-back wasn't tested. It fails safe, but the scenario's Then isn't met.
Suggested fix: exempt `read_offload` and add paged reads.

### B10. No product path creates an improvement candidate (US-8.2 "Promote only reviewed evidence")
`domain/tools.py:16-24`, `application/experts.py:32`, `api/improvement_routes.py`, `tests/db/improvement_check.py:153`. **Read.**
`propose_improvement` is in neither `PLAN_TOOLS` nor `EXPERT_TOOLS`, `validate_config` refuses any Expert naming it, and the routes only list, run regression, decide and roll back. The test injects the grant by hand. Its verification record says a scripted model called the tool, without saying the grant was injected.
Suggested fix: add a deliberate way to grant or submit proposals.

## Majors

### Approvals, effects and assignments

| # | Story | Where | Failure | Basis |
|---|---|---|---|---|
| M1 | US-5.4, SP-010 | `application/tool_gateway.py:268-274, 291-295` | A run resumes on an `unknown` receipt and the user cancels. The readback raises `NotDelivered`, and `_attempt` dispatches with no ownership check since line 195. The readback also has no timeout, so a hung one renews the lease indefinitely and the run stays `cancelling` | Read |
| M2 | US-5.3, PRD 9.2, LC-10 | `application/approvals.py:124-125` | An `approved` request is never checked for expiry. A paused run dispatches weeks after `expires_at`. An approval is never consumed, so each confirmed failure allows another send under the same decision | Read |
| M3 | US-5.3, US-5.4 | `application/goal_loop.py:88, 551`, `application/assignments.py:178-204`, `application/worker_leases.py:77` | A child's `approval_pending` returns outcome `waiting`, and only `lost` and `paused` raise, so the assignment is `finished` and the parent continues. Nothing drives the child afterward, so the approved effect never runs and the root can succeed. Latent until an Expert can hold a consequential tool. The author's record predicts different behavior | Read |
| M4 | US-5.2, SP-010 | `application/recovery.py:50`, `application/verification.py:43-47`, `api/run_routes.py:246` | `outstanding()` counts model calls across the tree but tool effects for one run only. The parent shows 0 unknown effects, cancels as clean `cancelled`, and can reach `succeeded` over a child's unreconciled effect. Resuming the parent also skips the gate a direct resume of the child would face | Read for the count, Reviewer for the path to success |
| M5 | US-5.2, SP-012 | `adapters/loop_middleware.py:161-166` | `_guard` checks only the direct parent. Pausing the root leaves a grandchild making paid calls, because its parent is blocked in a tool call and still `running` | Read |
| M6 | US-5.2, SP-012 | `adapters/loop_middleware.py:53-61`, `application/assignments.py:157` | A child keeps running under a parent whose lease moved. The new owner gets `assignment_busy`, which isn't a stop code, so the model can delegate a reworded goal and two children run. Needs more than one worker | Reviewer |
| M7 | US-5.1 "Route within granted scope" | `application/goal_loop.py:170, 191-193`, `application/assignments.py:228`, `application/experts.py:278` | The prompt and tool description never name the routable Experts, and `expert_id` is required. A live model has no valid value unless a user pastes one. A child isn't told its `outputs/child-N` namespace either. Scripted tests inject both | Read |
| M8 | US-5.1 | `application/experts.py:263`, `api/run_routes.py:107-109` | A member passes `expert_version: 1` on a session pinned to v2 and regains tools the owner removed. Whether earlier revisions may be chosen is an open source question | Reviewer |

### Retention

| # | Story | Where | Failure | Basis |
|---|---|---|---|---|
| M9 | US-9.1 | `api/app.py:33-36`, `api/operation_routes.py:131-134`, `application/retention.py:58,69` | The API pool isn't autocommit, so `store.remove` runs before the purge commits, contrary to the docstring. A crash rolls back: artifacts return to `published` with their bytes gone. Run row locks are also held across Storage calls. Tests use autocommit, so they miss this | Read |
| M10 | US-9.1, SP-014 | `supabase/migrations/20261105000023_operations.sql:17, 119-123`, `contracts/operations.py:38-46` | Keys expire by `created_at`, runs by `updated_at`. With 30-day windows, a run admitted on day 0 and finished on day 25 loses its key on day 30 and keeps content to day 55, so a retry creates a new paid run. `run_days=null, receipt_days=1` passes both checks. Expiry also ignores `unknown` receipts and uncertain calls | Read |
| M11 | US-9.1 | `application/runs.py:407-413`, `supabase/migrations/20261105000023_operations.sql:84`, `application/retention.py:89-94` | CANCEL withdraws approvals but never closes obligations, so a run cancelled while waiting is refused `open_obligation` forever, though the runbook says it retries. Refused runs stay at the head of `order by updated_at limit 100`, so 100 of them stop purges for that workspace | Read |

### Restore, readiness and upgrades

| # | Story | Where | Failure | Basis |
|---|---|---|---|---|
| M12 | US-9.2 "Avoid accidental resumed charges" | `scripts/local_backup.py:324-333`, `operations/worker.py:119-143` | `up -d --wait` publishes the database for up to 240 seconds before the hold is written, despite the comment "Before anything else can connect". A process pointed at that port could reconnect, fire routines, expire approvals and run retention. If `up` fails, the stack stays up with no hold at all | Read for the order, harm needs a process pointed at that port |
| M13 | US-9.2, LM-07 | `scripts/local_backup.py:280-334`, `scripts/qualify_backup.py:43-52`, `tests/db/restore_check.py:59,90` | A real restore can't be verified. `backup` and `restore` don't verify, and the qualifier builds its own disposable source with fixture assertions. The manifest's `users` and `credentials` facts are never compared, and runs and events by count only | Reviewer |
| M14 | US-9.1 | `operations/worker.py:172-180`, `application/routines.py:276, 311-367` | The maintenance step checks only the hold. With storage down, disk low or `adapter_unqualified`, due routines still create runs and jobs, contrary to `require_ready`'s docstring | Read |
| M15 | US-9.3 | `adapters/checkpoints.py:21-38`, `tests/db/upgrade_check.py:147` | The identity hashes only `langgraph-checkpoint-postgres`. Upgrading `langgraph-checkpoint`, `langgraph` or `deepagents` keeps `adapter_qualified` true. "Qualified" is a hand-written row with no replay evidence behind it | Read for the code, Reviewer for the lock pins |
| M16 | US-9.3, PRD 10.3 | `application/runs.py:136-145`, `application/goal_loop.py:431-438`, `domain/models.py:38` | The snapshot stores role to profile only. A release changing a profile's `wire_id` sends saved runs to a different model with no block | Reviewer |

### Workflows

| # | Story | Where | Failure | Basis |
|---|---|---|---|---|
| M17 | US-6.2, US-6.3 | `operations/worker.py:4-6, 225` | No production code runs a workflow. An execution stays `queued`. Disclosed by the author, but acceptance rests entirely on fixture workers | Read |
| M18 | US-6.1, US-6.2 | `domain/workflows.py:29-33, 44, 57-58` | Approval, condition and transform output `json`, and `read.path`, `artifact.content` and `agent.goal` require `string`. Approval-to-artifact and `to_string`-to-artifact both returned `link_type_mismatch`. An approval step can't guard any effect in a valid graph | Probe |
| M19 | US-6.2, PRD 7.3 | `application/tool_gateway.py:134-136`, `application/workflow_runner.py:196-202` | The operation identity has no instance key. A foreach over `["x","x"]` feeding an agent replays the first child's result as the second's, and no second assignment exists | Read |
| M20 | US-6.1, MP-01 | `api/workflow_routes.py:205-214`, `application/workflows.py:227`, `application/routines.py:258` | No caller passes `policy`, so executions fall to the default profile. A workspace that chose another profile has its agent steps frozen on the wrong binding | Read |
| M21 | US-6.3 Inspect | `application/workflows.py:312-319`, `apps/web/components/workflow-monitor.tsx:12` | `running` is never written, and an absent row shows "Waiting for its inputs". That covers a node mid-effect, an approval awaiting decision, a suspended `outcome_unknown` node, and unexecuted nodes on a cancelled run | Reviewer |

### Routines

| # | Story | Where | Failure | Basis |
|---|---|---|---|---|
| M22 | US-7.1, PRD 10.4 | `application/routines.py:259-268`, `application/workflows.py:226-234` | A workflow routine with `limit_micro_usd=500, tools=["calculate"]` validates, but its run gets a hard-coded $1 limit and every workflow tool grant | Read |
| M23 | US-7.1 | `domain/routines.py:49,57`, `application/routines.py:340-349` | After 20 hours away, a 1-minute routine found 1,000 occurrences with the latest 3h20m stale, while `evaluated_until` jumps to now. About 200 occurrences are never recorded, and the admitted one isn't the true latest | Probe |
| M24 | US-7.1 | `application/routines.py:320, 341-344` | `moment_now` is read once per pass and written with no `greatest`, so a slower worker moves `evaluated_until` backward. A `blocked` or `skipped_overlap` occurrence is then re-evaluated and admits a run while its history stays wrong, with `run_id` null, so `_has_active_run` can't see it. If the routine was edited in between, an uncaught `IdempotencyConflict` repeats and leads to M25 | Read |
| M25 | US-7.1 | `domain/routines.py:24, 47-48`, `application/routines.py:340`, `operations/worker.py:180-184` | `minutes=10**10` passed validation, then `occurrences` raised `OverflowError` outside any `try`. The whole pass aborts and retries about every 2 seconds. Later routines never evaluate and retention never runs | Probe for the raise, Read for the rest |

### Memory and improvement

| # | Story | Where | Failure | Basis |
|---|---|---|---|---|
| M26 | US-8.1, SP-016 | `adapters/loop_middleware.py:349` vs `354-363`, `327-336`, `application/goal_loop.py:269-271` | `_compacted` runs outside the admission handlers. With the budget exhausted, the refusal escapes `run_goal`, and the `budget_exceeded` suspension never happens. It repeats on each lease expiry with no cap | Read |
| M27 | US-8.1, PRD 8.4 | `application/memory.py:71, 94`, `supabase/migrations/20261105000021_memory.sql:2-11` | `_search_tool` passes no `run_id`, so any run's search returns snippets from every run's files in the workspace, across sessions and Experts and past narrowed `allowed_paths`. `memory_items` has no owner or Expert column, though the PRD requires them. Another workspace is correctly excluded | Read |
| M28 | US-8.1 | `application/compaction.py:61, 160, 186` | A 3,000-character result is cut to 2,000 for the summary, with no offload row or citation. The remainder leaves the model's view with no pointer back | Reviewer |
| M29 | US-8.1 | `application/goal_loop.py:167-188`, `deepagents/middleware/summarization.py:310` | Likely, not fully traced. The SDK's summarizer stays installed. At about 170K tokens it calls `AdmittedModel` outside dispatch, which raises `UnadmittedModelCall` and fails the run during the long work this story exists for | Reviewer |
| M30 | US-8.1 | `application/goal_loop.py:426-427`, `adapters/loop_middleware.py:240-241` | An Expert with different main and summarizer profiles suspends with `route_not_bound` at first compaction, and no single-route worker can finish it. Disclosed by the author | Reviewer |
| M31 | US-8.1, PRD 8.5 | `application/compaction.py:157-160, 202`, `adapters/loop_middleware.py:220, 226, 244` | Tool and retrieved text goes undelimited into a summary request, and the summary is replayed as a `HumanMessage`. An injected instruction moves from tool role to user role. Tool grants still hold | Reviewer, Read for the `HumanMessage` |
| M32 | US-8.2 | `application/improvements.py:203-217`, `contracts/improvements.py:83` | A bad first promotion can't be undone. The only rollback target for v1 is v1 | Reviewer |
| M33 | US-8.2, SP-016 | `application/improvements.py:95-99` | Regression certifies itself: each case checks a proposer-written `must_contain` against the proposer's content, and a run can cite itself as evidence. The author defers held-out replay to US-10.1, but the Gherkin gates promotion on regression now | Reviewer |

## Minors

All are **Reviewer** unless marked.

### US-5.1 and US-5.2

- `application/assignments.py:199`, `application/goal_loop.py:479`: assignment writes are unfenced, and `_settle_children` records `cancelled` even for a child that succeeded.
- `application/assignments.py:92`: a cancel between the gateway check and `hold_lease` orphans a new child beside a `cancelled` parent.
- `application/assignments.py:47, 54-55`: `tools=["calculate"]` still grants delegation, and versions come from the Expert's offer, not the parent's frozen grant.
- `application/assignments.py:105-106`: a grandchild's path isn't under its parent's grant, and the `inputs` grant is empty in practice.
- `application/run_projection.py:53-57, 182-196`: a child shows the Expert's own bindings, and its spend shows 0.
- `application/experts.py:192-195`: a session-create retry after a new revision returns 409.
- `api/run_routes.py:102`: `expert_id` without a session is ignored silently.
- Tests: `tests/db/assignment_check.py:61, 108, 147-152, 167` assert less than they claim, and nothing covers a child hitting `budget_exceeded` or the time limit.

### US-5.3 and US-5.4

- `application/tool_gateway.py:329-331`: `output_too_large` records `unknown` but doesn't stop the loop. Verification later fails the run.
- `application/goal_loop.py:517-518, 546`: during a cancel or pause, `outcome_unknown` is refused and relabelled `lease_lost`, losing the reason.
- `application/reconciliation.py:70-86`, `application/tool_gateway.py:273`: a verdict binds to the operation, not the attempt, so one based on attempt 1 can resolve attempt 2.
- `application/approvals.py:84-88, 188-191`, `application/runs.py:377-390, 408-412`: opposite lock orders can deadlock. State stays consistent, but the routes don't handle the error.
- `application/goal_loop.py:269-271`, `operations/worker.py:129`: `CommandRefused` and `LeaseLost` escape the pass, and settlement waits for lease expiry.
- `supabase/migrations/20261105000016_approvals.sql`: no requester, resource target, scope snapshot or policy version (PRD 9.2), and no human-readable diff.
- `application/tool_gateway.py:299`: the readback path ignores `too_large` and writes no event.
- Tests: no stale worker, cancel during dispatch or readback, or decision racing a cancel. `tests/db/effect_check.py:130` uses a random UUID as "another run".

### US-6.1 to US-6.3

- `domain/workflows.py:71-84`, `application/workflows.py:171, 181`, `api/workflow_routes.py:215`: bad config values give untyped 500s, and another workspace's Expert returns `internal_error` after the version is published.
- `contracts/workflows.py:19, 153`: `config` and `inputs` have no size limit. Likely; the BFF wasn't checked.
- `supabase/migrations/20261105000019_workflow_execution.sql:28`: `authenticated` can read raw emissions, bypassing `read_execution`'s redaction, if PostgREST is reachable. Unconfirmed.
- Workflow versions are immutable by grant only. `run_workflow` doesn't recheck `graph_hash`, and `workflow_executions.run_id` is nullable.
- `apps/web/components/workflow-monitor.tsx:41`: a parse failure stops polling while the page says "Live".
- `domain/workflows.py:201-209`: no reachability check.
- Tests: `tests/db/workflow_run_check.py:150-157` never exercises `_commit`'s fence, and `:191-196` cancels a queued run with no worker. No kill during an effect, and no agent restart.

### US-7.1, US-8.1 and US-8.2

- `adapters/loop_middleware.py:251-260`: `store_summary` and `offload_large` have no fence. No harm established.
- `application/routines.py:270-293`: model policy and skill text are read at each occurrence, so a changed workspace default reaches unattended runs. Whether that breaks "frozen configuration" is open.
- `contracts/improvements.py:17`, `application/improvements.py:67-70`: a 36-character non-UUID evidence ID likely gives a 500 and strands the candidate.
- `application/improvements.py:172-180`: concurrent promotions collide and return a 500. Fails safe.
- `api/improvement_routes.py:90-93`: rollback records no actor, and promoted memory's `created_by` is the workspace ID.
- `application/improvements.py:206`: "admitted work keeps its own" is untrue for memory. Skills are pinned.
- `AUTHORITY_CLAIMS` is bypassed by rewording or a newline. Disclosed by the author.
- Tests: nothing covers workflow budgets, the 1,000 cap, differing evaluation times, or read-back through the loop.

### US-9.1 to US-9.3

- `docs/engineering/runbooks/backup-restore.md:71-77`: release is a bare DELETE with no audit or verification. Enabled routines catch up at once and can use the restored key.
- `api/run_routes.py:228-258`: resume has no `require_ready`, so under a hold it moves paused to queued, contrary to "stay exactly as they were". Nothing runs until release.
- `application/retention.py:130-137`, `operations/worker.py:183`: `apply_all` has no per-workspace `try`, despite its docstring, and one failure skips the rest for an hour. **Read.**
- `scripts/local_backup.py:178-200`: a failed `docker stop` raises with nothing restarted, and a timeout is uncaught.
- `scripts/local_backup.py:192-193`: a fixed key filename silently overwrites an earlier key copy, so older backups can lose their matching key.
- `scripts/local_backup.py:293-300`: decrypted configuration is written into the backup directory, and `kill -9` leaves plaintext secrets there.
- `operations/worker.py:75`: `_beat` catches only `OperationalError`, so another error kills the beat while the worker runs on, and backup's live-worker check then passes.
- `operations/worker.py:92-104`: stop isn't propagated into the step, so a loop can start a paid call during drain. Not reachable from the shipped entry point.
- `configure_logging` leaves uvicorn's loggers alone, so unhandled API exceptions likely print unredacted tracebacks. Likely, not run.
- `services/agent/tests/test_execution_contract.py:17-23`: tool and `GRAPH_STATE_VERSION` bumps depend on a person remembering, and PRD 10.3's application revision isn't recorded.

## Invariants that held

These held in reading only, within each reviewer's scope.

- **Approval binding:** the hash and operation ID come from the same parsed object the handler receives. Changed arguments, tool version or run need a new approval, and another run's approval can't match. Pending, rejected, expired and withdrawn requests never release an effect.
- **Durable wait:** the proposal, event, obligation and wait commit together under the generation fence, and the job is released during the wait.
- **Effects, single owner:** the receipt commits before dispatch, a crash leaves `started`, which is classified `unknown`, and a tool with no readback isn't resent while `unknown`. The operation ID is stable and covers argument values.
- **Workspace isolation:** no cross-workspace path was found. Routes and queries filter on workspace, members get read-only RLS, and `app_private` is ungranted to `authenticated`. See M27 for scope within a workspace.
- **Workflow writes:** `_commit` holds the lease in the same transaction as emissions and instance status, so a stale worker can't commit a node result.
- **Terminal runs** can't resume, and a normal cancel cascades in one transaction.
- **Retention refusals:** each runs inside `purge_run_content`, in one transaction under the run lock, `SECURITY DEFINER` with an empty `search_path`. A nonterminal run or tree, an unresolved receipt on that run, and an open obligation are all refused. Tool receipts and model invocations are never deleted.
- **Restore hold:** checked in `_claim`, `process_next`, the maintenance step and the admission routes, and the runtime role has SELECT only. It is enforced in Python, not SQL, and is absent from heartbeat and dispatch.
- **Backup:** a cold copy of every named volume, with authenticated encryption. Refusals come before anything stops, and the target must be new, disposable-prefixed and not the source.
- **Routine dedupe:** `(routine_id, occurrence_time)` and receipts prevent a second run for an already admitted occurrence, and claim and run creation share a transaction.
- **Promotion:** `decide` requires `regression_passed` and an owner, no model tool can decide, and nothing writes to Expert configuration or model policy.

## Limits

- The only execution was the domain probes, from a frozen copy of `dce9e19`. Nothing ran against a database, a worker or a model.
- The EPIC-6 reviewer finished before the other session's edits were noticed, so it did no re-check against HEAD. The coordinating session re-read its main findings in the frozen copy, but not M21 or the EPIC-6 minors.
- `apps/web`, runbooks, `uv.lock` and `test_execution_contract.py` weren't in the frozen copy and were read from the working tree, apart from the approvals panel, which was read from `dce9e19`.
- `operations_check.py`, `operations-panel.tsx`, `qualify_operations.py` and `qualify_upgrade.py` were only searched. `test_operations.py`, `operations_worker.py` and the US-9.1 and US-9.3 `verification.md` weren't read.
- This round covers `dce9e19` only. Any later fix needs its own check against this list.
