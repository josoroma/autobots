# Python: product services

These eleven product-service modules (3,250 lines) are careful SQL services. Every create and new-version command goes through an idempotency receipt, durable writes are fenced by the run lease, artifacts publish only after a hash read-back, and routines are scheduled on database time under row locks. Comments explain invariants and cite their decisions. What raises the cost of change falls into three groups. (1) Typing stops at the seams. Connections and rows are Any (79 signatures and about 130 positional row reads in scope). Run admission takes an Any binding that three call sites fill with SimpleNamespace. Literals and models the API validates reach the application as str and dict. (2) Rules are restated instead of shared. Six receipt-and-version procedures are copied by hand. Workspace policy is loaded by 8 queries (3 here), the run-ledger SQL exists in 3 copies, agent-node detection in 4 places, and terminal run states in 3 private copies. Three stop-code lists already disagree on parent_not_running, so a pause can fail a workflow's agent node, contrary to requirement B6 ('a pause during a node stops it'). (3) A few hotspots carry most of the size. assign_tool is 134 lines with complexity 17, mostly closures that capture nothing. create_execution is 113 lines with 12 parameters, one of them unused, and read_execution is 99 lines. workflow_runner's 69-line block dispatch also depends on five private goal_loop functions through a two-way import. Would shared persistence helpers reduce the duplication without merging row and domain types? Yes. A typed connection, NamedTuple row types with explicit *_from_row mappers (the RunRow / run_from_row precedent), a receipted() helper, a next_version() helper over a closed set of tables, one workspace-policy loader and one ledger SQL fragment would all compose SQL and return rows. Domain, DTO and view types would stay where they are. Keep these helpers as narrow functions, not a generic repository (DH-06 warns against speculative frameworks). Many PLR0913 hits here are keyword-only signatures and cost little. The positional chains (7 PLR0917 hits) are the ones worth fixing. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Passes the project's ruff and mypy strict, but falls short of DH-06 (no broad Any or untyped dicts, no duplicated business rules) and AGENTS.md canonical states: 79 connection: Any, 3 copies of the terminal states, 8 policy loaders. No size rules are configured. |
| modules | 3 | Direction is domain to application to api. But 6 function-level imports (3 of them hiding cycles), workflow_runner uses five goal_loop privates, and 5 of 11 modules are both services and tool definitions. |
| size | 3 | Files are 61 to 550 lines. Most functions are short, but three run 99 to 134 lines and two exceed complexity 10 (17 and 13). |
| functions | 3 | Many small single-purpose helpers (narrowed_tools, _pattern, object_path). The largest functions mix 6 to 8 steps and pass records as positional tuples. |
| structure | 4 | Matches DH-03's application layer with one module per product concept. A few pieces are misplaced (approval tool models, the offload reader), and workflows.py hosts three concerns. |
| approach | 4 | Durability is exemplary: receipts, leases, staged publication, skip-locked scheduling on database time. List views are N+1, and one internal call reuses a user-facing idempotent command. |
| comments | 4 | Module docstrings cite PRD and decision IDs, and comments state invariants. 35 of 53 public functions are documented, with gaps at run_workflow and assign_tool, and lazy imports go unexplained. |
| types | 2 | Untyped connections and rows, an Any admission binding fed by SimpleNamespace, contract Literals widened to str, and positional tuples used as records. |
| errors | 3 | Refusal codes are typed and mapped to safe errors, and causes are suppressed on purpose. But the stop-code lists have drifted and seven exception classes copy one body. |
| tests | 3 | Behavior is covered by db checks (24 to 55 cases per module) and a few unit tests. Pure rules here have little fast coverage, and search and workflow_overview have no Python tests. |
| maintainability | 3 | Correct, carefully reasoned code. Change costs more than it should because rules are duplicated across modules, typing is weak at the SQL and admission seams, and a few functions are oversized. |

## Strengths

