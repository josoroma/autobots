# Python: run lifecycle and model spend

The run lifecycle stands on sound durable mechanics. A pure, unit-tested transition table (domain/runs.py) is enforced by apply_command under job-then-run row locks. Claims and heartbeats use database time and a rising generation, and idempotency receipts are serialized by advisory locks. Completion is decided from recorded evidence, and an integer micro-dollar ledger reserves before dispatch and keeps uncertain attempts open. Comments explain why and cite their decisions. The cost sits in two hubs. goal_loop.py (782 lines) combines tool assembly, prompts, dispatch, lease keeping and settlement, and workflow_runner plus ten test files reach its private names, with function-local imports to dodge a cycle. Its _finish decides the fate of every pass by membership in string sets: it fails any code PAUSE_FOR lacks, and it reads the run status three times. In runs.py, admit_run (15 parameters, with a binding typed Any that four shapes satisfy) and apply_command (11 parameters, positional job tuple) carry admission and transition plumbing. Job-row writes, version reads and system commands issued as Actor.USER are spread over six modules beside the command table. Types stop at the database edge: 73 connection: Any parameters, positional rows, and an untyped policy snapshot read seven ways. State vocabularies are restated as literals, and run_projection.py (664 lines) also hosts a display redaction weaker than the log redaction. I read the metric leads on validate_proposal, verify_candidate and ModelAdmission.admit and judged them acceptable, since they are flat guard sequences or one atomic reservation. Priorities, in order: a typed stop-code table with a pure _finish decision; one shared redaction; parameter objects for admission and worker commands that keep lock order, fencing and receipt fingerprints; and a split of goal_loop along its seams. [Back to the review](../README.md)

Area `py-run`, revision `156534da0bd5b19417f05d313077d767804b175b`, run `2026-11-12-09-52-30`. Every finding below was re-opened at its cited lines and recounted by an adversarial verifier.

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Project ruff and mypy strict pass, but no complexity or positional-argument gate exists, and Any at the database edge stops strict typing from catching errors. |
| modules | 2 | Other modules use goal_loop.py's private names through cyclic local imports, run_projection.py hosts redaction that 7 modules use, and the API imports the worker loop. |
| size | 2 | Two files exceed 650 lines. admit_run has 124 lines and 15 parameters; plan_tools has 121 lines, apply_command 97, run_goal 90, read_inspector 89 and _finish 86. |
| functions | 3 | Many small pure helpers (worst_case_cost, classify_status, validate_proposal, WakeClock), but admit_run, apply_command, run_goal and _finish mix decisions with I/O. |
| structure | 3 | The layout follows DH-03, but run and job state are written from four modules beside the command table rather than through it. |
| approach | 4 | Database-time leases, database-enforced fencing, receipts and a reserve-first ledger set the example; the gaps are unbounded re-claims, an unawaited keeper task and views without a consistent snapshot. |
| comments | 4 | Comments consistently explain why and cite decisions and stories; run_goal and _finish lack contract docstrings, and one module docstring is wrong. |
| types | 2 | 73 connection: Any parameters, positional rows, an untyped policy snapshot and a binding typed Any that SimpleNamespace satisfies; enums exist but stop at the edges. |
| errors | 2 | Stop codes are strings that fail by default, ledger conflicts raise plain ValueError, and a crashing pass is re-claimed forever; cancellation itself propagates correctly. |
| tests | 3 | The pure parts have unit tests named for behaviors and tests/db covers behavior broadly, but settlement and transition rules have no unit seam and tests depend on private names. |
| maintainability | 3 | Correct where it matters most, but slow to change: hub functions, string vocabularies and untyped rows make each lifecycle edit a multi-file change that only the db profile can prove. |

## Strengths

- **One canonical transition table, enforced where the change is written.** [services/agent/src/autobots/domain/runs.py:24-125](../../../../services/agent/src/autobots/domain/runs.py#L24) defines NORMAL_EXITS, COMMANDS, COMMAND_SOURCES and next_status. apply_command ([services/agent/src/autobots/application/runs.py:404-447](../../../../services/agent/src/autobots/application/runs.py#L404)) evaluates them under the job and run row locks, with the expected version. record_transition ([services/agent/src/autobots/application/runs.py:315-325](../../../../services/agent/src/autobots/application/runs.py#L315)) writes status, version and event together. Unit tests cover them in [services/agent/tests/test_contracts.py:103-159](../../../../services/agent/tests/test_contracts.py#L103).
- **Ownership by database time and a rising generation.** [services/agent/src/autobots/application/worker_leases.py:76-104](../../../../services/agent/src/autobots/application/worker_leases.py#L76) claims with 'for update of j skip locked', increments the generation and sets the expiry from clock_timestamp(). heartbeat (worker_leases.py:142-154) extends only a live lease, and revive_lease (worker_leases.py:123-139) fails once anyone else has claimed the job. [services/agent/src/autobots/application/runs.py:381-387](../../../../services/agent/src/autobots/application/runs.py#L381) checks ownership under the job row lock in the writing transaction. [services/agent/src/autobots/adapters/checkpoints.py:59-75](../../../../services/agent/src/autobots/adapters/checkpoints.py#L59) makes the database refuse stale checkpoint writes.
- **A conservative integer ledger that reserves before dispatch.** [services/agent/src/autobots/application/model_admission.py:60-70](../../../../services/agent/src/autobots/application/model_admission.py#L60) rounds the worst-case cost up, in micro-dollars. admit (model_admission.py:105-186) serializes each workspace on an advisory lock and checks slots, run and day budgets before inserting the reservation. Only fail_before_acceptance releases money (model_admission.py:242-248); mark_uncertain keeps it (model_admission.py:250-259).
- **Idempotent commands with serialized receipts.** [services/agent/src/autobots/application/runs.py:74-133](../../../../services/agent/src/autobots/application/runs.py#L74): request_hash normalizes content, and existing_receipt takes a transaction advisory lock on the exact key, so concurrent duplicates wait and replay, while different content raises IdempotencyConflict. Comments explain fingerprint compatibility with older receipts ([services/agent/src/autobots/application/runs.py:210-216](../../../../services/agent/src/autobots/application/runs.py#L210)).
- **Retry policy and sleep detection as small units with injected time.** [services/agent/src/autobots/application/model_attempts.py:55-71](../../../../services/agent/src/autobots/application/model_attempts.py#L55) classifies HTTP statuses in one table. call_with_policy (model_attempts.py:108-155) bounds retries by count, wait cap and root deadline, never retries an uncertain outcome and never invents a charge. [services/agent/tests/test_model_attempts.py:105-216](../../../../services/agent/tests/test_model_attempts.py#L105) states each rule as a test named for its behavior. WakeClock ([services/agent/src/autobots/application/worker_leases.py:19-47](../../../../services/agent/src/autobots/application/worker_leases.py#L19)) takes injected clocks and is tested in test_wake_clock.py.
- **Completion decided from records, not from model claims.** plan_view ([services/agent/src/autobots/application/plans.py:138-151](../../../../services/agent/src/autobots/application/plans.py#L138)) decides completion from recorded evidence. verify_candidate ([services/agent/src/autobots/application/verification.py:35-77](../../../../services/agent/src/autobots/application/verification.py#L35)) reads artifacts back from storage and writes no verdict. [services/agent/src/autobots/application/goal_loop.py:462-481](../../../../services/agent/src/autobots/application/goal_loop.py#L462) commits the verdict with the transition, so a worker that lost the run records nothing.
- **Public projection through the contract.** project_event ([services/agent/src/autobots/application/run_projection.py:93-108](../../../../services/agent/src/autobots/application/run_projection.py#L93)) validates each stored payload against the RunEvent contract and drops what doesn't fit while the cursor advances. read_inspector ([services/agent/src/autobots/application/run_projection.py:576-664](../../../../services/agent/src/autobots/application/run_projection.py#L576)) reads typed columns only, never tool arguments or partial model output.
- **Comments that explain why and cite their source.** [services/agent/src/autobots/application/goal_loop.py:269-270](../../../../services/agent/src/autobots/application/goal_loop.py#L269) (Decision 0023 on citing criteria by ID), [services/agent/src/autobots/application/run_usage.py:77-87](../../../../services/agent/src/autobots/application/run_usage.py#L77) (the clock behavior observed in US-12.5), [services/agent/src/autobots/application/compaction.py:1-6](../../../../services/agent/src/autobots/application/compaction.py#L1) (what compaction may never lose), [services/agent/src/autobots/application/recovery.py:18-20](../../../../services/agent/src/autobots/application/recovery.py#L18), [services/agent/src/autobots/application/worker_inference.py:1-5](../../../../services/agent/src/autobots/application/worker_inference.py#L1).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [PRUN-01](#prun-01) | high | modules | goal_loop.py is a seven-concern hub that other modules use through private names | M | medium |
| [PRUN-02](#prun-02) | high | errors | Stop codes are bare strings, and any code missing from PAUSE_FOR fails the run permanently | M | medium |
| [PRUN-03](#prun-03) | high | functions | _finish mixes the stop decision with cancellation settlement and raw job writes, and reads the status three times | M | high |
| [PRUN-04](#prun-04) | high | functions | admit_run takes 15 parameters and a binding typed Any that four different shapes satisfy | M | high |
| [PRUN-05](#prun-05) | high | duplication | Display redaction keeps its own three-pattern regex, weaker than the log redaction | S | medium |
| [PRUN-06](#prun-06) | medium | functions | apply_command packs replay, ownership, guard, cancel cascade and job rules into one 97-line transaction | M | high |
| [PRUN-07](#prun-07) | medium | structure | Run and job state are written from four modules, beside the command table rather than through it | M | high |
| [PRUN-08](#prun-08) | medium | types | The frozen policy snapshot is an untyped dict, written once and parsed ad hoc in seven places | M | medium |
| [PRUN-09](#prun-09) | medium | duplication | The invocation ledger's states, failure classes and spend formula are restated as literals in five modules | M | high |
| [PRUN-10](#prun-10) | medium | duplication | Run-status sets are restated as literals instead of derived from RunStatus and TERMINAL | S | low |
| [PRUN-11](#prun-11) | medium | approach | Run views read one run with 7 to 19 statements and no common snapshot | S | low |
| [PRUN-12](#prun-12) | medium | types | The database boundary is untyped: connection Any, positional rows and a bypassed RunRow | L | medium |
| [PRUN-13](#prun-13) | medium | errors | Ledger conflicts and missing rows are signalled with built-in exceptions that callers catch broadly | S | medium |
| [PRUN-14](#prun-14) | medium | errors | An unclassified exception leaves the job claimed for endless re-claims, and nothing reads attempts | S | high |
| [PRUN-15](#prun-15) | medium | approach | The lease keeper is started and stopped by hand in three places, and its cancelled task is never awaited | S | medium |
| [PRUN-16](#prun-16) | medium | size | run_projection.py holds five read models, the cursor codec and the shared redaction in 664 lines | M | low |
| [PRUN-17](#prun-17) | medium | tests | Settlement and transition decisions have no unit seam, so tests reach for private names and global patches | M | low |
| [PRUN-18](#prun-18) | low | functions | Long positional signatures invite swapped arguments, and two constructors hand-copy every field | S | low |
| [PRUN-19](#prun-19) | low | functions | plan_tools is a 121-line factory whose handlers can't be tested alone | S | low |
| [PRUN-20](#prun-20) | low | approach | Active-time segments are written without the fence that discount_sleep uses | S | medium |
| [PRUN-21](#prun-21) | low | comments | The central decision points have no contract docstring, and one module docstring is wrong | S | low |
| [PRUN-22](#prun-22) | low | naming | Names that hide meaning: profiles.py, two spellings of one credential code, and generation + 1 | S | low |

### <a id="prun-01"></a>PRUN-01: goal_loop.py is a seven-concern hub that other modules use through private names

- **Severity** high · **Dimension** modules · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/goal_loop.py:162-197](../../../../services/agent/src/autobots/application/goal_loop.py#L162): loop_registry: tool assembly, also used by tool_catalog.py and workflow_runner.py
  - [services/agent/src/autobots/application/goal_loop.py:250-288](../../../../services/agent/src/autobots/application/goal_loop.py#L250): _scope_guidance and _opening: prompt text plus an experts query
  - [services/agent/src/autobots/application/goal_loop.py:417-441](../../../../services/agent/src/autobots/application/goal_loop.py#L417): _drive: job dispatch; imports workflow_runner inside the function (line 434) to avoid a cycle
  - [services/agent/src/autobots/application/goal_loop.py:491-547](../../../../services/agent/src/autobots/application/goal_loop.py#L491): _keep_lease: lease keeping, imported by workflow_runner.py and tests/db/wake_check.py
  - [services/agent/src/autobots/application/goal_loop.py:697-782](../../../../services/agent/src/autobots/application/goal_loop.py#L697): _finish: settlement, called 8 times here and 6 times from workflow_runner.py
  - [services/agent/src/autobots/application/workflow_runner.py:16-24](../../../../services/agent/src/autobots/application/workflow_runner.py#L16): imports _finish, _keep_lease, _result and _run_status; imports _drive inside a function at line 299
  - [services/agent/src/autobots/application/tool_catalog.py:13](../../../../services/agent/src/autobots/application/tool_catalog.py#L13): the tool catalog imports the worker loop for loop_registry
  - [services/agent/src/autobots/api/run_routes.py:14](../../../../services/agent/src/autobots/api/run_routes.py#L14): the API imports the worker loop module for the 7-line execution_block query
- **Evidence:** 782 lines and 22 top-level definitions (19 functions, 3 classes): tool registry (162-197), graph construction (208-247), prompts and an experts query (250-288), the pass (291-380), job dispatch (383-441), candidate settlement (444-488), lease keeping (491-547) and run settlement (550-782). Consumers depend on the private half. workflow_runner.py imports four underscore names at module level and _drive inside drive_child, while goal_loop imports run_workflow inside _drive, a cycle that only function-local imports avoid. Besides workflow_runner.py, ten test files import goal_loop's private names: nine tests/db scripts (_finish, _drive, _settle_children, _settle_candidate, _keep_lease, _scope_guidance) and services/agent/tests/test_plans.py (_opening), counted by parsing every import statement.
- **Why it matters:** Settlement and the keeper are an undeclared API: reshaping _finish or _keep_lease breaks the workflow runner and ten test files, and import order becomes part of correctness. The API process and the tool catalog load deepagents and langgraph through this module just to call execution_block and loop_registry.
- **Recommendation:** Split along the existing seams, moving code without changing behavior. Tool assembly, prompts, the lease keeper, settlement and dispatch each get a module with public names. Make job dispatch the only module that imports both the goal loop and the workflow runner, and have it pass its own drive function to both as the child driver, since run_goal and run_workflow drive children through _drive today; then neither imports dispatch back. Keep temporary re-exports in goal_loop.py until tests/db moves to the public names.
- **Rule check:** DH-06 'small cohesive modules' and the DH-03 application/ layout. Code moves only: lease checks, fencing, receipts and transaction boundaries stay in the same functions, and the db profile proves the move.
- **Verification:** revised. Line ranges, the 22 definitions and every importer confirmed. An import scan finds ten test files using goal_loop's private names, not seven. The sketch now injects the child driver, because run_goal and drive_child call _drive, and a dispatcher that both import would otherwise bring the cycle back.

```text
application/loop_tools.py     loop_registry, SummarizationOff        <- tool_catalog, workflow_runner, goal_loop
application/loop_prompts.py   SYSTEM_PROMPT, opening(goal), scope_guidance(conn, run_id, goal)
application/lease_keeper.py   keep_lease(database_url, lease, config): async context manager
application/settlement.py     finish_pass (was _finish), loop_result (was _result), run_status,
                              settle_cancellation (was _settle_children + _cancel_stray_child)
application/job_dispatch.py   process_next, drive (was _drive), execution_block
                              imports goal_loop.run_goal and workflow_runner.run_workflow and passes
                              `drive` to both as the child driver, so neither imports it back
application/goal_loop.py      LoopConfig, LoopResult, run_goal(..., drive_child), build_stage, settle_candidate
```

### <a id="prun-02"></a>PRUN-02: Stop codes are bare strings, and any code missing from PAUSE_FOR fails the run permanently

- **Severity** high · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/application/goal_loop.py:92-115](../../../../services/agent/src/autobots/application/goal_loop.py#L92): PAUSE_FOR: 19 codes, 9 of them FailureClass values retyped as literals
  - [services/agent/src/autobots/application/goal_loop.py:116](../../../../services/agent/src/autobots/application/goal_loop.py#L116): NOT_OURS: no comment says what it means
  - [services/agent/src/autobots/application/goal_loop.py:740-745](../../../../services/agent/src/autobots/application/goal_loop.py#L740): None verifies, PAUSE_FOR suspends, everything else fails
  - [services/agent/src/autobots/application/goal_loop.py:773-781](../../../../services/agent/src/autobots/application/goal_loop.py#L773): the pass outcome as a nested string conditional
  - [services/agent/src/autobots/adapters/loop_middleware.py:77-88](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L77): STOPPING: another code set that feeds _finish
  - [services/agent/src/autobots/application/run_usage.py:36-39](../../../../services/agent/src/autobots/application/run_usage.py#L36): codes built with an f-string from the counter name, so grep can't find them
  - [services/agent/src/autobots/application/worker_inference.py:68-72](../../../../services/agent/src/autobots/application/worker_inference.py#L68): credential_invalid becomes invalid_credential before PAUSE_FOR sees it
  - [services/agent/src/autobots/application/assignments.py:203](../../../../services/agent/src/autobots/application/assignments.py#L203): a consumer compares outcome and code with literals
- **Evidence:** _finish decides a run's fate by set membership:

  ```python
  elif code is None:
      command = RunCommand.VERIFY
  elif code in PAUSE_FOR:
      command = RunCommand.SUSPEND
  else:
      command = RunCommand.FAIL
  ```

  Codes arrive from goal_loop, loop_middleware (19 LoopStopped raises carrying FailureClass values, AdmissionRefused and LimitReached codes), workflow_runner and worker_inference refusals. Five string sets route them: PAUSE_FOR and NOT_OURS here, STOPPING and REPAIRABLE in loop_middleware, and PLAN_REJECTIONS in plans.py. For example, rate_limited or provider_error after retries fails the run, while network_before_acceptance pauses it, and only PAUSE_FOR's membership shows that. No test references PAUSE_FOR or NOT_OURS. LoopResult.outcome is a str with five values, unlike ToolOutcome in domain/tools.py:74.
- **Why it matters:** A new or misspelled code silently becomes a terminal FAILED run, which can never resume. Knowing what any code does means reading five sets in three modules.
- **Recommendation:** Add a StopCode StrEnum and an explicit disposition table that maps every code reaching _finish to its current behavior. Then derive PAUSE_FOR and NOT_OURS from the table, and type LoopResult.outcome. Add a test that every FailureClass value, AdmissionRefused code, LimitReached counter and STOPPING member has a disposition. Whether an unmapped code should suspend instead of fail is a separate decision for the owner.
- **Rule check:** SP-010 (terminal runs cannot resume) and DH-06 'explicit enums/unions'. Mapping each code to its current disposition first changes no behavior. StopCode is a reason code, not a second run-state enum, and stays separate from DTOs.
- **Verification:** confirmed. Counted 19 PAUSE_FOR codes (nine are FailureClass values), five routing sets and 19 LoopStopped raises in loop_middleware.py; no test names PAUSE_FOR or NOT_OURS.

```text
class Disposition(StrEnum):
    VERIFY = 'verify'; SUSPEND = 'suspend'; FAIL = 'fail'; RELEASE = 'release'   # RELEASE was NOT_OURS

class StopCode(StrEnum):
    BUDGET_EXCEEDED = 'budget_exceeded'; RATE_LIMITED = 'rate_limited'; LEASE_LOST = 'lease_lost'  # ...

DISPOSITION: Final[Mapping[StopCode, Disposition]] = {...}   # every member, reviewed once

def disposition_of(code: StopCode | None) -> Disposition: ...   # pure; exhaustive unit test

class PassOutcome(StrEnum):
    CANDIDATE = 'candidate'; WAITING = 'waiting'; LOST = 'lost'; STOPPED = 'stopped'; SUCCEEDED = 'succeeded'
```

### <a id="prun-03"></a>PRUN-03: _finish mixes the stop decision with cancellation settlement and raw job writes, and reads the status three times

- **Severity** high · **Dimension** functions · **Effort** M · **Risk** high · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/goal_loop.py:697-782](../../../../services/agent/src/autobots/application/goal_loop.py#L697): 86 lines, C901 11, no docstring, 14 callers in two modules
  - [services/agent/src/autobots/application/goal_loop.py:703](../../../../services/agent/src/autobots/application/goal_loop.py#L703): first status read
  - [services/agent/src/autobots/application/goal_loop.py:709](../../../../services/agent/src/autobots/application/goal_loop.py#L709): second read, compared with the literal 'cancelling'
  - [services/agent/src/autobots/application/goal_loop.py:713-718](../../../../services/agent/src/autobots/application/goal_loop.py#L713): job requeued with a raw UPDATE
  - [services/agent/src/autobots/application/goal_loop.py:722](../../../../services/agent/src/autobots/application/goal_loop.py#L722): classify_interrupted with generation + 1, to include this owner's receipts
  - [services/agent/src/autobots/application/goal_loop.py:732-739](../../../../services/agent/src/autobots/application/goal_loop.py#L732): third read, then a raw job release
  - [services/agent/src/autobots/application/goal_loop.py:771-772](../../../../services/agent/src/autobots/application/goal_loop.py#L771): CommandRefused recorded as lease_lost
  - [services/agent/src/autobots/application/goal_loop.py:773-781](../../../../services/agent/src/autobots/application/goal_loop.py#L773): outcome derived from the final code
- **Evidence:** 

  ```python
  if code != "lease_lost" and await _run_status(connection, lease) == RunStatus.CANCELLING.value:
      code = "run_not_running" if await _holds_lease(connection, lease) else "lease_lost"
  if code is None and not view.finished:
      code = "plan_missing" if view.version is None else "plan_incomplete"
  command: RunCommand | None
  if code == "run_not_running" and await _run_status(connection, lease) == "cancelling":
  ```

  One function normalizes the code, settles a cancelled tree (children, requeue, classification), releases a paused job, picks the command, commits it with stop_reason in one transaction and maps the outcome.
- **Why it matters:** Every goal and workflow pass ends here, yet its decision table can only be exercised through a disposable database. The three status reads can disagree under a concurrent pause or cancel; apply_command re-validates under locks, so the cost is muddled reporting rather than a wrong write. A refused command is reported as a lost lease, so a parent's assignment sees 'lost' for what was a state conflict.
- **Recommendation:** Read status and ownership once, decide with a pure function, then run the effects. Keep the generation and status='claimed' guards on the job writes, keep classify_interrupted before FINISH_CANCEL, and keep the transition and its stop_reason in one transaction. Give a refused command its own stop code.
- **Rule check:** SP-010 cancellation rules and SP-012 fencing: apply_command still re-validates under row locks, job writes keep their generation predicates, and nothing reaches FINISH_CANCEL before outstanding work is classified.
- **Verification:** revised. Opened every cited line; the reads at 703, 709 and 732 and the CommandRefused-to-lease_lost mapping are as stated. The impact now notes that apply_command's own checks keep the writes safe, so the gain is clarity, testability and honest reporting.

```text
@dataclass(frozen=True)
class Observed:
    status: RunStatus; holds_lease: bool; plan: PlanView

@dataclass(frozen=True)
class Decision:
    code: StopCode | None; command: RunCommand | None; outcome: PassOutcome
    settle_cancel: bool; release_job: bool

def decide(code: StopCode | None, seen: Observed) -> Decision: ...      # pure, table-tested

async def finish_pass(conn, lease, goal, code) -> LoopResult:
    decision = decide(code, await observe(conn, lease, goal))
    if decision.settle_cancel:
        decision = await settle_cancellation(conn, lease)      # children, requeue, classify
    if decision.release_job:
        await release_job(conn, lease)                         # fenced by generation
    if decision.command:
        decision = await commit_stop(conn, lease, decision)    # apply + stop_reason, one transaction
    return await loop_result(conn, lease, goal, decision)
```

### <a id="prun-04"></a>PRUN-04: admit_run takes 15 parameters and a binding typed Any that four different shapes satisfy

- **Severity** high · **Dimension** functions · **Effort** M · **Risk** high · **Occurrences** 6
- **Where:**
  - [services/agent/src/autobots/application/runs.py:172-189](../../../../services/agent/src/autobots/application/runs.py#L172): 15 parameters, 124 lines
  - [services/agent/src/autobots/application/runs.py:185](../../../../services/agent/src/autobots/application/runs.py#L185): binding: Any decides tool grants and instructions
  - [services/agent/src/autobots/application/runs.py:195-196](../../../../services/agent/src/autobots/application/runs.py#L195): inherit silently replaces binding
  - [services/agent/src/autobots/application/runs.py:136-138](../../../../services/agent/src/autobots/application/runs.py#L136): policy is optional in the signature but required at runtime
  - [services/agent/src/autobots/application/runs.py:236-260](../../../../services/agent/src/autobots/application/runs.py#L236): 16-column positional insert with eight conditional expressions
  - [services/agent/src/autobots/application/routines.py:385](../../../../services/agent/src/autobots/application/routines.py#L385): SimpleNamespace binding; also workflows.py:397 and improvements.py:392
  - [services/agent/src/autobots/operations/browse_trial.py:175](../../../../services/agent/src/autobots/operations/browse_trial.py#L175): binding built with type('Binding', (), {...})()
  - [services/agent/src/autobots/application/experts.py:274](../../../../services/agent/src/autobots/application/experts.py#L274): RunBinding, the typed shape, whose non-optional fields the namespaces can't meet
- **Evidence:** 

  ```python
  binding: Any = None,
  inherit: Inheritance | None = None,
  ...
  if inherit is not None:
      binding = inherit
  ```

  The six callers pass a RunBinding (api/run_routes.py:264), SimpleNamespace objects (routines, workflows, improvements) whose session or Expert fields are None where RunBinding declares them non-optional, a class built with type() (browse_trial), or an Inheritance through inherit (assignments). The binding fills GoalSpec.allowed_tools and instructions (runs.py:283-284) and part of the idempotency fingerprint (runs.py:209). One function resolves a repeated goal, computes the fingerprint, checks continuation and performs six inserts.
- **Why it matters:** Nothing checks at the type level the scope a run is admitted with, mypy strict accepts any object, and policy=None fails only at runtime. Every admission edit is high-stakes, because the receipt fingerprint must stay byte-identical for replays.
- **Recommendation:** Introduce a frozen RunAdmission request, a typed RunScope with optional session and Expert fields, and an origin union, so that 'a policy unless inherited' is a type rule. Extract the fingerprint, the continuation check and the inserts. Keep request_hash's payload byte-identical, with a golden test against today's hashes, and keep run, job, first event and receipt in one transaction.
- **Rule check:** SP-012 and SP-014: the admitted run, job, first event and receipt still commit together. Decision 0015's started_by rule is unchanged, and RunAccepted and other DTOs stay separate from the request type.
- **Verification:** revised. Confirmed the signature, the 16-column insert and all six callers. Corrected two details: the insert has eight conditional expressions, not seven, and the routines namespace sets expert_id and version (it is session_id that is None there).

```text
@dataclass(frozen=True)
class RunScope:                    # replaces RunBinding subsets, SimpleNamespace and type(...)()
    session_id: UUID | None; expert_id: UUID | None; expert_version: int | None
    instructions: str; tools: Mapping[str, int]

@dataclass(frozen=True)
class Fresh:     policy: RolePolicy; scope: RunScope | None
@dataclass(frozen=True)
class Inherited: inheritance: Inheritance

@dataclass(frozen=True)
class RunAdmission:
    workspace_id: UUID; actor_id: UUID; started_by: UUID | None; idempotency_key: str
    goal_text: str | None; limit_micro_usd: int; origin: Fresh | Inherited
    criteria: tuple[str, ...] = (); continues_run_id: UUID | None = None
    required_artifacts: tuple[RequiredArtifact, ...] = ()
    input_documents: tuple[InputDocument, ...] = (); run_profile: str | None = None

async def admit_run(conn, admission: RunAdmission) -> AdmissionResult:
    goal = await _goal_text(conn, admission)
    fingerprint = admission_fingerprint(admission, goal)       # same payload as today
    async with conn.transaction():
        ...  # replay receipt, _require_continuable, _insert_run_and_job, _insert_inputs,
             # _insert_goal_spec, append_event, store_receipt
```

### <a id="prun-05"></a>PRUN-05: Display redaction keeps its own three-pattern regex, weaker than the log redaction

- **Severity** high · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/application/run_projection.py:58-61](../../../../services/agent/src/autobots/application/run_projection.py#L58): _SECRETS: sk-, Bearer (capitalized only) and eyJ
  - [services/agent/src/autobots/application/run_projection.py:89-90](../../../../services/agent/src/autobots/application/run_projection.py#L89): public_text, imported by 7 other modules, 26 calls in src
  - [services/agent/src/autobots/operations/logs.py:12-25](../../../../services/agent/src/autobots/operations/logs.py#L12): _SECRET: 11 alternatives, including tvly-, jina_, GitHub tokens and credentialed URLs
  - [services/agent/tests/test_contracts.py:126-127](../../../../services/agent/tests/test_contracts.py#L126): tests cover only sk-or and Bearer
- **Evidence:** run_projection.py:59-61 compiles three alternatives: sk- followed by 4 or more characters, Bearer with a capital B, and eyJ tokens. The log redactor matches sk-or-, sk-, tvly-, jina_, ghp_/gho_/ghu_/ghs_/ghr_, github_pat_, bearer in any case, JWTs, credentialed database and HTTP URLs, and password or token assignments. Re-run in memory: public_text leaves tvly-, jina_, ghp_ and github_pat_ tokens, a lowercase bearer value and https://user:pass@host intact, while logs.redact masks every one. public_text sanitizes plans, summaries, evidence, goal labels and run-list text written by the model, for display in the UI. Its importers are four api route modules, memory.py, workflows.py and operations/route_qualification.py.
- **Why it matters:** A Tavily, Jina or GitHub token that a model echoes into a plan or summary is redacted in the logs but shown to workspace members, although the projection's own comment (run_projection.py:58) says a key the model was shown must not be displayed. Each new tool key widens the gap, because nothing ties the two lists together.
- **Recommendation:** Keep the token shapes in one pure module that both logs.redact and public_text use. Display keeps its 500-character cut and can skip the key=value heuristic. Share one fixture list of token shapes across both modules' tests.
- **Rule check:** SP-011 (the public projection never exposes secrets) and python-worker.md 'sanitized public projections'; Decision 0025 V2 states the same principle for stored keys. The change only widens display redaction and keeps log redaction's coverage, so no guardrail is loosened.
- **Verification:** revised. Reproduced the gap in memory for every token shape listed. The rule check now cites SP-011 ('never exposes secrets') as the governing rule, and the change risk is medium rather than low because the shared module also feeds log redaction.

```text
# autobots/domain/secrets.py: pure, no I/O
TOKEN_SHAPES: Final[tuple[str, ...]] = (SK_OR, SK, TAVILY, JINA, GITHUB_CLASSIC, GITHUB_PAT,
                                        BEARER_ANY_CASE, JWT, CREDENTIALED_URL)   # one list, one owner
_TOKENS = re.compile('|'.join(TOKEN_SHAPES))
def mask_tokens(text: str) -> str: return _TOKENS.sub('[redacted]', text)

# operations/logs.py  redact(text)      = mask identifiers and key=value pairs, then mask_tokens(text)
# run views           public_text(text) = mask_tokens(text)[:limit]
# tests               one TOKEN_FIXTURES list asserted against both redact and public_text
```

### <a id="prun-06"></a>PRUN-06: apply_command packs replay, ownership, guard, cancel cascade and job rules into one 97-line transaction

- **Severity** medium · **Dimension** functions · **Effort** M · **Risk** high · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/application/runs.py:390-403](../../../../services/agent/src/autobots/application/runs.py#L390): 11 parameters, C901 13
  - [services/agent/src/autobots/application/runs.py:411-413](../../../../services/agent/src/autobots/application/runs.py#L411): a receipt applies only when both actor_id and idempotency_key are given
  - [services/agent/src/autobots/application/runs.py:436-438](../../../../services/agent/src/autobots/application/runs.py#L436): live-claim test, first copy
  - [services/agent/src/autobots/application/runs.py:449-461](../../../../services/agent/src/autobots/application/runs.py#L449): cancel side effects inline, recursing into apply_command for children
  - [services/agent/src/autobots/application/runs.py:462-467](../../../../services/agent/src/autobots/application/runs.py#L462): second copy, overriding _job_status
  - [services/agent/src/autobots/application/runs.py:468-476](../../../../services/agent/src/autobots/application/runs.py#L468): third copy
  - [services/agent/src/autobots/application/runs.py:381-387](../../../../services/agent/src/autobots/application/runs.py#L381): _require_owner unpacks the job row by position
  - [services/agent/src/autobots/application/runs.py:298-304](../../../../services/agent/src/autobots/application/runs.py#L298): _job_status, the pure part of the rule
- **Evidence:** 

  ```python
  if following is RunStatus.CANCELLING and not (
      job is not None and job[0] == "claimed" and bool(job[2])
  ):
      # Open work with no live owner. Something has to come back and settle it.
      job_status = "queued"
  ```

  The same positional test appears at lines 436, 464 and 472-473. Passing actor_id without idempotency_key, or the reverse, silently skips the receipt.
- **Why it matters:** After each transition, a rule decides whether a worker or nobody owns the run. It is split across _job_status and two inline overrides on a tuple, and can only be tested against a database.
- **Recommendation:** Name the locked job row and make the post-transition job status one pure, unit-tested function. Move the cancel side effects into a helper. Make the receipt an optional parameter object, so the actor and key are passed together or not at all. Keep the lock order (job row, then run row), the version check and the receipt in the one transaction.
- **Rule check:** SP-010 'atomic domain update/outbox event' and SP-012 ownership checked in the writing transaction: everything stays inside the same transaction and lock order; only code moves.
- **Verification:** confirmed. Opened apply_command and its helpers; the three positional live-claim tests and the paired receipt condition are as stated.

```text
@dataclass(frozen=True)
class LockedJob:
    status: str | None; generation: int | None; live: bool
    @property
    def live_claim(self) -> bool: return self.status == 'claimed' and self.live

@dataclass(frozen=True)
class Receipt:
    actor_id: UUID; idempotency_key: str

def job_status_after(following: RunStatus, actor: Actor, job: LockedJob) -> str | None: ...  # pure
async def _withdraw_waits_and_cascade(conn, workspace_id: UUID, run_id: UUID) -> None: ...
```

### <a id="prun-07"></a>PRUN-07: Run and job state are written from four modules, beside the command table rather than through it

- **Severity** medium · **Dimension** structure · **Effort** M · **Risk** high · **Occurrences** 15
- **Where:**
  - [services/agent/src/autobots/application/worker_leases.py:101-103](../../../../services/agent/src/autobots/application/worker_leases.py#L101): the claim writes queued to running with record_transition and never consults next_status
  - [services/agent/src/autobots/domain/runs.py:86](../../../../services/agent/src/autobots/domain/runs.py#L86): RunCommand.CLAIM is never issued, and neither is REPAIR (line 90)
  - [services/agent/src/autobots/application/goal_loop.py:713-718](../../../../services/agent/src/autobots/application/goal_loop.py#L713): job requeued with a literal status
  - [services/agent/src/autobots/application/goal_loop.py:734-739](../../../../services/agent/src/autobots/application/goal_loop.py#L734): job released with a literal status
  - [services/agent/src/autobots/application/goal_loop.py:748-763](../../../../services/agent/src/autobots/application/goal_loop.py#L748): read the version, then apply: one of 7 copies
  - [services/agent/src/autobots/application/workflow_runner.py:346-357](../../../../services/agent/src/autobots/application/workflow_runner.py#L346): another copy
  - [services/agent/src/autobots/application/runs.py:350-357](../../../../services/agent/src/autobots/application/runs.py#L350): cascade cancel issued as Actor.USER
  - [services/agent/src/autobots/application/approvals.py:222-229](../../../../services/agent/src/autobots/application/approvals.py#L222): approval expiry, run by the worker, pauses the run as Actor.USER
- **Evidence:** The domain table (domain/runs.py:24-125) is the guard, and apply_command enforces it under locks. Around it, run or job rows are written directly in four modules: the claim transition in worker_leases.py bypasses next_status; job rows get literal statuses in runs.py:477, worker_leases.py:90 and goal_loop.py:714 and 735; and operations/browse_trial.py:213 sets status='running' itself after its claim. Seven call sites (goal_loop.py:457, 564, 624 and 748, workflow_runner.py:346, approvals.py:66, assignments.py:279) read the run's version and pass it straight back. Four system actions (runs.py:355, goal_loop.py:634, approvals.py:227, assignments.py:292) are issued as Actor.USER because the table has only USER and WORKER, and the status event (runs.py:96-97) records no actor. Total: 4 job writers + 7 version-read copies + 4 system commands issued as USER.
- **Why it matters:** To answer 'what can move this run or its job', an engineer has to read several modules. A guard added to the CLAIM entry would not apply to claims, and guards and events can't tell a cascaded or expiry-driven command from a person's.
- **Recommendation:** Give the application one transitions surface. It should offer apply_command for people, and apply_worker_command(lease, ...), which reads the version and writes stop_reason in the same transaction. Add cascade_command with an explicit system actor, a claim that calls next_status(CLAIM), and named job helpers with a JobStatus enum. Keep every generation and status='claimed' predicate as it is.
- **Rule check:** DH-06 'documented transition table with actors, guards, writes' and SP-010 actor authorization. The system actor would be added to domain/runs.py together with the py-domain reviewers. CANCEL and RESUME stay refused to WORKER, and no guard is removed.
- **Verification:** revised. Confirmed that CLAIM and REPAIR are never issued, the 4 job writers, the 7 version-read copies and the 4 system commands issued as USER. The evidence now names the four modules that write run or job rows directly, adding operations/browse_trial.py:213.

```text
class JobStatus(StrEnum): QUEUED = 'queued'; CLAIMED = 'claimed'; DONE = 'done'

async def apply_worker_command(conn, lease: Lease, command: RunCommand, *, detail: str = '',
                               stop_reason: str | None | Unset = UNSET) -> TransitionResult: ...
async def cascade_command(conn, *, workspace_id: UUID, run_id: UUID, command: RunCommand,
                          cause: Cascade) -> TransitionResult: ...       # Actor.SYSTEM
async def requeue_job(conn, lease: Lease, *, available_at: datetime) -> None: ...  # generation + claimed guard
async def release_job(conn, lease: Lease) -> None: ...
```

### <a id="prun-08"></a>PRUN-08: The frozen policy snapshot is an untyped dict, written once and parsed ad hoc in seven places

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/application/runs.py:136-154](../../../../services/agent/src/autobots/application/runs.py#L136): the only writer: version, bindings, sources, routes
  - [services/agent/src/autobots/application/goal_loop.py:580-589](../../../../services/agent/src/autobots/application/goal_loop.py#L580): _summary_route: snapshot.get('bindings', {})
  - [services/agent/src/autobots/application/goal_loop.py:592-599](../../../../services/agent/src/autobots/application/goal_loop.py#L592): _route_is_bound: the same read, in a second query
  - [services/agent/src/autobots/application/worker_inference.py:107-123](../../../../services/agent/src/autobots/application/worker_inference.py#L107): frozen_policy: (snapshot or {}) four times
  - [services/agent/src/autobots/application/worker_inference.py:306-313](../../../../services/agent/src/autobots/application/worker_inference.py#L306): bind selects it again
  - [services/agent/src/autobots/application/worker_inference.py:354-361](../../../../services/agent/src/autobots/application/worker_inference.py#L354): role_route selects it again
  - [services/agent/src/autobots/application/run_projection.py:275-292](../../../../services/agent/src/autobots/application/run_projection.py#L275): _role_map: 'or {}' at every level
  - [services/agent/src/autobots/application/run_projection.py:580-586](../../../../services/agent/src/autobots/application/run_projection.py#L580): read_inspector selects it again
- **Evidence:** goal_loop.py:598 reads snapshot.get('bindings', {}).get(config.route.role), which raises on a null snapshot or a null bindings value. worker_inference.py:109 reads (snapshot or {}).get('bindings') or {}, and run_projection.py:280-282 coalesces each level. Three more readers are SQL in run_projection.py (lines 251, 428 and 445). One worker pass can select the snapshot four times (bind, role_route, _summary_route, _route_is_bound).
- **Why it matters:** The snapshot is durable admission state whose frozen routes must survive releases, yet its shape lives only in dict keys. Readers disagree about missing values, and a change to the writer has no type to update with it.
- **Recommendation:** Add a PolicySnapshot type with parse() and a to_json() that produces exactly today's bytes, plus one load_policy_snapshot(conn, run_id). Parse once in bind and pass the result into the loop instead of selecting it again.
- **Rule check:** model-gateway.md 'freeze canonical/wire identities and role policy at admission' and DH-06 'version role-policy snapshots'. The stored format is unchanged, and the type stays separate from the FrozenBinding DTO.
- **Verification:** confirmed. Confirmed the writer, the Python readers' differing null handling (goal_loop.py:598 raises on a null snapshot), the three SQL readers and the four selects in one pass.

```text
@dataclass(frozen=True)
class FrozenRoute:
    wire_id: str; canonical_id: str

@dataclass(frozen=True)
class PolicySnapshot:
    version: int
    bindings: Mapping[str, str]          # role -> profile
    sources: Mapping[str, str]           # empty for snapshots from before MD-02
    routes: Mapping[str, FrozenRoute]    # profile -> frozen identities
    @classmethod
    def parse(cls, raw: Mapping[str, Any] | None) -> 'PolicySnapshot': ...
    def to_json(self) -> str: ...        # sort_keys, same bytes as runs._snapshot
```

### <a id="prun-09"></a>PRUN-09: The invocation ledger's states, failure classes and spend formula are restated as literals in five modules

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** high · **Occurrences** 14
- **Where:**
  - [services/agent/src/autobots/application/model_admission.py:9-11](../../../../services/agent/src/autobots/application/model_admission.py#L9): ACTIVE and OUTSTANDING, the only named sets
  - [services/agent/src/autobots/application/model_admission.py:128-136](../../../../services/agent/src/autobots/application/model_admission.py#L128): admission's spend formula, again at 308-310
  - [services/agent/src/autobots/application/model_admission.py:188-195](../../../../services/agent/src/autobots/application/model_admission.py#L188): status guard as a SQL literal, SET clause built with an f-string
  - [services/agent/src/autobots/application/recovery.py:21-32](../../../../services/agent/src/autobots/application/recovery.py#L21): a second writer of reserved-to-cancelled and dispatched-to-uncertain
  - [services/agent/src/autobots/application/model_attempts.py:148](../../../../services/agent/src/autobots/application/model_attempts.py#L148): 'charge_not_reported', a failure class outside FailureClass
  - [services/agent/src/autobots/application/runs.py:332-333](../../../../services/agent/src/autobots/application/runs.py#L332): 'reserved' and 'dispatched' restated
  - [services/agent/src/autobots/application/run_projection.py:62](../../../../services/agent/src/autobots/application/run_projection.py#L62): comment: the public figures can't drift from what admission counted
  - [services/agent/src/autobots/application/run_projection.py:79-83](../../../../services/agent/src/autobots/application/run_projection.py#L79): the projection's own spend formula, copied at 446-450
- **Evidence:** The six invocation states (reserved, dispatched, succeeded, failed_before_acceptance, uncertain, cancelled) have no enum, and both ModelAdmission and recovery.classify_interrupted change them. Four failure classes live outside FailureClass: charge_not_reported, worker_lost, cancelled_after_dispatch and cancelled. Admission counts spend as the reservation while an attempt is outstanding and the charge otherwise. The projection computes two separate sums with an extra reconciled_at filter, and workflow_overview.py:24 holds a third copy. About 14 literal sites, counted by reading the 13 files plus grep for reconciled_at and the status lists.
- **Why it matters:** SP-008 requires shared root and workspace accounting, and SP-010 asks for documented state machines kept separate from run status, which the model-call ledger lacks. Today a new status or failure class has to be found in five files, and nothing enforces the comment that promises the public figures match admission.
- **Recommendation:** Add InvocationStatus and settlement-reason enums beside FailureClass, and make ModelAdmission the only writer (recovery calls a method on it). Define spend once, either as a SQL view or function in a forward migration or as one shared SQL fragment. Add a test that admission and projection agree on a seeded ledger.
- **Rule check:** SP-008 (reserve before dispatch, shared accounting) and SP-010's separately documented state machines. Migrations only move forward, and the reservation and settlement rules are unchanged.
- **Verification:** revised. Opened every cited writer and formula. SP-010 names steps, tool attempts, approvals and credentials for documented state machines, so the model-call ledger is covered by extension; the impact and rule check now say so instead of quoting a rule SP-010 doesn't state.

### <a id="prun-10"></a>PRUN-10: Run-status sets are restated as literals instead of derived from RunStatus and TERMINAL

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/domain/runs.py:22](../../../../services/agent/src/autobots/domain/runs.py#L22): TERMINAL, the canonical set
  - [services/agent/src/autobots/application/run_projection.py:339](../../../../services/agent/src/autobots/application/run_projection.py#L339): can_continue restates the terminal set
  - [services/agent/src/autobots/application/run_projection.py:383-387](../../../../services/agent/src/autobots/application/run_projection.py#L383): GROUPS lists all ten statuses by hand
  - [services/agent/src/autobots/application/runs.py:346](../../../../services/agent/src/autobots/application/runs.py#L346): SQL literal list for the cancel cascade
  - [services/agent/src/autobots/application/goal_loop.py:655](../../../../services/agent/src/autobots/application/goal_loop.py#L655): a local terminal set
  - [services/agent/src/autobots/application/goal_loop.py:709](../../../../services/agent/src/autobots/application/goal_loop.py#L709): 'cancelling' as a literal, six lines after RunStatus.CANCELLING.value
  - [services/agent/src/autobots/application/goal_loop.py:732](../../../../services/agent/src/autobots/application/goal_loop.py#L732): 'paused' as a literal
  - [services/agent/src/autobots/application/runs.py:157-169](../../../../services/agent/src/autobots/application/runs.py#L157): the repeat-goal rule that can_continue mirrors in Python
- **Evidence:** The terminal set appears four times in this area (run_projection.py:339 and 386, runs.py:346, goal_loop.py:655) and three more times in application/ (retention.py:107, routines.py:306, workflows.py:492). Counted with grep for the literal triple, plus goal_loop.py:655. can_continue (terminal, no parent, not a workflow) restates in Python what _goal_to_repeat checks in SQL.
- **Why it matters:** A status added to or renamed in RunStatus would be missing from GROUPS (the run would show under 'all' and in no group), from the cancel cascade and from settlement, and no test would fail. The UI's Continue can drift from what admission accepts.
- **Recommendation:** Use RunStatus members and TERMINAL everywhere, passing [s.value for s in TERMINAL] as an SQL parameter. Build GROUPS from RunStatus, with a test that each status belongs to exactly one group. Share one repeat-goal eligibility rule between the projection and admission.
- **Rule check:** SP-010 canonical states and contracts.md 'canonical states/guards are shared'. Serialized values are unchanged.
- **Verification:** confirmed. grep found the literal triple at run_projection.py:339 and :386, runs.py:346, retention.py:107, routines.py:306 and workflows.py:492, plus goal_loop.py:655's local set.

### <a id="prun-11"></a>PRUN-11: Run views read one run with 7 to 19 statements and no common snapshot

- **Severity** medium · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/application/run_projection.py:305-380](../../../../services/agent/src/autobots/application/run_projection.py#L305): read_workspace: 19 statements
  - [services/agent/src/autobots/application/run_projection.py:373](../../../../services/agent/src/autobots/application/run_projection.py#L373): the event cursor comes from the first statement
  - [services/agent/src/autobots/application/run_projection.py:576-664](../../../../services/agent/src/autobots/application/run_projection.py#L576): read_inspector: 7 statements, selecting again the row _require_run already read
  - [services/agent/src/autobots/api/event_routes.py:71-76](../../../../services/agent/src/autobots/api/event_routes.py#L71): a pool connection with no transaction block, so READ COMMITTED per statement
- **Evidence:** read_workspace runs these in sequence: _require_run, load_goal, usage, tokens, artifacts, two outstanding counts, a workflow check, five plan queries, verification, Expert, assignments, unknown operations, the role map and metered calls. Under READ COMMITTED each statement sees its own snapshot, so status and cursor come from the first query while plan, verification and counts can include later commits.
- **Why it matters:** SP-011 asks for an authoritative snapshot on reconnect. One response can pair a 'verifying' status with a passed verification, or show counts taken at different moments, and each page load costs 19 round trips.
- **Recommendation:** Run each view inside one read-only REPEATABLE READ transaction opened before its first statement. Then fold lookups of data the run row already holds (goal_summary, policy_snapshot) into the first query.
- **Rule check:** SP-011 'obtains an authoritative snapshot'. Read-only: no write path, field or sanitization changes.
- **Verification:** confirmed. Counted 19 statements in read_workspace and 7 in read_inspector. The API passes a pool connection at psycopg's default READ COMMITTED, so each statement takes its own snapshot.

```text
@asynccontextmanager
async def snapshot_read(conn) -> AsyncIterator[None]:
    async with conn.transaction():           # opened before any other statement on this connection
        await conn.execute('set transaction isolation level repeatable read, read only')
        yield
```

### <a id="prun-12"></a>PRUN-12: The database boundary is untyped: connection Any, positional rows and a bypassed RunRow

- **Severity** medium · **Dimension** types · **Effort** L · **Risk** medium · **Occurrences** 73
- **Where:**
  - [services/agent/src/autobots/application/run_projection.py:63-76](../../../../services/agent/src/autobots/application/run_projection.py#L63): _NAMES repeats RunRow's keys by hand
  - [services/agent/src/autobots/application/run_projection.py:119-120](../../../../services/agent/src/autobots/application/run_projection.py#L119): zip by position, then type: ignore[arg-type]
  - [services/agent/src/autobots/persistence/rows.py:8-20](../../../../services/agent/src/autobots/persistence/rows.py#L8): RunRow, the declared row type, which no query produces
  - [services/agent/src/autobots/application/run_projection.py:509-526](../../../../services/agent/src/autobots/application/run_projection.py#L509): 16 columns by index; tasks_complete=row[10] comes before tasks_total=row[9]
  - [services/agent/src/autobots/application/run_projection.py:597-621](../../../../services/agent/src/autobots/application/run_projection.py#L597): 18 columns by index
  - [services/agent/src/autobots/application/model_admission.py:151-157](../../../../services/agent/src/autobots/application/model_admission.py#L151): limits[0], limits[1], limits[2]
  - [services/agent/src/autobots/application/goal_loop.py:554](../../../../services/agent/src/autobots/application/goal_loop.py#L554): (await cursor.fetchone())[0], one of 17 in scope
  - [services/agent/src/autobots/application/worker_inference.py:309](../../../../services/agent/src/autobots/application/worker_inference.py#L309): the same pattern
- **Evidence:** The 13 files have 73 parameters typed connection: Any (grep), 17 unguarded `(await ...fetchone())[0]` subscripts, and 84 positional indexes in run_projection.py (row[...], item[...], usage[...], totals[...], tokens[...], shown[...]). mypy runs in strict mode ([services/agent/pyproject.toml:51](../../../../services/agent/pyproject.toml#L51)), but every query result is Any.
- **Why it matters:** A missing row surfaces as a TypeError far from its cause, and a reordered SELECT silently shifts values between columns of the same type. RunRow exists to keep rows explicit, yet its only producer bypasses it.
- **Recommendation:** Type connections with a small Protocol, as api/app.py:30 already does for the pool, or with psycopg.AsyncConnection. Use psycopg's dict_row or class_row with explicit column aliases for wide reads (RunRow, the run list, model calls). Add a fetch_one helper that raises a named error instead of subscripting None. Start with run_projection.py, which has the widest reads.
- **Rule check:** DH-06 'mypy strict for owned modules' and 'validate data at trust boundaries'. Rows stay separate from DTOs and domain types, and only the named adapters (contracts/adapters.py) convert them.
- **Verification:** confirmed. Recounted with grep: 73 connection: Any, 17 unguarded fetchone subscripts (16 on cursor plus one on expiry) and 84 positional indexes in run_projection.py. PDOM-08 reports the same pattern outside this area.

### <a id="prun-13"></a>PRUN-13: Ledger conflicts and missing rows are signalled with built-in exceptions that callers catch broadly

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/application/model_admission.py:194-195](../../../../services/agent/src/autobots/application/model_admission.py#L194): ValueError: already settled
  - [services/agent/src/autobots/application/model_admission.py:204-205](../../../../services/agent/src/autobots/application/model_admission.py#L204): ValueError: closed before it was sent
  - [services/agent/src/autobots/application/model_admission.py:291-292](../../../../services/agent/src/autobots/application/model_admission.py#L291): ValueError: not awaiting reconciliation
  - [services/agent/src/autobots/adapters/loop_middleware.py:585-592](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L585): any ValueError out of call_with_policy is read as 'recovery classified this call'
  - [services/agent/src/autobots/adapters/loop_middleware.py:276-278](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L276): float(cost) raises ValueError on a non-numeric charge
  - [services/agent/src/autobots/application/plans.py:102-103](../../../../services/agent/src/autobots/application/plans.py#L102): LookupError for a run with no goal
  - [services/agent/src/autobots/application/run_projection.py:308-316](../../../../services/agent/src/autobots/application/run_projection.py#L308): except LookupError also catches KeyError and IndexError
  - [services/agent/src/autobots/application/runs.py:137-138](../../../../services/agent/src/autobots/application/runs.py#L137): ValueError for a missing policy
- **Evidence:** The ledger's key signal, 'this attempt was settled elsewhere', is a plain ValueError, so loop_middleware.py:585 catches ValueError around the whole call. A reply whose cost metadata isn't numeric makes _charged raise ValueError inside dispatch, after the call was sent, so call_with_policy never settles it and the invocation stays dispatched. The middleware then treats it as a recovery race, and the handler's own _charged call raises again.
- **Why it matters:** An unrelated ValueError is misclassified on the paid path. A KeyError bug while loading a goal would render a run with no objective instead of failing. Callers can't catch the ledger's conditions by name.
- **Recommendation:** Add AttemptAlreadySettled, subclassing ValueError during the migration so existing catches keep working, and GoalMissing(LookupError). Raise them and catch only those names. Give CommandRefused a code like the other coded errors in application/runs.py.
- **Rule check:** DH-06 'centralize error handling ... expose safe typed errors'. The MP-08 classification and the handling of attempts settled elsewhere are unchanged.
- **Verification:** confirmed. Traced a non-numeric cost through dispatch, call_with_policy and the middleware's ValueError handler; each step behaves as stated.

### <a id="prun-14"></a>PRUN-14: An unclassified exception leaves the job claimed for endless re-claims, and nothing reads attempts

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** high · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/goal_loop.py:373-376](../../../../services/agent/src/autobots/application/goal_loop.py#L373): non-stale exceptions are re-raised
  - [services/agent/src/autobots/application/goal_loop.py:377-379](../../../../services/agent/src/autobots/application/goal_loop.py#L377): the keeper stops, and the job stays claimed until the lease runs out
  - [services/agent/src/autobots/application/worker_leases.py:80-81](../../../../services/agent/src/autobots/application/worker_leases.py#L80): an expired claim can be claimed again
  - [services/agent/src/autobots/application/worker_leases.py:91](../../../../services/agent/src/autobots/application/worker_leases.py#L91): attempts incremented on every claim
  - [services/agent/src/autobots/application/worker_leases.py:56](../../../../services/agent/src/autobots/application/worker_leases.py#L56): Lease.attempts, read nowhere
  - [services/agent/src/autobots/operations/worker.py:143-150](../../../../services/agent/src/autobots/operations/worker.py#L143): the step failure is logged as worker.step_failed and dropped
- **Evidence:** A grep for '.attempts' under application/ and operations/ finds no reader, and no migration bounds run_jobs.attempts ([supabase/migrations/20261105000007_run_admission.sql:14](../../../../supabase/migrations/20261105000007_run_admission.sql#L14) only checks attempts >= 0). worker.step_failed logs the error type and no run_id. A pass that raises before its first dispatch (in prompt building, scope guidance or graph construction) is claimed again after every lease period and fails the same way.
- **Why it matters:** A deterministic bug becomes an infinite loop of claims, recovery passes and error logs that operations shows only as expired leases. The run never reaches a state a person can act on.
- **Recommendation:** In the dispatch step, catch Exception (not BaseException, so cancellation still propagates) and log the run_id and error type. After N claims, suspend the run with a worker_error code; below N, release the job with a backoff through available_at.
- **Rule check:** SP-012 bounded retries and DH-06 'bound timeouts, retries ... propagate cancellation'. asyncio.CancelledError is a BaseException and stays uncaught, and a paused run remains resumable.
- **Verification:** revised. Confirmed that nothing reads Lease.attempts or run_jobs.attempts and that worker.step_failed logs only the error type. Raised the change risk to high, since the fix adds failure-path transitions on durable job and run state.

### <a id="prun-15"></a>PRUN-15: The lease keeper is started and stopped by hand in three places, and its cancelled task is never awaited

- **Severity** medium · **Dimension** approach · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/application/goal_loop.py:340](../../../../services/agent/src/autobots/application/goal_loop.py#L340): create_task in run_goal
  - [services/agent/src/autobots/application/goal_loop.py:378](../../../../services/agent/src/autobots/application/goal_loop.py#L378): cancel without await
  - [services/agent/src/autobots/application/goal_loop.py:449-455](../../../../services/agent/src/autobots/application/goal_loop.py#L449): the same pair in _settle_candidate
  - [services/agent/src/autobots/application/goal_loop.py:491-547](../../../../services/agent/src/autobots/application/goal_loop.py#L491): 57 lines, two nested infinite loops, C901 11
  - [services/agent/src/autobots/application/goal_loop.py:535-547](../../../../services/agent/src/autobots/application/goal_loop.py#L535): except Exception retries forever, logging the first and every 30th failure
  - [services/agent/src/autobots/application/workflow_runner.py:309-319](../../../../services/agent/src/autobots/application/workflow_runner.py#L309): the same pair in run_workflow
  - [services/agent/src/autobots/operations/worker.py:158-160](../../../../services/agent/src/autobots/operations/worker.py#L158): the worker already cancels and then awaits its own heartbeat task
- **Evidence:** 

  ```python
  beating = asyncio.create_task(_keep_lease(database_url, lease, config))
  ...
  finally:
      beating.cancel()
      await end_segment(connection, lease.run_id)
  ```
- **Why it matters:** Each new kind of pass has to copy the pattern. A cancelled task that nobody awaits closes its connection at some later point. A programming error in discount_sleep becomes a quiet reconnect loop while the lease keeps being extended, because the beat runs before the discount.
- **Recommendation:** Wrap the keeper in an async context manager that cancels and then awaits the task, as operations/worker.py does for its heartbeat. Split one look into a method that unit tests can drive with the injected WakeClock.
- **Rule check:** DH-06 'propagate cancellation after cleanup' and SP-012 heartbeats by database time. The heartbeat, revive and discount SQL and their order (beat before discount) are unchanged.
- **Verification:** confirmed. Confirmed the three create_task and cancel pairs, the unawaited cancels, the broad retry loop, and that operations/worker.py:158-160 awaits its heartbeat task after cancelling it.

```text
@asynccontextmanager
async def keep_lease(database_url, lease, config, clock=None) -> AsyncIterator[None]:
    task = asyncio.create_task(_LeaseKeeper(database_url, lease, config, clock).run())
    try:
        yield
    finally:
        task.cancel()
        await asyncio.wait({task})     # cleanup finished; the caller's own cancellation still propagates

class _LeaseKeeper:
    async def run(self) -> None: ...             # reconnect loop
    async def _look(self, conn) -> bool: ...     # one tick: wake check, beat or revive, discount
```

### <a id="prun-16"></a>PRUN-16: run_projection.py holds five read models, the cursor codec and the shared redaction in 664 lines

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/run_projection.py:54-90](../../../../services/agent/src/autobots/application/run_projection.py#L54): constants and public_text, used by 7 other modules
  - [services/agent/src/autobots/application/run_projection.py:129-150](../../../../services/agent/src/autobots/application/run_projection.py#L129): read_events
  - [services/agent/src/autobots/application/run_projection.py:157-222](../../../../services/agent/src/autobots/application/run_projection.py#L157): _plan_summary: 66 lines with two nested helpers
  - [services/agent/src/autobots/application/run_projection.py:305-380](../../../../services/agent/src/autobots/application/run_projection.py#L305): read_workspace: 76 lines
  - [services/agent/src/autobots/application/run_projection.py:383-533](../../../../services/agent/src/autobots/application/run_projection.py#L383): run list: groups, cursor codec, two SQL fragments and read_run_list (76 lines)
  - [services/agent/src/autobots/application/run_projection.py:536-544](../../../../services/agent/src/autobots/application/run_projection.py#L536): _canonical_id, defined 249 lines after its first use at line 287
  - [services/agent/src/autobots/application/run_projection.py:576-664](../../../../services/agent/src/autobots/application/run_projection.py#L576): read_inspector: 89 lines
- **Evidence:** Five entry points (read_summary, read_events, read_workspace, read_run_list, read_inspector) share one file with the redaction helper, the cursor codec and three SQL fragments. The theme is cohesive, but a change to any view touches the module that 7 others import for redaction.
- **Why it matters:** Navigation and review cost grow with each view, and the redaction everyone depends on changes in the same diffs as the UI read models.
- **Recommendation:** Turn the module into a package of the same name with one module per view, and re-export today's names from __init__ so api imports don't change. Move public_text to the shared redaction module (PRUN-05).
- **Rule check:** DH-06 'small cohesive modules' and SP-011's sanitized projection: no query, field or redaction behavior changes.
- **Verification:** confirmed. Confirmed the five entry points, the 664 lines and the _canonical_id placement. Moving public_text is shared with PRUN-05.

```text
application/run_projection/__init__.py  re-exports read_summary, read_events, read_workspace, read_run_list,
                                        read_inspector, InvalidCursor, RUN_LIST_SIZE
  summary.py    _SELECT_RUN, run row mapping, require_run, read_summary
  events.py     project_event, read_events
  workspace.py  read_workspace, plan_summary, verification, assignments, expert, role_map
  run_list.py   GROUPS, encode_cursor and decode_cursor, list SQL, read_run_list
  inspector.py  read_inspector, evidence, canonical_id
```

### <a id="prun-17"></a>PRUN-17: Settlement and transition decisions have no unit seam, so tests reach for private names and global patches

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 13
- **Where:**
  - [services/agent/src/autobots/application/goal_loop.py:697](../../../../services/agent/src/autobots/application/goal_loop.py#L697): _finish: exercised only by tests/db scripts
  - [services/agent/src/autobots/application/runs.py:298-304](../../../../services/agent/src/autobots/application/runs.py#L298): _job_status: pure, with no unit test
  - [tests/db/blocker_check.py:21](../../../../tests/db/blocker_check.py#L21): imports _finish (as does assignment_check.py:21)
  - [tests/db/review_check.py:21](../../../../tests/db/review_check.py#L21): imports _drive and _settle_children
  - [tests/db/wake_check.py:16](../../../../tests/db/wake_check.py#L16): imports _keep_lease
  - [services/agent/tests/test_worker_inference.py:480](../../../../services/agent/tests/test_worker_inference.py#L480): patches the private InferenceSource._refusal
  - [services/agent/tests/test_worker_inference.py:867](../../../../services/agent/tests/test_worker_inference.py#L867): patches psycopg.AsyncConnection.connect globally
  - [services/agent/src/autobots/application/worker_inference.py:230-232](../../../../services/agent/src/autobots/application/worker_inference.py#L230): open_attempt opens connections by URL, so tests can't inject them
- **Evidence:** services/agent/tests has no tests for runs.py's transitions, goal_loop's settlement, recovery.py, verification.py or run_projection's row mapping. These run only in tests/db scripts under the db profile. Thirteen test files import private names from these modules (found by parsing every import: ten take goal_loop names, two take runs._snapshot, one takes plans._evidence_exists), and test_worker_inference.py patches ProviderSettings, InferenceSource or psycopg at four sites in shared helpers (lines 480, 867, 868 and 1004).
- **Why it matters:** The riskiest decisions get feedback only from the slow disposable-database profile, and any refactor breaks tests that depend on private names.
- **Recommendation:** After the pure extractions (stop-code table, decide, job_status_after), add table-driven unit tests for them. Inject a connect callable into InferenceSource instead of patching psycopg. Keep tests/db for locks, fencing and restart behavior, importing public names only.
- **Rule check:** python-worker.md 'test stale ownership, cancellation, duplicate delivery and restart' stays in the db profile; DH-06 'tests use controlled clocks and injected transports' extends to connections.
- **Verification:** revised. An import scan finds 13 test files using private names, not ten, and the worker-inference tests patch at four sites, not six. No unit test covers apply_command, settlement, recovery, verification or the projection's row mapping.

### <a id="prun-18"></a>PRUN-18: Long positional signatures invite swapped arguments, and two constructors hand-copy every field

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [services/agent/src/autobots/application/goal_loop.py:208-218](../../../../services/agent/src/autobots/application/goal_loop.py#L208): build_stage: 9 positional parameters
  - [services/agent/src/autobots/application/goal_loop.py:346-356](../../../../services/agent/src/autobots/application/goal_loop.py#L346): called positionally, with two awaits among the arguments
  - [services/agent/src/autobots/application/compaction.py:198-207](../../../../services/agent/src/autobots/application/compaction.py#L198): store_summary: 8 positional parameters
  - [services/agent/src/autobots/adapters/loop_middleware.py:480-489](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L480): called positionally; role and profile are adjacent str arguments
  - [services/agent/src/autobots/application/worker_inference.py:158-167](../../../../services/agent/src/autobots/application/worker_inference.py#L158): bind_tools copies 7 fields by position
  - [services/agent/src/autobots/application/model_attempts.py:158-169](../../../../services/agent/src/autobots/application/model_attempts.py#L158): _with_attempt copies 9 fields by hand
  - [services/agent/pyproject.toml:47](../../../../services/agent/pyproject.toml#L47): ruff select has no C90 or PLR09 rule
- **Evidence:** _with_attempt rebuilds AdmissionRequest field by field where dataclasses.replace(request, attempt=attempt) would do, so a field added with a default would be silently dropped. store_summary(conn, run_id, cut, text, earlier, previous, route.role, route.profile) still type-checks with role and profile swapped.
- **Why it matters:** Swapped arguments of the same type pass mypy, and hand copies drift when a dataclass gains a field. Nothing in the lint configuration stops the lists from growing (admit_run reached 15).
- **Recommendation:** Make trailing parameters keyword-only, compute awaited arguments before the call, and use dataclasses.replace for copies (with AttemptModel as a frozen dataclass). Enable ruff PLR0917 and C901 with a per-file baseline, so new code meets them.
- **Rule check:** DH-06 'Ruff for lint/format'. A baseline adds a gate without failing today's code.
- **Verification:** confirmed. Confirmed each signature and call. ruff 0.17.3 lists PLR0917 as a stable rule (not preview), so it can be enabled as recommended.

### <a id="prun-19"></a>PRUN-19: plan_tools is a 121-line factory whose handlers can't be tested alone

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/plans.py:177-297](../../../../services/agent/src/autobots/application/plans.py#L177): plan_tools, C901 13
  - [services/agent/src/autobots/application/plans.py:178-210](../../../../services/agent/src/autobots/application/plans.py#L178): propose, a closure that only needs limits.plan_revisions
  - [services/agent/src/autobots/application/plans.py:221-261](../../../../services/agent/src/autobots/application/plans.py#L221): complete, a closure that needs nothing from the factory
  - [services/agent/src/autobots/application/plans.py:107-116](../../../../services/agent/src/autobots/application/plans.py#L107): latest_plan returns a bare (int, list) tuple
  - [services/agent/src/autobots/application/plans.py:184-187](../../../../services/agent/src/autobots/application/plans.py#L184): used as plan[1] and plan[0]
- **Evidence:** test_plans.py covers validate_proposal and reference_shape, but propose, proposed_already and complete (hold_lease, consume and the idempotent inserts) run only in tests/db. validate_proposal's C901 score of 14 comes from a flat sequence of guard clauses, which reads well as it is.
- **Why it matters:** The handlers that write plans and evidence under a lease have no fast test, and positional plan tuples make each caller re-learn the order.
- **Recommendation:** Move the three handlers to module level, taking limits as a parameter (functools.partial in plan_tools), and return a small Plan(version, tasks) dataclass from latest_plan.
- **Rule check:** SP-011 'the model proposes; deterministic logic commits': hold_lease and consume stay inside the same transactions.
- **Verification:** confirmed. Confirmed plan_tools spans lines 177-297 and that test_plans.py imports only validate_proposal, reference_shape and PlanRejected from plans.py.

### <a id="prun-20"></a>PRUN-20: Active-time segments are written without the fence that discount_sleep uses

- **Severity** low · **Dimension** approach · **Effort** S · **Risk** medium · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/application/run_usage.py:59-64](../../../../services/agent/src/autobots/application/run_usage.py#L59): begin_segment: no generation check
  - [services/agent/src/autobots/application/run_usage.py:67-74](../../../../services/agent/src/autobots/application/run_usage.py#L67): end_segment: no generation check
  - [services/agent/src/autobots/application/run_usage.py:77-94](../../../../services/agent/src/autobots/application/run_usage.py#L77): discount_sleep: fenced, 'so a lost one can't move a new owner's clock'
  - [services/agent/src/autobots/application/goal_loop.py:377-379](../../../../services/agent/src/autobots/application/goal_loop.py#L377): a stale owner's finally block still runs end_segment
- **Evidence:** A worker that lost its lease reaches the finally block after its next fenced write fails. end_segment then adds the new owner's elapsed time and sets its segment_started_at to null, so the new owner's later time is never counted.
- **Why it matters:** The 15-minute active-time limit undercounts after a reassignment, and the module's own stated invariant holds for only one of its three writers.
- **Recommendation:** Pass the lease to begin_segment and end_segment, and reuse discount_sleep's generation predicate.
- **Rule check:** Decision 0014 accepts uncounted active time as a release limit; removing one of its causes doesn't contradict that. The call, tool and money limits are untouched, and the fence matches discount_sleep's.
- **Verification:** revised. Traced the stale owner's finally block: end_segment adds the new owner's elapsed time and nulls its segment. Reworded the rule check, because Decision 0014 accepts the limit but doesn't say it can be changed under its ID.

### <a id="prun-21"></a>PRUN-21: The central decision points have no contract docstring, and one module docstring is wrong

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [services/agent/src/autobots/application/goal_loop.py:291](../../../../services/agent/src/autobots/application/goal_loop.py#L291): run_goal: no docstring
  - [services/agent/src/autobots/application/goal_loop.py:697](../../../../services/agent/src/autobots/application/goal_loop.py#L697): _finish: no docstring
  - [services/agent/src/autobots/application/goal_loop.py:116](../../../../services/agent/src/autobots/application/goal_loop.py#L116): NOT_OURS: no comment
  - [services/agent/src/autobots/application/goal_loop.py:148-159](../../../../services/agent/src/autobots/application/goal_loop.py#L148): LoopResult.outcome takes five values, none of them listed
  - [services/agent/src/autobots/application/run_projection.py:1](../../../../services/agent/src/autobots/application/run_projection.py#L1): says nothing here reads checkpoints
  - [services/agent/src/autobots/application/run_projection.py:640-645](../../../../services/agent/src/autobots/application/run_projection.py#L640): read_inspector selects from agent_runtime.checkpoints
  - [services/agent/src/autobots/application/worker_inference.py:324-328](../../../../services/agent/src/autobots/application/worker_inference.py#L324): two function-local imports with no reason given, unlike goal_loop.py:433
- **Evidence:** Small helpers carry precise comments explaining why, but run_goal (90 lines) and _finish (86 lines) have no docstring, so the codes they emit and the outcomes they return can only be learned by reading the bodies. The projection's module docstring contradicts read_inspector, which reads checkpoint ids, step and source (metadata only, as its own docstring says).
- **Why it matters:** Readers have to reverse-engineer the pass contract, and a reviewer checking SP-011's rule against raw checkpoint data is misled by the module docstring.
- **Recommendation:** Document run_goal and _finish (inputs, codes emitted, outcome values), say what NOT_OURS means, and give the deferred imports a reason. Change the projection docstring to 'reads checkpoint metadata (ids, step, source), never checkpoint content'.
- **Rule check:** DH-06 'explain nonobvious invariants in code'. Decision and story citations stay.
- **Verification:** confirmed. Confirmed the missing docstrings, the five outcome values and that read_inspector reads checkpoint metadata from agent_runtime.checkpoints despite the module docstring.

### <a id="prun-22"></a>PRUN-22: Names that hide meaning: profiles.py, two spellings of one credential code, and generation + 1

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/application/profiles.py:1-5](../../../../services/agent/src/autobots/application/profiles.py#L1): member display names, while 'profile' elsewhere in the service means a model profile
  - [services/agent/src/autobots/application/profiles.py:54-64](../../../../services/agent/src/autobots/application/profiles.py#L54): returns a positional (id, name, role, timezone) tuple
  - [services/agent/src/autobots/application/worker_inference.py:68-72](../../../../services/agent/src/autobots/application/worker_inference.py#L68): credential_invalid mapped to invalid_credential
  - [services/agent/src/autobots/application/goal_loop.py:722](../../../../services/agent/src/autobots/application/goal_loop.py#L722): classify_interrupted(..., lease.generation + 1)
  - [services/agent/src/autobots/application/recovery.py:33-37](../../../../services/agent/src/autobots/application/recovery.py#L33): the 'generation < %s' predicate the + 1 relies on
- **Evidence:** domain/models.PROFILES, run_profile, ModelRoute.profile and approved_profile all mean model profiles, so application/profiles.py reads as their home. The public settings contract uses credential_invalid ([contracts/settings.py:179](../../../../services/agent/src/autobots/contracts/settings.py#L179)), while FailureClass uses invalid_credential. Passing generation + 1 makes classify_interrupted also mark the current owner's started receipts as unknown, which only the SQL reveals.
- **Why it matters:** Small, repeated misreads: the wrong file opened when looking for model profiles, a grep for one spelling that misses the other, and a + 1 that looks like an off-by-one error.
- **Recommendation:** Rename the module to member_profiles.py (one import, in api/routes.py) and return a small named type. Keep both public codes, but comment the mapping. Give classify_interrupted an explicit keyword such as include_current_owner.
- **Rule check:** Public error codes stay unchanged; the renames are internal.
- **Verification:** confirmed. Confirmed the module's purpose, its single importer (api/routes.py:15), the two credential spellings and the generation predicate in recovery.py.

## Rejected during verification

None. Every finding held up at its cited lines and was kept; where counts, evidence, severity or risk changed, the finding is marked revised and its verification line says what changed.

## Not covered

This was a static review: no tests or verify profiles were run, and nothing was written. Supporting files outside the area were read only around the cited lines: workflow_runner.py, loop_middleware.py, assignments.py, approvals.py, experts.py, routines.py, workflows.py, improvements.py, artifacts.py, operations/worker.py, operations/logs.py, operations/browse_trial.py, the api route modules, tests/db checks and test_worker_inference.py. The SQL migrations and triggers behind database fencing (SQLSTATE AB001) were not read, so claims about database-enforced checkpoint fencing rest on adapters/checkpoints.py and its call sites. Query cost (for example the correlated subqueries in _LIST_SELECT) was not measured. Only the task-named sections of PRD-Development-Harness.md (DH-03 to DH-06) and option-b-contract.md (SP-006 to SP-014) were read, and metrics.md was read in part. An extra exploratory ruff run (BLE, TRY, S608, FBT, PLC0415, ARG, SLF, PLR2004) printed to the terminal only and was not saved. No earlier review existed to compare against.