- **Idempotency receipts on every create and version command, with compatible fingerprints.** All nine create and new-version commands in scope check and store a receipt inside their transaction ([services/agent/src/autobots/application/experts.py:128-153](../../../../services/agent/src/autobots/application/experts.py#L128), [services/agent/src/autobots/application/routines.py:162-186](../../../../services/agent/src/autobots/application/routines.py#L162), [services/agent/src/autobots/application/workflows.py:154-174](../../../../services/agent/src/autobots/application/workflows.py#L154)). Fingerprint changes preserve old receipts deliberately: workflows.py:153 says 'Only when given, so a receipt from before descriptions still matches.' Toggles, drafts, improvement decisions and owner notes (store_memory) take no receipt.
- **Staged, verified artifact publication and order-aware reconciliation.** [services/agent/src/autobots/application/artifacts.py:78-123](../../../../services/agent/src/autobots/application/artifacts.py#L78) stages a row, uploads, reads back and compares the hash, and only then publishes under the lease. reconcile_run (artifacts.py:153-157) lists objects before reading rows, so another worker's fresh upload can't look like an orphan.
- **Fenced durable writes.** [services/agent/src/autobots/application/workflow_runner.py:133-148](../../../../services/agent/src/autobots/application/workflow_runner.py#L133) commits each node instance in one transaction under hold_lease, with insert-only emissions. assignments.py:102-109 takes the lease and a for-share status read before admitting a child. artifacts.py:120-122 publishes under the lease.
- **Scheduling on database time, with row locks and per-routine isolation.** [services/agent/src/autobots/application/routines.py:414-427](../../../../services/agent/src/autobots/application/routines.py#L414) uses 'for update skip locked' and reads clock_timestamp() under the row lock, with a comment explaining why. routines.py:478-488 keeps one routine's failure from stopping the rest, and logs only the error type, per the redaction policy in [services/agent/src/autobots/operations/logs.py:64-66](../../../../services/agent/src/autobots/operations/logs.py#L64).
- **Pure, tested decision helpers at the trust points.** narrowed_tools ([services/agent/src/autobots/application/assignments.py:42-67](../../../../services/agent/src/autobots/application/assignments.py#L42)) is pure and tested in [services/agent/tests/test_final_review.py:235-240](../../../../services/agent/tests/test_final_review.py#L235). expand_groups and validate_config (experts.py:32-73) are tested in [services/agent/tests/test_tool_catalog.py:148-197](../../../../services/agent/tests/test_tool_catalog.py#L148).
- **Workspace scoping and input hardening in SQL.** Every read names the workspace ([services/agent/src/autobots/application/search.py:1-3](../../../../services/agent/src/autobots/application/search.py#L1), experts.py:110, workflows.py:126). search.py:23-25 escapes LIKE wildcards. memory.py:69 uses websearch_to_tsquery, so a query can't be malformed. read_artifact (artifacts.py:219-233) takes the workspace from the row and checks the hash before bytes leave.
- **Comments that state invariants and cite their source.** [services/agent/src/autobots/application/routines.py:247-249](../../../../services/agent/src/autobots/application/routines.py#L247) (Decision 0026 C7), assignments.py:60 (N-4) and 104 (why the status read is under the lease), workflow_runner.py:86 (why a stop is not a failure), improvements.py:28-29 (why authority claims are refused).
- **Batched reads where they were needed.** [services/agent/src/autobots/application/workflow_overview.py:68-83](../../../../services/agent/src/autobots/application/workflow_overview.py#L68) loads every named Expert in one '= any(%s)' query, and workflow_overview.py:18-32 builds execution summaries in one set-based statement. This is the model for fixing the N+1 list views.

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [PPRD-01](#pprd-01) | high | types | Run admission takes an Any binding that three call sites fill with SimpleNamespace | S | medium |
| [PPRD-02](#pprd-02) | high | modules | workflow_runner is built on goal_loop's private lifecycle, and the two modules import each other | M | medium |
| [PPRD-03](#pprd-03) | high | errors | Stop codes live in three hand-kept lists that already disagree on parent_not_running | S | medium |
| [PPRD-04](#pprd-04) | medium | size | workflows.py mixes definitions, execution binding and the execution read model, with two ~100-line functions | M | medium |
| [PPRD-05](#pprd-05) | medium | size | assign_tool is 134 lines with complexity 17 because four independent helpers are closures | S | medium |
| [PPRD-06](#pprd-06) | medium | size | _run_block dispatches ten block kinds through an if-chain that isn't tied to the domain's block registry | M | medium |
| [PPRD-07](#pprd-07) | medium | duplication | Run-now and scheduled evaluation repeat the occurrence admission sequence | S | medium |
| [PPRD-08](#pprd-08) | medium | duplication | Six receipt-guarded create and new-version procedures repeat one sequence by hand | M | medium |
| [PPRD-09](#pprd-09) | medium | duplication | Policy resolution and the root-run ledger are rebuilt in SQL at each call site | S | medium |
| [PPRD-10](#pprd-10) | medium | duplication | Workflow graph facts are re-derived in four places, and the copies already behave differently | S | low |
| [PPRD-11](#pprd-11) | medium | approach | List and detail views issue per-row queries (N+1) | M | low |
| [PPRD-12](#pprd-12) | medium | types | The SQL boundary is untyped: Any connections, positional rows and unchecked fetchone results | L | medium |
| [PPRD-13](#pprd-13) | medium | types | Contract types the API validates degrade to str, dict and positional tuples inside the application | S | low |
| [PPRD-14](#pprd-14) | medium | standards | Canonical run statuses and SQL-owned status vocabularies are restated as literals | S | low |
| [PPRD-15](#pprd-15) | medium | modules | Product service modules also hold tool definitions and the knowledge store, which creates import cycles | M | low |
| [PPRD-16](#pprd-16) | medium | tests | Decision logic in this area has little fast test coverage because it sits inside database functions | M | low |
| [PPRD-17](#pprd-17) | low | errors | Seven refusal classes copy one body, and a few error paths say less than they mean | S | low |
| [PPRD-18](#pprd-18) | low | duplication | search.py re-implements tool_catalog.latest() with an Any-typed map | S | low |
| [PPRD-19](#pprd-19) | low | structure | Two tool definitions sit away from their owners | S | low |
| [PPRD-20](#pprd-20) | low | naming | A few names collide or hide their meaning | S | low |
| [PPRD-21](#pprd-21) | low | functions | Expert tool checks default to the process environment, though availability is the workspace's | S | low |

### <a id="pprd-01"></a>PPRD-01: Run admission takes an Any binding that three call sites fill with SimpleNamespace

- **Severity** high · **Dimension** types · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/application/runs.py:185](../../../../services/agent/src/autobots/application/runs.py#L185): admit_run(binding: Any = None) reads session_id, expert_id, version, tools and instructions
  - [services/agent/src/autobots/application/workflows.py:397-403](../../../../services/agent/src/autobots/application/workflows.py#L397): SimpleNamespace grant for a workflow run
  - [services/agent/src/autobots/application/routines.py:385-392](../../../../services/agent/src/autobots/application/routines.py#L385): SimpleNamespace grant for a routine's Expert run
  - [services/agent/src/autobots/application/improvements.py:392-398](../../../../services/agent/src/autobots/application/improvements.py#L392): SimpleNamespace grant for a held-out replay run
  - [services/agent/src/autobots/application/experts.py:273-282](../../../../services/agent/src/autobots/application/experts.py#L273): RunBinding, the typed shape the API passes
  - [services/agent/src/autobots/application/runs.py:52-63](../../../../services/agent/src/autobots/application/runs.py#L52): Inheritance, which also stands in as the binding for a child
- **Evidence:** Excerpt from routines.py:385-392. Counted with grep 'SimpleNamespace(' over services/agent/src: 3 hits, all in this area.

  ```python
  binding=SimpleNamespace(
      session_id=None,
      expert_id=config.target.id,
      version=pinned_version(config),
      instructions=expert.instructions
      + await active_skill_text(connection, workspace_id, expert.skills),
      tools={**PLAN_TOOLS, **{tool: EXPERT_TOOLS[tool] for tool in tools}},
  ),
  ```

- **Why it matters:** The binding carries the run's tool grant and instructions, and its expert_id and version enter the admission fingerprint. Because it is Any, mypy strict can't compare the three namespaces with RunBinding or Inheritance. A misspelled or newly required attribute fails only at run time, on the routine, replay and workflow admission paths that only the db checks reach.
- **Recommendation:** Declare the grant once in runs.py: a Protocol with read-only properties (session_id, expert_id, version, instructions, tools) and a frozen RunGrant dataclass that satisfies it. Type admit_run's binding with the Protocol and build RunGrant at the three call sites. RunBinding and Inheritance keep their own shapes and satisfy the Protocol structurally, so nothing merges. Keep the fingerprint inputs identical, and replay an existing receipt in a db check before and after the change.
- **Rule check:** DH-06: 'Avoid broad any/untyped dictionaries.' The grant is an application type. RunBinding (expert resolution) and Inheritance (child admission) stay distinct, so the contracts rule on keeping types apart holds.
- **Verification:** confirmed. admit_run reads binding.expert_id and version into the fingerprint (runs.py:209) and session_id, tools and instructions into the run (251-253, 283-284); grep finds exactly three SimpleNamespace( calls in src, all in this area.

```text
# application/runs.py
class AdmissionGrant(Protocol):
    @property
    def session_id(self) -> UUID | None: ...
    @property
    def expert_id(self) -> UUID | None: ...
    @property
    def version(self) -> int | None: ...
    @property
    def instructions(self) -> str: ...
    @property
    def tools(self) -> Mapping[str, int]: ...

@dataclass(frozen=True)
class RunGrant:                      # satisfies AdmissionGrant
    instructions: str
    tools: Mapping[str, int]
    session_id: UUID | None = None
    expert_id: UUID | None = None
    version: int | None = None

async def admit_run(..., binding: AdmissionGrant | None = None, inherit: Inheritance | None = None)
```

### <a id="pprd-02"></a>PPRD-02: workflow_runner is built on goal_loop's private lifecycle, and the two modules import each other

- **Severity** high · **Dimension** modules · **Effort** M · **Risk** medium · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/application/workflow_runner.py:16-24](../../../../services/agent/src/autobots/application/workflow_runner.py#L16): imports _finish, _keep_lease, _result, _run_status
  - [services/agent/src/autobots/application/workflow_runner.py:298-301](../../../../services/agent/src/autobots/application/workflow_runner.py#L298): function-level import of goal_loop._drive
  - [services/agent/src/autobots/application/goal_loop.py:432-436](../../../../services/agent/src/autobots/application/goal_loop.py#L432): goal_loop imports run_workflow inside _drive
  - [services/agent/src/autobots/application/workflow_runner.py:309-319](../../../../services/agent/src/autobots/application/workflow_runner.py#L309): heartbeat task created and cancelled, third copy
  - [services/agent/src/autobots/application/goal_loop.py:340-378](../../../../services/agent/src/autobots/application/goal_loop.py#L340): heartbeat copy in run_goal
  - [services/agent/src/autobots/application/goal_loop.py:449-455](../../../../services/agent/src/autobots/application/goal_loop.py#L449): heartbeat copy in _settle_candidate
  - [services/agent/src/autobots/application/workflow_runner.py:331](../../../../services/agent/src/autobots/application/workflow_runner.py#L331): _complete(goal: Any), because GoalSpec flows through private helpers
  - [services/agent/tests/test_workflows.py:13](../../../../services/agent/tests/test_workflows.py#L13): tests also import _run_block, _Stop and _tool
- **Evidence:** Excerpts from workflow_runner.py:16-24 (import list condensed) and 298-301. Counted by reading the import block and line 299: five private goal_loop functions.

  ```python
  from autobots.application.goal_loop import (
      LoopConfig, LoopResult, _finish, _keep_lease, _result, _run_status, loop_registry,
  )
  async def drive_child(child_connection: Any, child_lease: Lease) -> LoopResult:
      from autobots.application.goal_loop import _drive
      return await _drive(child_connection, database_url, child_lease, lambda: model, config)
  ```

- **Why it matters:** goal_loop is the largest application module (782 lines). It can't rename or change its private finish and settle helpers without silently changing how workflow runs finish, report and keep their lease. Importing workflow_runner loads goal_loop and every tool adapter it imports. The heartbeat start/cancel scaffolding exists three times.
- **Recommendation:** Make the shared run lifecycle a public module that both loops import. It holds LoopConfig, LoopResult, finish, result_of, run_status and a lease_heartbeat async context manager that owns the task's start and cancel in one place. Move loop_registry to its own registry module. Break the dispatch cycle by injection: _drive builds the child driver and passes it to run_workflow, so workflow_runner never imports goal_loop. Write the tests first (blocker_check, workflow_run_check and the goal-loop db checks), because finish and settle behavior is sensitive.
- **Rule check:** python-worker rule: 'One LangGraph lifecycle owns execution.' The change names that one lifecycle's API publicly instead of adding a second. Leases and fencing are untouched.
- **Verification:** confirmed. Five goal_loop privates confirmed (_finish, _keep_lease, _result, _run_status and the lazily imported _drive); the heartbeat create/cancel pair appears at workflow_runner.py:309-319 and goal_loop.py:340-378 and 449-455. goal_loop.py:433 does explain its own lazy import.

```text
application/run_lifecycle.py    LoopConfig, LoopResult
                                 finish(conn, lease, goal, code), result_of(...), run_status(conn, lease)
                                 @asynccontextmanager lease_heartbeat(database_url, lease, config)
application/registry.py          loop_registry(...)
application/goal_loop.py         run_goal/_settle_candidate use lease_heartbeat;
                                 _drive calls run_workflow(..., drive_child=lambda c, l: _drive(c, url, l, factory, config))
application/workflow_runner.py   run_workflow(conn, lease, model, config, *, drive_child: Driver, after_commit=...)
                                 imports run_lifecycle and registry only
```

### <a id="pprd-03"></a>PPRD-03: Stop codes live in three hand-kept lists that already disagree on parent_not_running

- **Severity** high · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/application/workflow_runner.py:87-98](../../../../services/agent/src/autobots/application/workflow_runner.py#L87): STOPS: 8 codes
  - [services/agent/src/autobots/application/workflow_runner.py:151-160](../../../../services/agent/src/autobots/application/workflow_runner.py#L151): any other non-success becomes BlockFailed, a permanent node failure
  - [services/agent/src/autobots/application/assignments.py:105-109](../../../../services/agent/src/autobots/application/assignments.py#L105): raises parent_not_running inside the leased transaction
  - [services/agent/src/autobots/application/goal_loop.py:92-116](../../../../services/agent/src/autobots/application/goal_loop.py#L92): PAUSE_FOR includes parent_not_running (line 109); NOT_OURS
  - [services/agent/src/autobots/adapters/loop_middleware.py:77-87](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L77): STOPPING, a third list
  - [services/agent/src/autobots/application/tool_gateway.py:290-298](../../../../services/agent/src/autobots/application/tool_gateway.py#L290): the gateway's own running check becomes run_not_running, which is in STOPS
  - [tests/db/blocker_check.py:176-194](../../../../tests/db/blocker_check.py#L176): B6: a pause during a node stops it without failing it
  - [services/agent/tests/test_workflows.py:308-319](../../../../services/agent/tests/test_workflows.py#L308): the unit test lists 4 of the 8 stop codes
- **Evidence:** goal_loop lists parent_not_running in PAUSE_FOR (goal_loop.py:109), but the workflow runner's STOPS does not, so `_tool` turns it into BlockFailed.

  ```python
  # assignments.py:108-109, inside _create's leased transaction
  if (await cursor.fetchone())[0] != RunStatus.RUNNING.value:
      raise ToolFailed("parent_not_running")
  # workflow_runner.py:156-159
  if result.code in STOPS:
      raise _Stop(str(result.code))
  if result.outcome.value != "succeeded":
      raise BlockFailed(str(result.code or "tool_failed"))
  ```

- **Why it matters:** goal_loop treats parent_not_running as a wait that a person can resolve. In a workflow it is not in STOPS. Suppose the run is paused after the gateway's running check (tool_gateway.py:290-298) commits and before _create's for-share read. The agent node is then committed as failed, and after resume the run ends workflow_node_failed, contrary to B6. Every new code an assignment can raise must be added by hand to lists in three modules across two layers. This is read from code; no test covers the race.
- **Recommendation:** Define the stop vocabulary once: a StrEnum plus named sets such as RETRY_LATER and NOT_OURS, in domain/tools.py or a small new module. Have assignments and the gateway raise its members, and derive STOPS, STOPPING and PAUSE_FOR from it. Add parent_not_running to the workflow's stops once a blocker_check case reproduces the pause-inside-_create race. Add a unit test that every code assign_tool can raise is classified in each set. Compare outcomes with ToolOutcome.SUCCEEDED rather than with .value strings.
- **Rule check:** python-worker rule: test stale ownership, cancellation and restart where behavior changes. Treating a pause as a stop keeps the node's receipt and replays it. No lease, fence or approval is weakened.
- **Verification:** confirmed. Traced the race: a user's pause leaves the worker's claimed lease live (runs.py:470-478), so _commit's hold_lease succeeds and the agent node is stored failed with parent_not_running, which goal_loop's PAUSE_FOR (109) treats as a wait. Read from code, not reproduced, so the recommended blocker_check case comes first. PTOL-09 in py-tools proposes the same vocabulary from the gateway side.

```text
# domain/stops.py
class StopCode(StrEnum):
    APPROVAL_PENDING = "approval_pending"; OUTCOME_UNKNOWN = "outcome_unknown"
    ASSIGNMENT_PAUSED = ...; ASSIGNMENT_LOST = ...; ASSIGNMENT_BUSY = ...; PARENT_NOT_RUNNING = ...
    LEASE_LOST = ...; RUN_NOT_RUNNING = ...; RUN_NOT_FOUND = ...
NOT_OURS = frozenset({LEASE_LOST, RUN_NOT_RUNNING, RUN_NOT_FOUND, APPROVAL_PENDING})
RETRY_LATER = frozenset({ASSIGNMENT_PAUSED, ASSIGNMENT_LOST, ASSIGNMENT_BUSY, PARENT_NOT_RUNNING, OUTCOME_UNKNOWN})
# workflow_runner.py
STOPS = NOT_OURS | RETRY_LATER
# test
assert ASSIGNMENT_CODES <= STOPS | PERMANENT_FAILURES
```

### <a id="pprd-04"></a>PPRD-04: workflows.py mixes definitions, execution binding and the execution read model, with two ~100-line functions

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/application/workflows.py:325-437](../../../../services/agent/src/autobots/application/workflows.py#L325): create_execution: 113 lines, 12 parameters
  - [services/agent/src/autobots/application/workflows.py:335](../../../../services/agent/src/autobots/application/workflows.py#L335): policy: no caller among 17 call sites passes it, and when given, require_offered is skipped
  - [services/agent/src/autobots/application/workflows.py:360-427](../../../../services/agent/src/autobots/application/workflows.py#L360): everything after the receipt lookup is nested under 'if existing is None'
  - [services/agent/src/autobots/application/workflows.py:305-322](../../../../services/agent/src/autobots/application/workflows.py#L305): _agent_session calls the user-facing create_session with a throwaway idempotency key
  - [services/agent/src/autobots/application/workflows.py:452-550](../../../../services/agent/src/autobots/application/workflows.py#L452): read_execution: 99 lines
  - [services/agent/src/autobots/application/workflows.py:481-487](../../../../services/agent/src/autobots/application/workflows.py#L481): reads r.status again and overwrites the unused value from 454-467
  - [services/agent/src/autobots/application/workflows.py:490-499](../../../../services/agent/src/autobots/application/workflows.py#L490): status rule for unstarted instances is a nested closure
- **Evidence:** Excerpt from workflows.py:360-367, inside the transaction after the receipt lookup. All 17 call sites in src and tests/db were checked: none passes policy=.

  ```python
  if existing is None:
      session_id = await _agent_session(connection, workspace_id, actor_id, graph)
      if policy is None:
          cursor = await connection.execute(
              "select default_profile, role_overrides from app_private.model_policies "
              "where workspace_id = %s",
              (workspace_id,),
          )
  ```

- **Why it matters:** create_execution performs eight steps inside one nested block: version lookup, input validation, receipt, session, policy resolution with the offered check, tool narrowing, run admission and the execution insert. The API and routines share this 12-argument entry point. Its unused policy branch is a trap that would skip require_offered. The session it creates stores a receipt under a random key that can never be replayed. In read_execution the first status read is dead, and the status rule for unstarted instances can only be tested against a database.
- **Recommendation:** Split the module by concern and extract named steps. Remove the unused policy parameter. Give sessions an internal insert that both create_session and _agent_session use. Return early when a receipt already exists. Make the instance-status rule a pure function with unit tests. Select current_instance and the pending-approval flag in the first query, and drop the second status read.
- **Rule check:** Receipts and the offered-profile check stay. Removing the unused policy branch removes a path that would skip a required check. No migration or contract change.
- **Verification:** confirmed. An AST scan of src, services/agent/tests, tests and scripts finds 17 create_execution calls and none passes policy. The internal session insert must keep the Expert-in-workspace checks create_session performs through get_expert and _option.

```text
application/workflows/          package; __init__ re-exports today's public names
  definitions.py   create, describe, drafts, publish, get, list                     ~300 lines
  executions.py    create_execution, orchestration only (~35 lines):
      _published_version(conn, ws, wf, version) -> PublishedVersion   # graph, hash, blocks, name
      execution_policy(conn, ws, graph) -> RolePolicy                 # shared loader + offered check
      granted_tools(requested: list[str] | None) -> dict[str, int]    # pure
      insert_session(conn, ws, actor, kind, pinned) -> UUID           # no receipt; create_session wraps it
    read_execution = _execution_row(...) + instance_views(saved, graph, current, run_status, pending)  # pure
  overview.py      today's workflow_overview.py
  runner.py        today's workflow_runner.py
```

### <a id="pprd-05"></a>PPRD-05: assign_tool is 134 lines with complexity 17 because four independent helpers are closures

- **Severity** medium · **Dimension** size · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/assignments.py:177-310](../../../../services/agent/src/autobots/application/assignments.py#L177): assign_tool, C901 17
  - [services/agent/src/autobots/application/assignments.py:218-294](../../../../services/agent/src/autobots/application/assignments.py#L218): _refuse_if_waiting, _finished_child, _close, _resume_if_paused never read delegation
  - [services/agent/src/autobots/application/assignments.py:196](../../../../services/agent/src/autobots/application/assignments.py#L196): a 5-tuple splatted by position into _close
  - [services/agent/src/autobots/application/assignments.py:227-229](../../../../services/agent/src/autobots/application/assignments.py#L227): returns tuple[str, str | None, str, list[str], list[str]]
  - [services/agent/src/autobots/application/assignments.py:244-253](../../../../services/agent/src/autobots/application/assignments.py#L244): _close: 8 positional parameters (PLR0917)
  - [services/agent/src/autobots/application/assignments.py:27](../../../../services/agent/src/autobots/application/assignments.py#L27): Driver returns Awaitable[Any], so the five LoopResult attributes run reads go unchecked
  - [services/agent/src/autobots/application/assignments.py:70-162](../../../../services/agent/src/autobots/application/assignments.py#L70): _create: 93 lines of checks, then leased admission
- **Evidence:** Excerpts from assignments.py:177-178, 196 and 244-253 (parameter list condensed).

  ```python
  def assign_tool(delegation: Delegation) -> ToolDefinition:
      async def run(arguments: AssignSpecialist, context: ToolContext) -> AssignmentResult:
                  return await _close(connection, assignment_id, child, *finished)
      async def _close(
          connection: Any, assignment_id: UUID, child: UUID, outcome: str,
          code: str | None, run_status: str | None, completed: list[Any], remaining: list[Any],
      ) -> AssignmentResult:
  ```

- **Why it matters:** Only run uses delegation. Nesting the four helpers counts them into one function, keeps them out of reach of unit tests, and couples _finished_child to _close by tuple position: reordering either one silently swaps code and run_status in the stored AssignmentResult.
- **Recommendation:** Move the four helpers to module level. Introduce a ChildOutcome dataclass, returned both by _finished_child and by a pure mapper from LoopResult (which raises ToolFailed for paused, lost and waiting). Give _close a single ChildOutcome parameter. Type Driver's result as LoopResult, through a TYPE_CHECKING import that avoids the runtime cycle, or as a small Protocol. Optionally split _create into the pre-transaction checks and the leased admission.
- **Rule check:** python-worker rule on replay: a finished assignment still returns its stored result and never starts a second specialist. The refactor moves code without changing that order.
- **Verification:** confirmed. Ruff reports C901 17 at assignments.py:177; the four nested helpers reference no enclosing name, and _finished_child's (outcome, code, status, completed, remaining) tuple feeds _close's matching positional parameters.

```text
@dataclass(frozen=True)
class ChildOutcome:
    outcome: str; code: str | None; run_status: str | None; completed: list[str]; remaining: list[str]
async def _finished_child(conn, child) -> ChildOutcome | None
def _outcome_of(result: LoopResult) -> ChildOutcome          # raises assignment_paused / assignment_lost
async def _close(conn, assignment_id, child, outcome: ChildOutcome) -> AssignmentResult
async def _run_assignment(delegation, arguments, context) -> AssignmentResult   # ~30 lines
def assign_tool(delegation) -> ToolDefinition:
    return ToolDefinition(..., handler=partial(_run_assignment, delegation))
```

### <a id="pprd-06"></a>PPRD-06: _run_block dispatches ten block kinds through an if-chain that isn't tied to the domain's block registry

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/workflow_runner.py:163-231](../../../../services/agent/src/autobots/application/workflow_runner.py#L163): _run_block: 69 lines, C901 13, 9 returns
  - [services/agent/src/autobots/domain/workflows.py:31-50](../../../../services/agent/src/autobots/domain/workflows.py#L31): BLOCKS already enumerates the same kinds
  - [services/agent/src/autobots/application/workflow_runner.py:124-132](../../../../services/agent/src/autobots/application/workflow_runner.py#L124): _commit: 7 positional parameters
  - [services/agent/src/autobots/application/workflow_runner.py:234-242](../../../../services/agent/src/autobots/application/workflow_runner.py#L234): _pass: 7 positional parameters
  - [services/agent/src/autobots/application/workflow_runner.py:190-219](../../../../services/agent/src/autobots/application/workflow_runner.py#L190): read_run_file, save_artifact, publish_artifact and workflow_approval spelled as literals
  - [services/agent/src/autobots/application/workflows.py:43](../../../../services/agent/src/autobots/application/workflows.py#L43): workflow_approval literal again (also line 384)
  - [services/agent/tests/test_workflows.py:377](../../../../services/agent/tests/test_workflows.py#L377): block logic is testable only through a fake gateway and a None connection
- **Evidence:** Excerpts from workflow_runner.py:175-179 and 231. Ruff: C901 13 and PLR0911 9 at line 163; PLR0917 at 124, 163 and 234.

  ```python
  if block == "input":
      return [("value", 0, inputs[step.node_id])]
  if block in {"output", "join"}:
      port = "items" if block == "join" else "value"
      return [(port, 0, value)]
  ...
  raise BlockFailed("unknown_block")
  ```

- **Why it matters:** A block added to BLOCKS validates and publishes, then fails only at run time as unknown_block. Pure blocks (input through foreach) share one function with gateway blocks (read, artifact, approval, agent), so the pure ones can't be tested without a gateway. gateway, connection, scope and execution_id travel by position through _pass, _run_block, _tool and _commit. Four tool ids are spelled as literals, though DELEGATION_TOOL already shows the constant pattern.
- **Recommendation:** Replace the chain with two tables keyed by block kind: pure runners with no I/O, and gateway runners. Add a unit test that their keys equal the keys of BLOCKS. Carry the per-execution values in one frozen _Execution object. Name the tool ids in domain/tools.py next to DELEGATION_TOOL.
- **Rule check:** Effects still go through the tool gateway with per-instance operation identity (scope.instance = step.key), so replay by receipt is unchanged.
- **Verification:** confirmed. Ruff reports C901 13 and PLR0911 9 at workflow_runner.py:163; validate_graph accepts any block present in BLOCKS (domain/workflows.py:233), so a new kind reaches unknown_block only at run time.

```text
@dataclass(frozen=True)
class _Execution:
    gateway: ToolGateway; connection: Db; scope: ToolScope; execution_id: UUID; shape: GraphShape; inputs: dict[str, Any]
class Emission(NamedTuple): port: str; sequence: int; value: Any
PURE_BLOCKS: Mapping[str, Callable[[Mapping[str, Any], Step, dict[str, Any]], list[Emission]]]          # input, output, join, transform, condition, foreach
TOOL_BLOCKS: Mapping[str, Callable[[_Execution, Mapping[str, Any], Step], Awaitable[list[Emission]]]]   # read, artifact, approval, agent
async def _run_block(execution: _Execution, node, step) -> list[Emission]
# test: set(PURE_BLOCKS) | set(TOOL_BLOCKS) == set(BLOCKS)
```

### <a id="pprd-07"></a>PPRD-07: Run-now and scheduled evaluation repeat the occurrence admission sequence

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/application/routines.py:285-299](../../../../services/agent/src/autobots/application/routines.py#L285): run_routine_now
  - [services/agent/src/autobots/application/routines.py:448-462](../../../../services/agent/src/autobots/application/routines.py#L448): _evaluate_one
  - [services/agent/src/autobots/application/routines.py:312-326](../../../../services/agent/src/autobots/application/routines.py#L312): _record: 7 positional parameters, called with a positional None
  - [services/agent/src/autobots/application/routines.py:259-261](../../../../services/agent/src/autobots/application/routines.py#L259): returns a positional (status, reason, run_id) tuple
  - [services/agent/src/autobots/application/cronjob_tool.py:146](../../../../services/agent/src/autobots/application/cronjob_tool.py#L146): the caller unpacks that tuple by position
  - [services/agent/src/autobots/application/routines.py:279](../../../../services/agent/src/autobots/application/routines.py#L279): database clock read, repeated at 426-427
- **Evidence:** Excerpt from routines.py:448-455; run_routine_now repeats it at 285-292, returning tuples.

  ```python
  if await _has_active_run(connection, routine_id):
      await _record(connection, routine_id, latest, version, "skipped_overlap", "run_active")
      return 0
  if await _needs_model(config, connection):
      code = await credential_check(workspace_id)
      if code != "ready":
          await _record(connection, routine_id, latest, version, "blocked", code)
          return 0
  ```

- **Why it matters:** Decision 0026 C6 promises that run now admits through the same admission as a scheduled occurrence. Today that holds only because about 15 lines are copied, so a new gate (a budget check, say) added to one copy diverges silently. Calls like _record(connection, routine_id, latest, version, "admitted", None, run_id) and the tuple return are easy to misorder.
- **Recommendation:** Extract one _admit_occurrence that applies the overlap, credential and admission checks in order, records the occurrence and returns a typed outcome. run_routine_now returns that outcome, and _evaluate_one counts admitted outcomes. Make _record's reason and run_id keyword-only, and read the database clock through one helper.
- **Rule check:** Decision 0026 C6 (run now admits through the same admission as a scheduled occurrence): one function makes that structural. Database time and the row lock stay as they are.
- **Verification:** confirmed. The overlap, credential, admit and record sequence is the same at routines.py:285-299 and 448-462, and Decision 0026 C6 says run admits 'through the same admission as a scheduled one'.

```text
class OccurrenceOutcome(NamedTuple):
    status: Literal["admitted", "skipped_overlap", "blocked"]; reason: str | None; run_id: UUID | None
@dataclass(frozen=True)
class _Occurrence: workspace_id: UUID; routine_id: UUID; version: int; moment: datetime
async def _admit_occurrence(conn, occ: _Occurrence, config: RoutineConfig, check: CredentialCheck) -> OccurrenceOutcome
async def _record(conn, occ: _Occurrence, status: str, *, reason: str | None = None, run_id: UUID | None = None) -> None
run_routine_now(...) -> OccurrenceOutcome      # missed occurrences stay in _evaluate_one
_evaluate_one(...)   -> int(outcome.status == "admitted")
```

### <a id="pprd-08"></a>PPRD-08: Six receipt-guarded create and new-version procedures repeat one sequence by hand

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 6
- **Where:**
  - [services/agent/src/autobots/application/experts.py:157-199](../../../../services/agent/src/autobots/application/experts.py#L157): add_version
  - [services/agent/src/autobots/application/routines.py:190-229](../../../../services/agent/src/autobots/application/routines.py#L190): add_routine_version
  - [services/agent/src/autobots/application/workflows.py:251-302](../../../../services/agent/src/autobots/application/workflows.py#L251): publish_version
  - [services/agent/src/autobots/application/experts.py:119-154](../../../../services/agent/src/autobots/application/experts.py#L119): create_expert hashes the request before expanding groups (128-130)
  - [services/agent/src/autobots/application/routines.py:150-187](../../../../services/agent/src/autobots/application/routines.py#L150): create_routine
  - [services/agent/src/autobots/application/workflows.py:144-175](../../../../services/agent/src/autobots/application/workflows.py#L144): create_workflow
  - [services/agent/src/autobots/application/experts.py:236-243](../../../../services/agent/src/autobots/application/experts.py#L236): create_session hashes the versions it resolved, not the request
  - [services/agent/src/autobots/application/runs.py:100-133](../../../../services/agent/src/autobots/application/runs.py#L100): receipt scope typed as tuple[UUID, UUID, str, str, str]
- **Evidence:** Excerpt from experts.py:184-189; routines.py:214-219 and workflows.py:279-284 have the same shape. Counted by reading: 3 version procedures and 3 create procedures. Grep for 'scope = (workspace_id, actor_id' finds 9 hand-built receipt scopes in this area.

  ```python
  row = await cursor.fetchone()
  if row is None:
      raise ExpertRefused("expert_not_found")
  if row[0] != expected_version:
      raise ExpertRefused("expert_version_conflict")
  version = row[0] + 1
  ```

- **Why it matters:** Each of the six repeats the receipt lookup, lock, not-found and conflict checks, insert, latest_version bump and receipt store. Each builds the receipt scope as a positional 5-tuple whose operation and target strings can be swapped without a type error. The copies already diverge: create_session fingerprints resolved versions, so an honest retry with the same key after an Expert gains a version is refused as idempotency_conflict, whereas create_expert fingerprints the request.
- **Recommendation:** Yes, shared persistence helpers would remove this without merging row and domain types. First, a ReceiptScope NamedTuple and a receipted helper that opens the transaction, takes the advisory lock and returns either the prior result or a store callback. Second, a next_version helper for the lock, check and bump step over a closed set of parent tables (composed with psycopg.sql.Identifier). It raises a typed conflict that each module maps to its own code. Each module keeps its own INSERT, row type and view mapping. Always fingerprint the request, never resolved state, and fix create_session accordingly; its old receipts mismatch once, then expire under retention. Keep the helpers narrow: no generic repository layer.
- **Rule check:** SQL still owns the schema: the helpers compose existing statements and need no migration. Row, domain and DTO types stay separate (DH-06 and the contracts rule). Receipt hashes must stay byte-identical for every operation except create_session, whose change should be called out.
- **Verification:** confirmed. Nine hand-built receipt scopes recounted; existing_receipt raises IdempotencyConflict on a changed fingerprint (runs.py:117-118), so create_session's retry behaves as described. add_routine_version also locks only rows where removed_at is null, which a shared next_version must keep. PTOL-15 proposes the same receipt helper for the decision commands.

```text
# application/receipts.py
class ReceiptScope(NamedTuple):
    workspace_id: UUID; actor_id: UUID; operation: str; target: str; key: str
@asynccontextmanager
async def receipted(conn, scope: ReceiptScope, fingerprint: str) -> AsyncIterator[Receipt]
    # Receipt.prior: dict | None;  await receipt.store(result)
# application/versioning.py
Versioned = Literal["experts", "routines", "workflows"]
async def next_version(conn, table: Versioned, row_id: UUID, workspace_id: UUID, expected: int) -> int
    # raises NotFound / VersionConflict; the caller maps them to expert_/routine_/workflow_ codes
```

### <a id="pprd-09"></a>PPRD-09: Policy resolution and the root-run ledger are rebuilt in SQL at each call site

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 11
- **Where:**
  - [services/agent/src/autobots/application/routines.py:354-368](../../../../services/agent/src/autobots/application/routines.py#L354): load the row, resolve with the Expert's overrides, require_offered
  - [services/agent/src/autobots/application/workflows.py:363-377](../../../../services/agent/src/autobots/application/workflows.py#L363): same steps, without run overrides
  - [services/agent/src/autobots/application/workflow_overview.py:119-139](../../../../services/agent/src/autobots/application/workflow_overview.py#L119): same query and resolution with the Expert's role bindings, for the preview's executor model, with no offered check
  - [services/agent/src/autobots/api/run_routes.py:123](../../../../services/agent/src/autobots/api/run_routes.py#L123): same query in the API (also line 204)
  - [services/agent/src/autobots/api/improvement_routes.py:100-112](../../../../services/agent/src/autobots/api/improvement_routes.py#L100): same query, resolve and require_offered
  - [services/agent/src/autobots/application/workflow_overview.py:18-32](../../../../services/agent/src/autobots/application/workflow_overview.py#L18): ledger subqueries, 'as the run list counts it'
  - [services/agent/src/autobots/application/run_projection.py:79-83](../../../../services/agent/src/autobots/application/run_projection.py#L79): second ledger copy
  - [services/agent/src/autobots/application/run_projection.py:446-453](../../../../services/agent/src/autobots/application/run_projection.py#L446): third ledger copy
- **Evidence:** Excerpt from routines.py:354-361. Counted with grep 'default_profile, role_overrides from app_private.model_policies' over services/agent/src: 8 sites, 3 in this area. Grep 'i.root_run_id = r.id or i.run_id = r.id' finds 3 ledger statements.

  ```python
  cursor = await connection.execute(
      "select default_profile, role_overrides from app_private.model_policies "
      "where workspace_id = %s",
      (workspace_id,),
  )
  policy_row = await cursor.fetchone()
  policy = resolve_role_policy(
      run_role_overrides={r: p.value for r, p in expert.role_bindings.items()},
  ```

- **Why it matters:** The role policy a run is admitted with (MP-01's order) and the money a list shows are business rules, and every copy must change together. The workflow preview computes the executor model separately from create_execution, and the two already differ: the preview applies the Expert's role bindings, while an agent step's child run inherits the workflow run's snapshot, which create_execution resolves without them. The three ledger copies must also agree on which invocation statuses count as reserved.
- **Recommendation:** Add one application function, workspace_role_policy(connection, workspace_id, *, run_overrides=None), plus require_offered_policy, and use it in routines, workflows, workflow_overview and the API. Add a helper that turns an ExpertConfig into overrides, replacing the comprehension repeated four times in scope. Decide whether an agent step's model comes from the Expert's bindings or from the workflow's snapshot, and have the preview and admission call the loader the same way; WF-03 doesn't say, so raise it as a question. Share one ledger SQL fragment between run_projection and workflow_overview, or add a view through a forward migration.
- **Rule check:** model-gateway rule: role policy is frozen at admission. One loader makes the preview and admission agree, and adds no fallback or alternative provider. A view, if chosen, arrives by a forward migration.
- **Verification:** revised. Recounted 8 loader queries (3 here) and 3 ledger statements. Reading on: preview_steps applies the Expert's role bindings, but an agent step's child run inherits the parent's policy snapshot (assignments.py:81-86 and 132-135), which create_execution resolves without them (workflows.py:369-372), so the preview already differs from admission when an Expert binds the executor role; read from code, not exercised. The preview also has no offered check, so its location note was corrected.

### <a id="pprd-10"></a>PPRD-10: Workflow graph facts are re-derived in four places, and the copies already behave differently

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [services/agent/src/autobots/application/workflows.py:440-449](../../../../services/agent/src/autobots/application/workflows.py#L440): needs_model: joins workflows for the workspace and returns False when the version is missing
  - [services/agent/src/autobots/application/routines.py:397-405](../../../../services/agent/src/autobots/application/routines.py#L397): _needs_model: no workspace join, TypeError when the version is missing
  - [services/agent/src/autobots/application/workflows.py:373](../../../../services/agent/src/autobots/application/workflows.py#L373): re-queries the graph that create_execution loaded at 341-350
  - [services/agent/src/autobots/application/workflows.py:309-311](../../../../services/agent/src/autobots/application/workflows.py#L309): agent Experts read with strict indexing
  - [services/agent/src/autobots/application/workflow_overview.py:86-92](../../../../services/agent/src/autobots/application/workflow_overview.py#L86): agent Experts read with defensive .get
  - [services/agent/src/autobots/application/workflows.py:512-515](../../../../services/agent/src/autobots/application/workflows.py#L512): parses node#iteration by hand
  - [services/agent/src/autobots/domain/workflow_execution.py:116-117](../../../../services/agent/src/autobots/domain/workflow_execution.py#L116): instance_key builds that format
- **Evidence:** The two needs_model checks and the instance-key parsing above, beside the agent-Expert extraction at workflows.py:309-311 and workflow_overview.py:86-92.

  ```python
  # workflows.py:449
  return row is not None and any(node["block"] == "agent" for node in row[0]["nodes"])
  # routines.py:404-405
  graph = (await cursor.fetchone())[0]
  return any(node["block"] == "agent" for node in graph["nodes"])
  # workflows.py:514-515
  node_id = current.split("#")[0]
  iteration = int(current.split("#")[1]) if "#" in current else None
  ```

- **Why it matters:** The two needs_model functions already differ in their workspace check and in how they handle a missing row. create_execution pays a second query for a graph it already holds. A change to the instance-key format in the domain would silently break the parsing in read_execution.
- **Recommendation:** Add pure domain helpers next to BLOCKS and instance_key: agent_expert_ids(graph), needs_model(graph) and parse_instance_key(key). Database functions load the graph once and call them, and routines applies the shared helper to the version it already loads.
- **Rule check:** DH-06: keep domain decisions independent of database clients. These are pure rules over workflow IR, so they belong in domain/workflows.py and domain/workflow_execution.py.
- **Verification:** confirmed. workflows.needs_model returns False on a missing row while routines._needs_model raises TypeError from indexing None; instance_key at domain/workflow_execution.py:116-117 is the only builder of the node#iteration format that read_execution parses.

### <a id="pprd-11"></a>PPRD-11: List and detail views issue per-row queries (N+1)

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** low · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/application/workflows.py:135-141](../../../../services/agent/src/autobots/application/workflows.py#L135): list_workflows: _view per row
  - [services/agent/src/autobots/application/workflows.py:104-120](../../../../services/agent/src/autobots/application/workflows.py#L104): _overview re-reads the workspace and adds recent, chain and count: 5-6 queries per workflow
  - [services/agent/src/autobots/application/experts.py:100-105](../../../../services/agent/src/autobots/application/experts.py#L100): list_experts: 2 queries per Expert
  - [services/agent/src/autobots/application/routines.py:141-147](../../../../services/agent/src/autobots/application/routines.py#L141): list_routines: 2 queries per routine
  - [services/agent/src/autobots/application/improvements.py:297-315](../../../../services/agent/src/autobots/application/improvements.py#L297): list_candidates: replay_state per row, up to 100 rows
  - [services/agent/src/autobots/application/experts.py:266-269](../../../../services/agent/src/autobots/application/experts.py#L266): get_session: _option per pinned Expert
  - [services/agent/src/autobots/application/workflows.py:220-248](../../../../services/agent/src/autobots/application/workflows.py#L220): publish_draft rebuilds the full view three times
  - [services/agent/src/autobots/application/improvements.py:77-84](../../../../services/agent/src/autobots/application/improvements.py#L77): one query per evidence item
- **Evidence:** Excerpt from workflows.py:135-141. Query counts come from reading the call chains, not from measurement.

  ```python
  async def list_workflows(connection: Any, workspace_id: UUID) -> list[WorkflowView]:
      cursor = await connection.execute(
          "select id, name, latest_version, description from public.workflows "
          "where workspace_id = %s order by name",
          (workspace_id,),
      )
      return [await _view(connection, *row) for row in await cursor.fetchall()]
  ```

- **Why it matters:** Queries grow linearly with rows, sequentially on one pooled connection: list_workflows issues 5-6 per workflow, list_candidates up to 101, and publish_draft more than 20 to publish one draft. Latency grows with workspace size, and the API holds its connection for the whole loop.
- **Recommendation:** Batch child reads per list with '= any(%s)' and group in Python, as workflow_overview._experts already does, or aggregate with jsonb_agg in one statement. Pass workspace_id into _overview. Read a draft through an owned-draft query instead of get_workflow. Keep the row-to-view mapping in each module.
- **Rule check:** none
- **Verification:** confirmed. Counts read from the call chains: _view makes 5-6 statements per workflow (versions, draft, workspace, recent, chain, count), list_candidates up to 101, and publish_draft calls get_workflow three times, once inside publish_version.

### <a id="pprd-12"></a>PPRD-12: The SQL boundary is untyped: Any connections, positional rows and unchecked fetchone results

- **Severity** medium · **Dimension** types · **Effort** L · **Risk** medium · **Occurrences** 79
- **Where:**
  - [services/agent/src/autobots/application/workflow_overview.py:35-48](../../../../services/agent/src/autobots/application/workflow_overview.py#L35): ten columns read by index, out of order
  - [services/agent/src/autobots/application/memory.py:101-134](../../../../services/agent/src/autobots/application/memory.py#L101): row[0] to row[5] mapped into SearchHit
  - [services/agent/src/autobots/application/workflows.py:111-112](../../../../services/agent/src/autobots/application/workflows.py#L111): row[0] with no None check
  - [services/agent/src/autobots/application/workflow_runner.py:283](../../../../services/agent/src/autobots/application/workflow_runner.py#L283): unpacks fetchone() with no check
  - [services/agent/src/autobots/application/assignments.py:86](../../../../services/agent/src/autobots/application/assignments.py#L86): unpacks fetchone() with no check
  - [services/agent/src/autobots/application/routines.py:98](../../../../services/agent/src/autobots/application/routines.py#L98): indexes fetchone() with no check
  - [services/agent/src/autobots/persistence/rows.py:8](../../../../services/agent/src/autobots/persistence/rows.py#L8): RunRow, the only declared row type
  - [services/agent/src/autobots/contracts/adapters.py:8](../../../../services/agent/src/autobots/contracts/adapters.py#L8): run_from_row, the explicit row-to-contract mapper to copy
- **Evidence:** Excerpt from workflow_overview.py:35-42. Counts: 'connection: Any' per file by grep (79 in scope, 225 in src); positional reads by grep for name[digit] (133 in scope, 88 of them row[n]); unchecked fetchone results by reading (21 sites).

  ```python
  def _summary(row: Any) -> WorkflowExecutionSummary:
      finished = RunStatus(row[3]) in TERMINAL
      return WorkflowExecutionSummary(
          id=row[0],
          run_id=row[1],
          version=row[2],
          status=row[3],
          charged_micro_usd=int(row[7]),
  ```

- **Why it matters:** Because connection is Any, every row is Any too. mypy strict therefore sees none of the 21 places that index or unpack fetchone() without a None check: 6 are aggregates or clock reads that always return a row, and the other 15 rely on an unstated invariant. Adding or reordering a selected column silently shifts about 130 positional reads.
- **Recommendation:** Introduce a narrow typed connection in persistence/: a Db Protocol for execute and transaction that test fakes can satisfy, or psycopg.AsyncConnection[TupleRow]. Declare NamedTuple row types per query in persistence/rows.py and fetch them with psycopg's class_row and column aliases. Add fetch_required(cursor, code) for rows that must exist. Map rows to contract views in explicit *_from_row functions, like contracts/adapters.run_from_row. Adopt module by module, starting with workflow_overview and workflows.
- **Rule check:** DH-06: 'Avoid broad any/untyped dictionaries' and 'Distinguish ... persistence rows, public DTOs'. Row types live in persistence/ and are mapped explicitly to contracts, so nothing merges. SQL still owns the schema.
- **Verification:** confirmed. Recounted 79 connection: Any in scope (225 in src), 133 positional reads (88 of them row[n]) and 21 unchecked fetchone sites, 6 of them aggregates or clock reads. PTOL-13 proposes the same persistence types for the tool modules, so one change serves both.

```text
# persistence/db.py
class Db(Protocol):
    async def execute(self, query: str, params: Sequence[object] = ...) -> Cursor: ...
    def transaction(self) -> AbstractAsyncContextManager[object]: ...
# persistence/rows.py
class ExecutionSummaryRow(NamedTuple):
    id: UUID; run_id: UUID; version: int; status: str; started_at: datetime; updated_at: datetime
    created_at: datetime; charged_micro_usd: int; reserved_micro_usd: int; unreported: bool
# application/workflow_overview.py
rows = await fetch_all(conn, _EXECUTIONS, params, ExecutionSummaryRow)   # class_row underneath
return [summary_from_row(row) for row in rows]
```

### <a id="pprd-13"></a>PPRD-13: Contract types the API validates degrade to str, dict and positional tuples inside the application

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 9
- **Where:**
  - [services/agent/src/autobots/application/improvements.py:200-220](../../../../services/agent/src/autobots/application/improvements.py#L200): decide(decision: str): any value but 'reject' takes the promote path
  - [services/agent/src/autobots/contracts/improvements.py:86](../../../../services/agent/src/autobots/contracts/improvements.py#L86): the API already validates Literal['promote', 'reject']
  - [services/agent/src/autobots/application/experts.py:230](../../../../services/agent/src/autobots/application/experts.py#L230): kind: str, where the contract is Literal['direct', 'coordinator']
  - [services/agent/src/autobots/application/workflows.py:260](../../../../services/agent/src/autobots/application/workflows.py#L260): source: str, where the contract is Literal['user', 'model_proposal']
  - [services/agent/src/autobots/api/improvement_routes.py:122](../../../../services/agent/src/autobots/api/improvement_routes.py#L122): validated HeldOutTask models dumped to dicts (cases likewise at line 71)
  - [services/agent/src/autobots/application/improvements.py:383-408](../../../../services/agent/src/autobots/application/improvements.py#L383): task['goal_text'] and task['criteria'] read back from those dicts
  - [services/agent/src/autobots/application/memory.py:67-80](../../../../services/agent/src/autobots/application/memory.py#L67): replay passed as tuple[UUID, str, str] and read as replay[1], replay[2]
  - [services/agent/src/autobots/application/routines.py:261](../../../../services/agent/src/autobots/application/routines.py#L261): returns tuple[str, str | None, UUID | None]
- **Evidence:** Excerpts from improvements.py:200-202 and 216-220. Counted by reading: 4 widened Literals (decide, create_session, publish_version, rollback kind), 2 model-to-dict dumps, 3 positional tuples (memory replay, run_routine_now, read_artifact).

  ```python
  async def decide(
      connection: Any, workspace_id: UUID, candidate_id: UUID, actor_id: UUID, decision: str
  ) -> str:
          if decision == "reject":
              outcome = "rejected"
          else:
              if status != "regression_passed":
                  raise ImprovementRefused("regression_required")
  ```

- **Why it matters:** mypy can't check internal callers against the vocabularies the API enforces. In decide, a typo attempts promotion through the else branch (regression and replay checks still gate it). Positional tuples carry meaning by index across modules; cronjob_tool unpacks run_routine_now's tuple by position.
- **Recommendation:** Define the Literal aliases once (in domain or contracts), use them in application signatures, and branch exhaustively with match and assert_never. Accept the validated models (list[RegressionCase], list[HeldOutTask]), as the application already accepts ImprovementProposal and RoutineConfig, and dump them inside so the request_hash input stays identical. Replace the positional tuples with NamedTuples (ReplayProposal, OccurrenceOutcome, ArtifactContent).
- **Rule check:** contracts rule: Pydantic owns the public definitions, and the application reuses them instead of redefining them. Domain, row, DTO and UI types stay distinct.
- **Verification:** revised. Literals confirmed at contracts/improvements.py:86, contracts/experts.py:80 and 102, contracts/workflows.py:79 and the memory/skill kind; the replay task model is HeldOutTask (contracts/improvements.py:118), not ReplayTask, so the name was corrected in the location and recommendation.

### <a id="pprd-14"></a>PPRD-14: Canonical run statuses and SQL-owned status vocabularies are restated as literals

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 29
- **Where:**
  - [services/agent/src/autobots/application/assignments.py:29-31](../../../../services/agent/src/autobots/application/assignments.py#L29): TERMINAL_STATUSES, a private copy of domain TERMINAL
  - [services/agent/src/autobots/application/routines.py:302-309](../../../../services/agent/src/autobots/application/routines.py#L302): terminal statuses as a SQL literal
  - [services/agent/src/autobots/application/workflows.py:490-499](../../../../services/agent/src/autobots/application/workflows.py#L490): the terminal set plus waiting_approval, running and queued as literals
  - [services/agent/src/autobots/domain/runs.py:9-22](../../../../services/agent/src/autobots/domain/runs.py#L9): RunStatus and TERMINAL, the canonical source
  - [services/agent/src/autobots/application/routines.py:286-298](../../../../services/agent/src/autobots/application/routines.py#L286): occurrence statuses as bare strings (13 in the file)
  - [services/agent/src/autobots/application/improvements.py:109](../../../../services/agent/src/autobots/application/improvements.py#L109): candidate statuses as bare strings (13 in the file, plus one source kind)
  - [supabase/migrations/20261105000020_routines.sql:26](../../../../supabase/migrations/20261105000020_routines.sql#L26): a CHECK constraint owns the occurrence vocabulary
  - [supabase/migrations/20261105000022_improvements.sql:11-12](../../../../supabase/migrations/20261105000022_improvements.sql#L11): a CHECK constraint owns the candidate vocabulary
- **Evidence:** Counted: 3 terminal copies by reading; 26 status literals by grep (13 occurrence statuses in routines.py and 13 candidate statuses in improvements.py, whose 14th grep hit at line 190 is a memory source kind).

  ```python
  TERMINAL_STATUSES = frozenset(  # assignments.py:29-31
      {RunStatus.SUCCEEDED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value}
  )
  "on r.id = o.run_id where o.routine_id = %s and r.status not in "  # routines.py:305-306
  "('succeeded', 'failed', 'cancelled'))",
  return "not_run" if run_status in {"succeeded", "failed", "cancelled"} else "waiting"  # workflows.py:492
  ```

- **Why it matters:** A change to which run states are terminal must be found in three private copies besides domain.runs.TERMINAL. Nothing types the 26 literals of SQL-owned vocabularies, so a typo surfaces only at run time, when the CHECK constraint rejects a write.
- **Recommendation:** Use RunStatus and TERMINAL everywhere: StrEnum members compare equal to stored strings, and SQL can take 'r.status <> all(%s)' with the TERMINAL values. Mirror each SQL-owned vocabulary as a StrEnum or Literal alias in persistence/rows.py, with a db check that compares it to the CHECK constraint, so SQL stays the owner.
- **Rule check:** AGENTS.md says to use canonical states from the Option B contract, and DH-06 says not to invent a second state enum. This change removes copies, and SQL remains the owner of row vocabularies.
- **Verification:** revised. Recounted: of the 14 candidate-vocabulary grep hits in improvements.py, 'promoted' at line 190 is a memory source kind, so there are 13 candidate status literals and 29 occurrences in all, not 30.

### <a id="pprd-15"></a>PPRD-15: Product service modules also hold tool definitions and the knowledge store, which creates import cycles

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** low · **Occurrences** 6
- **Where:**
  - [services/agent/src/autobots/application/experts.py:37](../../../../services/agent/src/autobots/application/experts.py#L37): lazy import of tool_catalog, breaking a cycle through assignments (also line 65)
  - [services/agent/src/autobots/application/experts.py:53](../../../../services/agent/src/autobots/application/experts.py#L53): lazy import of tool_keys, which has no import path back
  - [services/agent/src/autobots/application/routines.py:369-370](../../../../services/agent/src/autobots/application/routines.py#L369): tool_catalog (a cycle through goal_loop and cronjob_tool) and tool_keys (no cycle)
  - [services/agent/src/autobots/application/tool_catalog.py:12-17](../../../../services/agent/src/autobots/application/tool_catalog.py#L12): the catalog imports assignments, goal_loop, workflow_runner and workflows
  - [services/agent/src/autobots/application/goal_loop.py:43-49](../../../../services/agent/src/autobots/application/goal_loop.py#L43): the loop imports tool definitions from artifacts, assignments, improvements and memory
  - [services/agent/src/autobots/application/assignments.py:10](../../../../services/agent/src/autobots/application/assignments.py#L10): assignments imports experts, closing the cycle
  - [services/agent/src/autobots/application/experts.py:10](../../../../services/agent/src/autobots/application/experts.py#L10): Experts import the improvement-review module only for skill text
  - [services/agent/src/autobots/application/routines.py:16](../../../../services/agent/src/autobots/application/routines.py#L16): routines also import active_skill_text from improvements
- **Evidence:** Counted with ruff PLC0415 on the 11 files: 6 function-level imports.

  ```python
  if not config.tool_groups:  # experts.py:35-37
      return config
  from autobots.application.tool_catalog import expert_tools_by_group
  from autobots.application.assignments import Delegation  # tool_catalog.py:12-17
  from autobots.application.goal_loop import loop_registry
  from autobots.application.workflow_runner import APPROVAL_GATE
  from autobots.application.workflows import WORKFLOW_TOOLS
  ```

- **Why it matters:** Five of the eleven modules (artifacts, assignments, improvements, memory, workflow_runner) both hold service logic and define tools the registry imports, and artifacts, improvements and memory are also called by the API. As a result experts and routines, which query the catalog, sit on both sides of it: experts to tool_catalog to assignments to experts, and routines to tool_catalog to goal_loop to cronjob_tool to routines. Six function-level imports hide these cycles, and none says why. Three of them break no cycle: the two tool_keys imports and workflow_runner.py:299, whose module is already imported at the top. Admission code also depends on improvements.py only to read active skill text.
- **Recommendation:** Move the tool definitions (publish_tool, assign_tool, PROPOSE_IMPROVEMENT, SEARCH_MEMORY, READ_OFFLOAD, APPROVAL_GATE) into tool modules that depend on the services, so the services no longer sit underneath the registry. Move knowledge heads, versions, rollback and active_skill_text into a knowledge.py that both admission and promotion import. Make the tool_keys imports top-level; the _drive import goes away with PPRD-02's injection, or moves to the top until then. Comment every lazy import that remains with the cycle it breaks. Add a small ast-based test that forbids new import cycles in application.
- **Rule check:** DH-06: explicit ownership and narrow interfaces. Only imports move; behavior, contracts and migrations don't change.
- **Verification:** revised. api/ imports only artifacts, improvements, memory, search and workflow_overview from this area, so assignments and workflow_runner are not API-called services; impact corrected. Both cycles traced through the top-level imports, and the _drive advice now matches PPRD-02's injection.

```text
application/knowledge.py       active_skill_text, activate, rollback      <- experts, routines, improvements
application/improvements.py    propose, run_regression, decide, request_replay, replay_state
application/product_tools.py   publish_tool, assign_tool, PROPOSE_IMPROVEMENT, SEARCH_MEMORY, READ_OFFLOAD
                               (imports the services; goal_loop and tool_catalog import this module, not the services)
```

### <a id="pprd-16"></a>PPRD-16: Decision logic in this area has little fast test coverage because it sits inside database functions

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 6
- **Where:**
  - [services/agent/src/autobots/application/workflows.py:490-499](../../../../services/agent/src/autobots/application/workflows.py#L490): status rule for unstarted instances; stopped_here and waiting_approval appear in no test
  - [services/agent/src/autobots/application/improvements.py:435-442](../../../../services/agent/src/autobots/application/improvements.py#L435): replay verdict rule (Decision 0016), db check only
  - [services/agent/src/autobots/application/workflow_overview.py:35-48](../../../../services/agent/src/autobots/application/workflow_overview.py#L35): duration and ledger mapping, no Python test
  - [services/agent/src/autobots/application/search.py:23-25](../../../../services/agent/src/autobots/application/search.py#L23): LIKE escaping, no Python test
  - [services/agent/src/autobots/application/improvements.py:30-36](../../../../services/agent/src/autobots/application/improvements.py#L30): authority regex, exercised only by improvement_check
  - [services/agent/src/autobots/application/workflows.py:378-386](../../../../services/agent/src/autobots/application/workflows.py#L378): tool narrowing for executions, db only
  - [services/agent/tests/test_workflows.py:377](../../../../services/agent/tests/test_workflows.py#L377): a None connection under type: ignore
  - [tests/db/major_check.py:402-407](../../../../tests/db/major_check.py#L402): the only read_execution check: not_run, running and waiting
- **Evidence:** By grep: no file under services/agent/tests imports application.search, workflow_overview, workflows, routines, improvements, memory or artifacts. These modules are exercised by tests/db/*_check.py scripts on a disposable database (improvement_check has 55 checks, assignment_check 43, workflow_run_check 38, routine_check 24) and by browser specs. read_execution is checked only by [tests/db/major_check.py:402-407](../../../../tests/db/major_check.py#L402), for not_run, running and waiting.
- **Why it matters:** Regressions in these rules surface only in the db profile (Docker and a disposable database) or in browser suites, never in the fast profile. Two of read_execution's derived statuses, stopped_here and waiting_approval, have no check at all, though they belong to the most user-visible rule here.
- **Recommendation:** Extract the pure rules (instance_views, replay_verdict(statuses), granted_tools, the execution summary mapping, _pattern and the occurrence decision) and unit-test them in services/agent/tests with plain values. Keep db checks for SQL behavior, locking and receipts. Once a Db Protocol exists, replace the None connections with a typed fake.
- **Rule check:** python-worker rule: fake models by default, and tests for stale ownership, cancellation and restart. The unit tests add speed and replace none of the db checks.
- **Verification:** revised. Corrected 'no db check calls read_execution': [tests/db/major_check.py:402-407](../../../../tests/db/major_check.py#L402) does (not_run, running, waiting), so only stopped_here and waiting_approval lack a check. No unit test imports the seven listed modules; the stop-code test location moved to PPRD-03, which already cites it.

### <a id="pprd-17"></a>PPRD-17: Seven refusal classes copy one body, and a few error paths say less than they mean

- **Severity** low · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/application/experts.py:24-29](../../../../services/agent/src/autobots/application/experts.py#L24): ExpertRefused
  - [services/agent/src/autobots/application/routines.py:43-46](../../../../services/agent/src/autobots/application/routines.py#L43): RoutineRefused; the same body appears in ArtifactUnavailable, ImprovementRefused, MemoryRefused, WorkflowRefused and _Stop
  - [services/agent/src/autobots/application/routines.py:295](../../../../services/agent/src/autobots/application/routines.py#L295): four refusal types listed just to read .code (again at line 458)
  - [services/agent/src/autobots/api/routine_routes.py:42-51](../../../../services/agent/src/autobots/api/routine_routes.py#L42): each route maps codes by suffix, per type
  - [services/agent/src/autobots/application/experts.py:69-73](../../../../services/agent/src/autobots/application/experts.py#L69): except Exception relabels any error as expert_role_unknown
  - [services/agent/src/autobots/application/improvements.py:457-458](../../../../services/agent/src/autobots/application/improvements.py#L457): propose never returns None
  - [services/agent/src/autobots/application/workflows.py:428](../../../../services/agent/src/autobots/application/workflows.py#L428): assert used for narrowing, stripped under -O
- **Evidence:** Counted with grep 'self.code = code': 7 classes in scope, 15 in services/agent/src.

  ```python
  class RoutineRefused(Exception):  # routines.py:43-46
      def __init__(self, code: str) -> None:
          super().__init__(code)
          self.code = code
  except Exception:  # experts.py:72-73
      raise ExpertRefused("expert_role_unknown") from None
  ```

- **Why it matters:** With no shared base, callers must list every type to read .code (routines.py does so twice, with four types), and each route re-maps codes by suffix. The broad catch would report a programming error as a user's unknown role. The dead branch suggests a failure that can't happen, and the assert disappears under -O.
- **Recommendation:** Add one Refused(Exception) base with code: str, taking a class default with an optional instance override, so it covers both the runs.py class-attribute style and this area's instance style. Subclasses keep their names. Catch Refused wherever any refusal blocks an occurrence. In validate_config, catch UnknownModelProfile. Delete the None check, and restructure create_execution so run_id is always bound.
- **Rule check:** DH-06: centralize error handling and expose safe typed errors. Codes and API responses stay the same.
- **Verification:** confirmed. Recounted 7 copies of the code-carrying body in scope and 15 in src; validate_config's except Exception wraps approved_role, which raises UnknownModelProfile (domain/models.py:116-120), and propose always returns a uuid4. routine_routes' _error starts at line 42, not 41.

### <a id="pprd-18"></a>PPRD-18: search.py re-implements tool_catalog.latest() with an Any-typed map

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/search.py:48-60](../../../../services/agent/src/autobots/application/search.py#L48): newest-version loop over all_descriptors, then the filter and sort
  - [services/agent/src/autobots/application/tool_catalog.py:277-282](../../../../services/agent/src/autobots/application/tool_catalog.py#L277): latest(): the same loop, typed as ToolDescriptor
- **Evidence:** Excerpt from search.py:48-51; tool_catalog.latest (277-282) is the same loop, typed as ToolDescriptor.

  ```python
  newest: dict[str, Any] = {}
  for item in all_descriptors(environ):
      if item.tool_id not in newest or item.version > newest[item.tool_id].version:
          newest[item.tool_id] = item
  ```

- **Why it matters:** Two copies of 'newest version per tool' can drift, so search could show a tool version the catalog doesn't. Any also hides ToolDescriptor's fields from mypy in the filter and sort that follow.
- **Recommendation:** Filter latest(all_descriptors(environ)) instead, and type Hit.kind as a Literal of the four kinds.
- **Rule check:** none
- **Verification:** confirmed. search.py:48-51 repeats tool_catalog.latest's loop over all_descriptors with dict[str, Any]; latest is already public.

### <a id="pprd-19"></a>PPRD-19: Two tool definitions sit away from their owners

- **Severity** low · **Dimension** structure · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/application/workflow_runner.py:54-85](../../../../services/agent/src/autobots/application/workflow_runner.py#L54): ApprovalInput and ApprovalOutput defined here; other tools' I/O lives in contracts/
  - [services/agent/src/autobots/application/tool_catalog.py:169-170](../../../../services/agent/src/autobots/application/tool_catalog.py#L169): the catalog publishes every input_model's JSON schema
  - [services/agent/src/autobots/application/memory.py:165-186](../../../../services/agent/src/autobots/application/memory.py#L165): _read_offload reads app_private.run_offloads
  - [services/agent/src/autobots/application/compaction.py:79-86](../../../../services/agent/src/autobots/application/compaction.py#L79): compaction writes that table
- **Evidence:** Excerpt from workflow_runner.py:54-58; ApprovalOutput follows at 61-64.

  ```python
  class ApprovalInput(BaseModel):
      model_config = ConfigDict(extra="forbid", frozen=True)

      node: str
      value: Any = None
  ```

- **Why it matters:** The tool catalog publishes the approval gate's input and output like any other tool contract, but a contract reviewer looking in contracts/ won't find them. Offloads are written in compaction.py and read in memory.py, so a change to their format spans two unrelated modules.
- **Recommendation:** Move ApprovalInput and ApprovalOutput to contracts/workflows.py. Move _read_offload and READ_OFFLOAD next to their writer in compaction.py, or into an offloads.py beside it. Confirm with the fast profile's drift check that the generated OpenAPI is unchanged (tool schemas are catalog data).
- **Rule check:** contracts rule: Pydantic owns the public definitions under contracts/. Generated files are regenerated, never edited.
- **Verification:** confirmed. Every other registered tool's I/O models live under contracts/ (memory, artifacts, assignments, improvements, code_tools, cronjob); run_offloads is written only at compaction.py:79 and read only at memory.py:171.

### <a id="pprd-20"></a>PPRD-20: A few names collide or hide their meaning

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 6
- **Where:**
  - [services/agent/src/autobots/application/search.py:28](../../../../services/agent/src/autobots/application/search.py#L28): search(): workspace search
  - [services/agent/src/autobots/application/memory.py:59](../../../../services/agent/src/autobots/application/memory.py#L59): search(): memory search; routes import both as bare 'search'
  - [services/agent/src/autobots/application/routines.py:340](../../../../services/agent/src/autobots/application/routines.py#L340): 'binding' holds an ExecutionBinding; 45 lines later 'binding=' means a run grant
  - [services/agent/src/autobots/application/workflows.py:382-383](../../../../services/agent/src/autobots/application/workflows.py#L382): the comprehension reuses name and version (the workflow's, used again at 393) with tool meanings
  - [services/agent/src/autobots/application/assignments.py:167-173](../../../../services/agent/src/autobots/application/assignments.py#L167): poll budget encoded as lease_seconds * 5 + 5 and 0.2
  - [services/agent/src/autobots/application/routines.py:233](../../../../services/agent/src/autobots/application/routines.py#L233): positional boolean: set_enabled(db, workspace, id, False)
  - [services/agent/src/autobots/application/routines.py:397](../../../../services/agent/src/autobots/application/routines.py#L397): _needs_model(config, connection) reverses the connection-first order
- **Evidence:** Excerpt from assignments.py:167-173.

  ```python
  for _ in range(int(delegation.lease_seconds * 5) + 5):
      lease = await claim_run(
          connection, child, worker_id="assignment", lease_seconds=delegation.lease_seconds
      )
      if lease is not None:
          return lease
      await delegation.sleep(0.2)
  ```

- **Why it matters:** Each costs a reread. Searching for 'await search(' finds two unrelated features. 'binding' means two different types within one function. The claim wait (the lease plus about a second) is implicit in two magic numbers.
- **Recommendation:** Rename the functions to search_workspace and search_memory. Call the workflow branch's result 'execution'. Name the comprehension variables tool and tool_version. Name CLAIM_POLL_SECONDS and derive the attempt count from it. Make set_enabled's flag keyword-only, and keep the connection argument first.
- **Rule check:** none
- **Verification:** confirmed. api/memory_routes.py:11 and api/search_routes.py:13 each import a bare search; cronjob_tool.py:136 passes set_enabled's flag positionally.

### <a id="pprd-21"></a>PPRD-21: Expert tool checks default to the process environment, though availability is the workspace's

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/application/experts.py:32](../../../../services/agent/src/autobots/application/experts.py#L32): expand_groups(config, environ=os.environ)
  - [services/agent/src/autobots/application/experts.py:58](../../../../services/agent/src/autobots/application/experts.py#L58): validate_config(config, environ=os.environ)
  - [services/agent/src/autobots/application/experts.py:51-55](../../../../services/agent/src/autobots/application/experts.py#L51): PK-04: the workspace's key sources decide availability
  - [services/agent/src/autobots/application/experts.py:129-131](../../../../services/agent/src/autobots/application/experts.py#L129): every caller passes the workspace's keys (also 171-173)
- **Evidence:** Excerpts from experts.py:32 and 51-52; validate_config at 58 has the same default.

  ```python
  def expand_groups(config: ExpertConfig, environ: Mapping[str, str] = os.environ) -> ExpertConfig:
  async def _workspace_keys(connection: Any, workspace_id: UUID) -> Mapping[str, str]:
      """PK-04: a tool's key may be saved for this workspace, so availability is the workspace's."""
  ```

- **Why it matters:** No caller uses the default today. A new caller that omits environ would judge availability from the server's environment alone, ignoring keys saved for the workspace and PK-04's precedence, and could refuse or accept the wrong tools.
- **Recommendation:** Make environ a required argument of both functions; tests already pass {}.
- **Rule check:** PK-04 and Decisions 0024-0025 (workspace key sources). The change enforces the documented rule.
- **Verification:** confirmed. Every caller passes environ today (experts.py:130-131 and 172-173, and the unit tests in test_tool_catalog.py and test_browsing_tool.py), so making it required changes no behavior.

## Rejected during verification

| ID | Title | Reason |
|---|---|---|
| None | | Every finding was kept. Corrections are recorded on each revised finding. |

## Not covered

Static review only. No tests, mypy or database ran. Query counts and the parent_not_running pause race come from reading the code; they were not measured or reproduced, and a blocker_check case should confirm the race before it is fixed. Ruff ran in check mode on the 11 files, with the project config and with extra rules. Neighboring modules (goal_loop, tool_gateway, tool_catalog, runs, run_projection, compaction, cronjob_tool, tool_keys, operations/logs, domain workflows/workflow_execution/runs, the contracts, the API routes, and tests under services/agent/tests and tests/db) were read only around the cited lines, to confirm boundaries and callers; their own quality belongs to other areas. The browser specs (search.spec.ts, workflow-list.spec.ts) were not read, so whether they cover expert_chain, preview_steps or search escaping is unconfirmed. Of PRD-Development-Harness.md only DH-03 to DH-06 were read. docs/engineering/option-b-contract.md was not read, because no recommendation here changes states or recovery.
