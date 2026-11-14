# Python: tools and approvals

The tools-and-approvals area is the one place a tool runs, and its durable-effect design is strong. A receipt commits under the lease before any effect. A failure is classified as failed or unknown. Readback reconciles interrupted effects. An approval binds the operation identity built from run, instance, tool version and the normalized parsed arguments, and the reviewed hash and resolved target are checked again. The cost of change sits in two functions, `ToolGateway._dispatch` (complexity 19, 15 returns) and `approval_gate` (116 lines, 18 parameters), which took in each new guardrail inline. The approval rule is restated in the catalog, and the approval and receipt state machines are bare strings written from six modules, one of them an adapter. One defect was confirmed by measurement: `search_files` runs a model-supplied regex in a thread, but CPython's `re` holds the GIL, so a catastrophic pattern freezes the worker's event loop, its lease heartbeat and the gateway's own timeout. An approved `browse_goal` call leaves no receipt, so the same call can repeat without a person for up to 24 hours. Key precedence follows the documented order but is coded in four resolvers. Types stop at the database boundary (`Any` connections, rows read by position), and gateway codes are strings matched by hand. `code_tools.search` (61 lines) was read and is acceptable as a pure, tested function. Its only issue is that `truncated` means different things in count mode depending on the target. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Project ruff passes on all 13 files and mypy strict is configured, but DH-06 bars are missed: 39 `connection: Any`, 5 blind `except Exception`, 5 narrowing `assert`s, and no enums for approval or receipt states. |
| modules | 3 | tool_gateway.py is a hub: 27 modules import it, adapters use its lease helpers, and it has a cycle with tool_uses. The catalog imports the whole run stack just to list tools. |
| size | 3 | Most functions are short, but `_dispatch` (19), `approval_gate` (116 lines, 18 parameters) and `browse` (13) concentrate the risky logic, and tool_gateway.py is 594 lines. |
| functions | 3 | Helpers are mostly single-purpose. The cronjob if-chain, re-resolving and re-validating every call, and a GET that writes rows add friction. |
| structure | 3 | 13 tool modules sit flat among 41 top-level application files under three naming forms, and tool definitions are split between application/ and adapters/ with no stated rule. |
| approach | 3 | Receipt-before-effect, fencing and readback are well designed. But the regex thread does not bound work, approvals without receipts can be reused, and the catalog rebuilds the worker registry with dummy dependencies. |
| comments | 4 | Most comments explain why and cite decisions and stories. A handful are stale, misplaced or wrong, including one that says a thread bounds a slow regex. |
| types | 2 | The database boundary is `Any` with rows read by position. Approval and receipt states and gateway codes are bare strings matched by hand, and the decision commands widen contract Literals to `str`. |
| errors | 3 | Typed refusals and the failed/unknown split are careful. Unexpected causes are dropped with no log or receipt detail, and one `suppress(BaseException)` can swallow a cancellation. |
| tests | 3 | The pure parts have focused unit tests and the DB checks cover gateway recovery. Gateway decisions reach unit tests only through a `connection=None` seam, and four risks found here have no test. |
| maintainability | 3 | The durable-effect design is sound, but central long functions and string-typed state machines make each new guardrail costly to add safely. |

## Strengths

- **One enforcement point that refuses before any effect.** [services/agent/src/autobots/application/tool_gateway.py:1](../../../../services/agent/src/autobots/application/tool_gateway.py#L1) calls itself the one place a tool runs, and `_dispatch` (322-408) refuses ungranted, unqualified, invalid, out-of-scope or unowned calls before the handler. [services/agent/src/autobots/adapters/tool_middleware.py:35-48](../../../../services/agent/src/autobots/adapters/tool_middleware.py#L35) answers every SDK tool call from `gateway.execute`. `ToolResult.for_model` (tool_gateway.py:127-135) returns only codes and validated output.
- **Receipt before effect, fenced, with an explicit failed/unknown split.** `_effect` ([services/agent/src/autobots/application/tool_gateway.py:441-490](../../../../services/agent/src/autobots/application/tool_gateway.py#L441)) commits a 'started' receipt under `hold_running` before the handler runs. `_attempt` (529-554) maps ToolFailed to failed, LeaseLost to denied and anything else to unknown. `_record` (563-594) only moves a receipt forward. `_replay` (492-527) reads back from the destination instead of resending.
- **Approvals bound to the normalized operation.** `_operation_id` ([services/agent/src/autobots/application/tool_gateway.py:209-213](../../../../services/agent/src/autobots/application/tool_gateway.py#L209)) hashes run, instance, tool, version and the canonical dump of the parsed arguments. `decide` requires the reviewed argument hash and refuses oversized arguments ([services/agent/src/autobots/application/approvals.py:273-277](../../../../services/agent/src/autobots/application/approvals.py#L273)). `_target_unchanged` refuses a changed target (tool_gateway.py:216-232). [services/agent/tests/test_tools.py:105-133](../../../../services/agent/tests/test_tools.py#L105) pins the policy version.
- **Declarative tool definitions checked at registration and by tests.** `ToolRegistry.register` ([services/agent/src/autobots/application/tool_gateway.py:142-153](../../../../services/agent/src/autobots/application/tool_gateway.py#L142)) refuses unqualified arbitrary execution and retried effects. [services/agent/tests/test_tool_catalog.py:35-54](../../../../services/agent/tests/test_tool_catalog.py#L35) checks that public fields are model fields. [services/agent/tests/test_execution_contract.py:23-29](../../../../services/agent/tests/test_execution_contract.py#L23) keeps domain/execution.py's TOOL_VERSIONS equal to the registry.
- **Ports and injected clocks keep browsing testable.** The browsing loop takes a `Page` Protocol ([services/agent/src/autobots/application/browsing_loop.py:59-67](../../../../services/agent/src/autobots/application/browsing_loop.py#L59)), a `Step` callable (142) and a `clock` (226). `browse_tool(None)` describes itself and fails before any container starts ([services/agent/src/autobots/application/browsing_tool.py:148-156](../../../../services/agent/src/autobots/application/browsing_tool.py#L148)). [services/agent/tests/test_browsing_loop.py:95](../../../../services/agent/tests/test_browsing_loop.py#L95) opens 12 behavior-named test functions, three of them parametrized, all with fakes.
- **Secrets never leave key resolution.** `KeySources` holds markers, never values ([services/agent/src/autobots/application/tool_keys.py:146-167](../../../../services/agent/src/autobots/application/tool_keys.py#L146)). `ToolKeyUnavailable` blocks fallback when a saved secret can't be unsealed (tool_keys.py:69-75, 179-180), as model-gateway.md requires. Key errors name the credential only (61-66).
- **Why-comments that cite decisions.** [services/agent/src/autobots/application/tool_gateway.py:441-442](../../../../services/agent/src/autobots/application/tool_gateway.py#L441) says why the receipt commits first, 549 why a success is recorded whoever owns the run, and 571-573 why `_record` only moves forward. [services/agent/src/autobots/application/approvals.py:176-183](../../../../services/agent/src/autobots/application/approvals.py#L176) explains receipt-aware release. [services/agent/src/autobots/application/tool_keys.py:1-9](../../../../services/agent/src/autobots/application/tool_keys.py#L1) states the precedence order.
- **Risky paths have behavior-named database checks.** [tests/db/tool_gateway_check.py:163](../../../../tests/db/tool_gateway_check.py#L163) ('a lost response is reconciled by readback, without repeating') and its check at line 100 ('a stale generation cannot use a tool'), tests/db/effect_check.py and [tests/db/approval_check.py:152](../../../../tests/db/approval_check.py#L152) ('the next model turn with changed arguments needs its own approval') exercise the gateway and approvals on disposable databases.

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [PTOL-01](#ptol-01) | high | approach | A model-supplied regex runs under the GIL and can freeze the worker's event loop | M | medium |
| [PTOL-02](#ptol-02) | high | size | `ToolGateway._dispatch` holds every guardrail in one 87-line function and recomputes the call's identity | M | medium |
| [PTOL-03](#ptol-03) | high | modules | Approval and receipt states are bare strings changed from six modules, one of them an adapter | L | high |
| [PTOL-04](#ptol-04) | medium | duplication | The approval rule is written in four places, and the version test pins only two | M | medium |
| [PTOL-05](#ptol-05) | medium | size | `approval_gate` takes 18 parameters, three of them optional although Decision 0015 requires them | M | medium |
| [PTOL-06](#ptol-06) | medium | approach | An approved `browse_goal` call can run again without a person until the approval expires | M | high |
| [PTOL-07](#ptol-07) | medium | modules | tool_gateway.py is a hub: lease fencing and the tool vocabulary live in it, and it has a cycle with tool_uses | M | low |
| [PTOL-08](#ptol-08) | medium | approach | Tool registration has no single source, so the catalog rebuilds the worker's registry with dummies | M | medium |
| [PTOL-09](#ptol-09) | medium | types | Gateway result codes are bare strings matched by hand-kept sets in four modules | M | medium |
| [PTOL-10](#ptol-10) | medium | errors | Unexpected failures leave no cause anywhere, and one cleanup can swallow a cancellation | S | low |
| [PTOL-11](#ptol-11) | medium | duplication | Run-file and plan readers are copied instead of shared | M | low |
| [PTOL-12](#ptol-12) | medium | duplication | Key precedence is coded in four resolvers, and item names live in up to three modules | M | medium |
| [PTOL-13](#ptol-13) | medium | types | The database boundary is untyped: `Any` connections and rows read by position | M | low |
| [PTOL-14](#ptol-14) | medium | functions | The cronjob handler falls through to `run`, and narrows with asserts | S | low |
| [PTOL-15](#ptol-15) | medium | types | Decision commands widen the contracts' Literals to `str` and repeat the idempotent-command skeleton | S | low |
| [PTOL-16](#ptol-16) | low | types | Type narrowing is done with assert, ignore, cast and getattr where a precise type would do | S | low |
| [PTOL-17](#ptol-17) | low | comments | A few comments are stale, misplaced or omit a non-obvious invariant | S | low |
| [PTOL-18](#ptol-18) | low | functions | Reading Keys & vars inserts rows and makes two queries per item | S | low |
| [PTOL-19](#ptol-19) | low | duplication | Small rules are copied: the browsing URL check, URL scrubbing, JSON hashing and a contract ceiling | S | low |
| [PTOL-20](#ptol-20) | low | naming | Names collide or say too little: two REPOSITORYs, a bare `Item` and an unnamed 100-character cut | S | low |
| [PTOL-21](#ptol-21) | low | structure | Tool code has no home: flat modules, three naming forms, and tools split across two layers with no rule | M | low |

### <a id="ptol-01"></a>PTOL-01: A model-supplied regex runs under the GIL and can freeze the worker's event loop

- **Severity** high · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/code_tools.py:114-117](../../../../services/agent/src/autobots/application/code_tools.py#L114): _search moves search() to a thread, with a comment saying this bounds a slow pattern
  - [services/agent/src/autobots/application/code_tools.py:41](../../../../services/agent/src/autobots/application/code_tools.py#L41): re.compile on the model's pattern; each line is matched by pattern.search at 67
  - [services/agent/src/autobots/contracts/code_tools.py:19](../../../../services/agent/src/autobots/contracts/code_tools.py#L19): pattern: any regular expression up to 200 characters
  - [services/agent/src/autobots/application/tool_gateway.py:417](../../../../services/agent/src/autobots/application/tool_gateway.py#L417): the only bound is asyncio.wait_for around the handler (10 s for search_files)
  - [services/agent/src/autobots/application/goal_loop.py:340](../../../../services/agent/src/autobots/application/goal_loop.py#L340): the lease heartbeat _keep_lease is a task on the same event loop
  - [services/agent/src/autobots/application/worker_leases.py:12](../../../../services/agent/src/autobots/application/worker_leases.py#L12): DEFAULT_LEASE_SECONDS = 60.0
  - [services/agent/src/autobots/operations/worker.py:128](../../../../services/agent/src/autobots/operations/worker.py#L128): the worker's status beat shares the loop too
- **Evidence:** CPython's `re` engine holds the GIL for a whole `pattern.search(line)` call. Measured with Python 3.12.16 in a scratch script that touched no project file: `asyncio.wait_for(asyncio.to_thread(...), 0.2)` around `re.compile('(a+)+$').search('a'*25 + 'b')` returned only after 1.90 s, and the event loop ticked once in that time. The same wrapper around `time.sleep(1.9)` returned at 0.20 s with 18 ticks. For this pattern, each added character doubles the time. Run files hold up to 256,000 characters.

  ```python
  async def _search(arguments: SearchFilesInput, context: ToolContext) -> SearchFilesOutput:
      files = await _latest_files(context)
      # In a thread, so the gateway's timeout bounds a slow pattern instead of the event loop.
      return await asyncio.to_thread(search, files, arguments)
  ```

- **Why it matters:** One nested-quantifier pattern, written by mistake or steered by third-party text in a run file, stops every task in the worker process. `_keep_lease` can't renew the 60 s lease, the worker's status beat stops, and the 10 s tool timeout can't fire until the match ends. The run is handed to another worker, and the stalled process is fenced only when it wakes. The comment tells maintainers the opposite of what happens.
- **Recommendation:** Run `search` where it can be stopped: a child process (stdlib `multiprocessing`, spawn context, with `search` kept in a module with light imports) that is terminated when the tool's time runs out and reported as `ToolFailed('search_timeout')`. This keeps the search pure Python, as Decision 0017 C7 requires. A linear-time engine (`google-re2`) or the `regex` package's `timeout=` would also bound it, but each is a new compiled dependency that needs its own story and a check against C7. Correct the comment. Add a unit test with a pathological pattern that asserts the call ends within the limit while a ticker task keeps running.
- **Rule check:** DH-06: keep blocking work off the async event loop and bound timeouts. SP-012: leases must keep renewing. Decision 0017 C7 (search is pure Python, with no rg binary) holds with the stdlib child process. A compiled regex engine would be a new dependency under the delivery rule (story-scoped, pinned and recorded) and would need checking against C7.
- **Verification:** revised. Re-measured inline under python3.12 -I with no file written: wait_for(to_thread(...), 0.2) raised TimeoutError only after 1.90 s while a 0.1 s ticker stalled, against 0.20 s for time.sleep(1.9); a to_thread worker also can't be cancelled, so it keeps scanning lines after the timeout. Added Decision 0017 C7 to the recommendation and rule check.

```text
application/bounded.py
  async def run_in_child(fn, *args, seconds: float) -> T
      # one spawned process; await its result off the loop; terminate() on timeout; raise BoundExceeded
application/code_tools.py
  async def _search(arguments, context):
      files = await _latest_files(context)
      try: return await run_in_child(search, files, arguments, seconds=SEARCH_SECONDS)
      except BoundExceeded: raise ToolFailed('search_timeout') from None
tests/test_code_tools.py
  test_a_catastrophic_pattern_times_out_and_the_loop_keeps_running
```

### <a id="ptol-02"></a>PTOL-02: `ToolGateway._dispatch` holds every guardrail in one 87-line function and recomputes the call's identity

- **Severity** high · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/tool_gateway.py:322-408](../../../../services/agent/src/autobots/application/tool_gateway.py#L322): _dispatch: complexity 19, 15 returns, 18 branches (ruff)
  - [services/agent/src/autobots/application/tool_gateway.py:349-398](../../../../services/agent/src/autobots/application/tool_gateway.py#L349): 50-line inline approval block: condition, target, review detail, gate, target recheck
  - [services/agent/src/autobots/application/tool_gateway.py:355](../../../../services/agent/src/autobots/application/tool_gateway.py#L355): _operation_id(scope, tool, parsed) at 355, 364, 379 and 396, again at 439; _hash(parsed) also at 383 and 438
  - [services/agent/src/autobots/application/tool_gateway.py:399](../../../../services/agent/src/autobots/application/tool_gateway.py#L399): metered test written inline, while tool_uses.is_metered (tool_uses.py:186) has no caller
  - [services/agent/src/autobots/application/tool_uses.py:91-161](../../../../services/agent/src/autobots/application/tool_uses.py#L91): begin_use (71 lines) looks the tool up and validates the arguments again (97-104)
  - [services/agent/src/autobots/application/tool_uses.py:190](../../../../services/agent/src/autobots/application/tool_uses.py#L190): complete_use (7 parameters) looks the tool up a third time (204-205)
  - [services/agent/src/autobots/application/tool_uses.py:95](../../../../services/agent/src/autobots/application/tool_uses.py#L95): `if connection is None: return None`, a seam for unit tests
  - [services/agent/tests/test_market_data.py:132](../../../../services/agent/tests/test_market_data.py#L132): unit tests reach the pure checks through execute(None, ...)
- **Evidence:** The guards run in a fixed order (grant, registry, qualification, validation, path grants, ownership, Expert-only, approval, metered budget), each ending in `return _denied(...)`. The field comments cite Decision 0025 V7, Decision 0026 C3 and PRD-Studio GH-06 for parts of the inline approval block.

  ```python
  reviewing = ToolContext(connection, scope, _operation_id(scope, tool, parsed))
  ...
  if tool.review_detail is not None and not await _has_approval(
      connection, _operation_id(scope, tool, parsed)
  ...
      operation_id=_operation_id(scope, tool, parsed),
  ```

- **Why it matters:** This is the single enforcement point for every tool call, so each new rule lands in the riskiest function. A reader must confirm by eye that five identity computations agree, and that agreement is what binds an approval to its effect. Unit tests reach the pure checks only by passing `connection=None` and relying on those checks running first. Reordering the guards would crash those tests instead of failing them.
- **Recommendation:** Resolve the call once into a frozen `Call` (tool, parsed arguments, argument hash, operation ID), then run named steps. The pure `resolve` step covers grant, registry, qualification, validation and path grants, is tested directly, and replaces the `connection is None` seams. Pass the `Call` to `begin_use`, `complete_use`, `_effect` and `_read` so each call is looked up and validated once. Keep the guard order, the codes and `APPROVAL_POLICY_VERSION` unchanged. Prove behavior with the existing `db` checks (tool_gateway_check, approval_check, effect_check).
- **Rule check:** SP-013: completed arguments are validated before any effect; the sketch keeps validation, ownership, approval and budget in their current order. Decision 0015: no rule or reason text changes, so the policy version stays.
- **Verification:** confirmed. Ruff reports C901 19, PLR0911 15 and PLR0912 18 at tool_gateway.py:322; _operation_id is called at 355, 364, 379, 396 and 439, is_metered has no caller, and five unit tests call execute(None, ...).

```text
@dataclass(frozen=True)
class Call:  # built once per dispatch
    tool: ToolDefinition; parsed: BaseModel; argument_hash: str; operation_id: str
def resolve(registry, scope, name, arguments) -> Call | ToolResult        # pure, unit-tested
async def admission_refusal(conn, scope, call) -> str | None              # ownership, expert-only
async def hold_for_approval(conn, scope, call) -> str | None              # target, review detail, gate, recheck
async def admit_budget(conn, scope, call, use) -> str | None              # metered calls
async def _dispatch(...): resolve -> admission -> approval if needed -> budget -> _effect | _read
```

### <a id="ptol-03"></a>PTOL-03: Approval and receipt states are bare strings changed from six modules, one of them an adapter

- **Severity** high · **Dimension** modules · **Effort** L · **Risk** high · **Occurrences** 11
- **Where:**
  - [services/agent/src/autobots/application/tool_gateway.py:447](../../../../services/agent/src/autobots/application/tool_gateway.py#L447): receipt inserted as 'started'; reopened at 472; moved by _record at 583 and 590
  - [services/agent/src/autobots/application/tool_gateway.py:563](../../../../services/agent/src/autobots/application/tool_gateway.py#L563): _record: six positional parameters and two near-identical UPDATEs
  - [services/agent/src/autobots/application/reconciliation.py:94](../../../../services/agent/src/autobots/application/reconciliation.py#L94): an operator's ruling sets 'succeeded' or 'failed'
  - [services/agent/src/autobots/application/recovery.py:34](../../../../services/agent/src/autobots/application/recovery.py#L34): worker loss sets 'unknown'
  - [services/agent/src/autobots/application/approvals.py:185](../../../../services/agent/src/autobots/application/approvals.py#L185): a stale approval goes back to 'pending'; 'expired' at 208; decided at 299
  - [services/agent/src/autobots/application/runs.py:451](../../../../services/agent/src/autobots/application/runs.py#L451): cancelling sets 'withdrawn'
  - [services/agent/src/autobots/adapters/github_pulls.py:142](../../../../services/agent/src/autobots/adapters/github_pulls.py#L142): adapter sends a request back to 'pending' with its own `interval '1 day'` and event, and writes tool_receipts.reconciled_at directly (137-139)
  - [services/agent/src/autobots/application/approvals.py:315](../../../../services/agent/src/autobots/application/approvals.py#L315): DECIDED is a tuple of strings; no ApprovalStatus or ReceiptStatus enum exists
- **Evidence:** rg for 'approval_requests set status|tool_receipts set status|into app_private.tool_receipts' finds 11 statements in tool_gateway.py (4), reconciliation.py, recovery.py, approvals.py (3), runs.py and adapters/github_pulls.py. The values are literals: 'started', 'succeeded', 'failed', 'unknown' and 'pending', 'approved', 'rejected', 'expired', 'withdrawn'. `ToolOutcome` overlaps the receipt values but adds 'denied' and lacks 'started'. The adapter's re-request copies approvals.py:184-199 with a hard-coded day instead of `DEFAULT_TTL_SECONDS`.
- **Why it matters:** No module owns either state machine. A change such as consuming an approval after use (PTOL-06) must reach several modules, including an adapter, and nothing catches a missed writer. The adapter's copy hard-codes the one-day TTL that approvals.py takes from DEFAULT_TTL_SECONDS: the same value today, from a second source. SP-010 asks for these state machines to be documented separately from run status. Today they exist only as scattered SQL.
- **Recommendation:** Add `ReceiptStatus` and `ApprovalStatus` StrEnums in the domain, with their permitted transitions and tests. Make a new `application/receipts.py` the only writer of receipt status (start, reopen, record, mark_unknown, rule); `_record` becomes `receipts.record(context, operation_id, outcome)`. Make approvals.py the only writer of approval status (request, return_to_review, expire, decide, withdraw). runs.py, recovery.py, reconciliation.py and the GitHub adapter call these. Document both tables beside SP-010's run table. Stored values stay the same, so no migration is needed. A CHECK constraint, if wanted, is a forward migration.
- **Rule check:** SP-010 (document separate state machines for tool attempts and approvals) and DH-06 (explicit enums; keep tool-attempt and approval states distinct). Values are unchanged and applied migrations are untouched; any constraint is a new forward migration.
- **Verification:** revised. Recounted 11 status writes in six modules with the same pattern (github_pulls.py:138 sets only reconciled_at and isn't counted); the adapter's TTL equals DEFAULT_TTL_SECONDS today, so the impact now calls it a second source, not a different value.

```text
domain/effects.py         ReceiptStatus(StrEnum), ApprovalStatus(StrEnum), RECEIPT_MOVES, APPROVAL_MOVES
application/receipts.py   start / reopen / record / mark_unknown / rule          # sole tool_receipts writer
application/approvals.py  request / return_to_review / expire / decide / withdraw  # sole approval writer
adapters/github_pulls.py  return_to_review -> approvals.return_to_review(conn, operation_id, detail)
runs.apply_command(CANCEL) -> approvals.withdraw_pending(conn, run_id)
tests/test_effect_states.py  every permitted move accepted, every other move refused
```

### <a id="ptol-04"></a>PTOL-04: The approval rule is written in four places, and the version test pins only two

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 4
- **Where:**
  - [services/agent/src/autobots/application/tool_gateway.py:349-353](../../../../services/agent/src/autobots/application/tool_gateway.py#L349): inline condition that decides whether a call waits
  - [services/agent/src/autobots/application/tool_gateway.py:189](../../../../services/agent/src/autobots/application/tool_gateway.py#L189): _approval_rule
  - [services/agent/src/autobots/application/tool_gateway.py:198](../../../../services/agent/src/autobots/application/tool_gateway.py#L198): _approval_reason
  - [services/agent/src/autobots/application/tool_catalog.py:173-175](../../../../services/agent/src/autobots/application/tool_catalog.py#L173): the catalog recomputes the condition
  - [services/agent/src/autobots/application/tool_catalog.py:203-205](../../../../services/agent/src/autobots/application/tool_catalog.py#L203): and derives the always/by_action/never label
  - [services/agent/src/autobots/application/tool_gateway.py:183-186](../../../../services/agent/src/autobots/application/tool_gateway.py#L183): comment: bump the version when the condition changes; a unit test pins it
  - [services/agent/tests/test_tools.py:105-133](../../../../services/agent/tests/test_tools.py#L105): the pin test calls _approval_rule and _approval_reason only
  - [services/agent/src/autobots/application/tool_gateway.py:78-107](../../../../services/agent/src/autobots/application/tool_gateway.py#L78): six approval fields scattered among ToolDefinition's 31 flat fields
- **Evidence:** The catalog's lines above (tool_catalog.py:173-175 and 204) restate the gateway's own condition (tool_gateway.py:349-353), which reads the same three fields. Only `_approval_rule` and `_approval_reason` are pinned with APPROVAL_POLICY_VERSION.

  ```python
  approval = tool.approval_required or (
      tool.operation_class is OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE
  )
  ...
  "always" if approval else "by_action" if tool.approval_when is not None else "never"
  ```

- **Why it matters:** Decision 0015 says the policy version is only as honest as its bumps. A change to the condition passes the pin test, and the Tools page could then show 'never' for a tool the gateway holds, or the reverse.
- **Recommendation:** Group the six approval fields into one `ApprovalPolicy` value on `ToolDefinition`, with `applies(tool, parsed)`, `rule`, `reason` and `label`. The gateway, the catalog and the pin test all call it. Extend the pin test to cover the condition for each operation class and for `approval_when`.
- **Rule check:** Decision 0015 (the policy version names the rules) and Decision 0026 C9 (the catalog's by_action label). No rule or text changes, so APPROVAL_POLICY_VERSION stays approval-policy/2.
- **Verification:** confirmed. Decision 0015 says the version 'is only as honest as its bumps'; test_tools.py:105-133 pins _approval_rule and _approval_reason but neither the condition at tool_gateway.py:349-353 nor the catalog's condition and label at tool_catalog.py:173-175 and 203-205.

```text
@dataclass(frozen=True)
class ApprovalPolicy:
    always: bool = False; when: Callable[[Any], bool] | None = None; reason: str | None = None
    resource_target: ...; target_resolver: ...; review_detail: ...
    def applies(self, tool, parsed) -> bool
    def rule(self, tool) -> str; def text(self, tool) -> str
    def label(self, tool) -> Literal['always', 'by_action', 'never']
```

### <a id="ptol-05"></a>PTOL-05: `approval_gate` takes 18 parameters, three of them optional although Decision 0015 requires them

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/approvals.py:87-202](../../../../services/agent/src/autobots/application/approvals.py#L87): 116 lines, 18 parameters, 9 returns
  - [services/agent/src/autobots/application/approvals.py:102-104](../../../../services/agent/src/autobots/application/approvals.py#L102): scope, policy_version and policy_rule default to None
  - [services/agent/src/autobots/application/tool_gateway.py:374-392](../../../../services/agent/src/autobots/application/tool_gateway.py#L374): the only caller builds all 16 keyword arguments inline
  - [services/agent/src/autobots/application/approvals.py:153-159](../../../../services/agent/src/autobots/application/approvals.py#L153): event plus _enter_wait for a new request
  - [services/agent/src/autobots/application/approvals.py:184-200](../../../../services/agent/src/autobots/application/approvals.py#L184): the same event plus wait again for a stale approval
  - [services/agent/src/autobots/application/approvals.py:169-178](../../../../services/agent/src/autobots/application/approvals.py#L169): receipt check, repeated in tool_gateway._target_unchanged
  - [services/agent/src/autobots/application/tool_gateway.py:220-225](../../../../services/agent/src/autobots/application/tool_gateway.py#L220): the same 'not failed means it may have been sent' test
- **Evidence:** One transaction block locks the request, creates it (reading the requester from the run), decides among pending, approved, rejected and expired, reads the receipt, and reopens a stale approval. The 'approval.requested' event plus `_enter_wait` is written twice. `scope`, `policy_version` and `policy_rule` default to None, though the only caller always passes them.
- **Why it matters:** The optional fields let a future caller store a request without the scope snapshot, policy version and rule that Decision 0015 requires. The decision table (status, expiry, scope match, receipt state) can be exercised only through a database.
- **Recommendation:** Pass one frozen `ApprovalProposal` built by the gateway, with the Decision 0015 fields required. Split the body into `_request_review`, `_reopen` and a pure `gate_decision(row, scope_hash, receipt)` that returns release, wait, re-request or a refusal code, and unit-test that table. Share one `_receipt_state` reader with `_target_unchanged`.
- **Rule check:** Decision 0015's fields become required. SP-013's binding (operation identity, argument hash, scope hash, expiry) is unchanged.
- **Verification:** confirmed. approval_gate has one caller (tool_gateway.py:374, connection plus 16 keyword arguments); ruff reports PLR0913 18 and PLR0911 9; the event-plus-wait pair appears at 153-158 and 190-199.

```text
@dataclass(frozen=True)
class ApprovalProposal: operation_id, tool_id, tool_version, operation_class, argument_hash,
    arguments, scope_hash, scope (required), policy: PolicyStamp(version, rule, reason),
    resource_target, review_detail
def gate_decision(row: RequestRow | None, scope_hash: str, receipt: ReceiptState | None) -> Gate  # pure
async def approval_gate(conn, run: RunRef, proposal, ttl=DEFAULT_TTL_SECONDS) -> str | None
    # -> _request_review | _reopen | _enter_wait | refusal code
```

### <a id="ptol-06"></a>PTOL-06: An approved `browse_goal` call can run again without a person until the approval expires

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** high · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/approvals.py:166-201](../../../../services/agent/src/autobots/application/approvals.py#L166): approved, no receipt, not expired: released (return None at 201)
  - [services/agent/src/autobots/application/approvals.py:298-303](../../../../services/agent/src/autobots/application/approvals.py#L298): a decision sets expires_at to now plus 24 hours
  - [services/agent/src/autobots/domain/tools.py:69-71](../../../../services/agent/src/autobots/domain/tools.py#L69): EFFECTFUL excludes arbitrary_execution, so browse_goal gets no receipt
  - [services/agent/src/autobots/application/tool_gateway.py:406-408](../../../../services/agent/src/autobots/application/tool_gateway.py#L406): non-effect calls go to _read, which writes no receipt
  - [services/agent/src/autobots/application/browsing_tool.py:173](../../../../services/agent/src/autobots/application/browsing_tool.py#L173): approval_required=True; its description (165) says 'A person approves every call.'
  - [services/agent/src/autobots/application/tool_gateway.py:209-213](../../../../services/agent/src/autobots/application/tool_gateway.py#L209): operation ID: run, instance, tool, version, argument hash; only workflow steps set instance
- **Evidence:** For effects, the receipt makes an approval single-use: a repeated call finds the receipt and replays it. `browse_goal` is `arbitrary_execution`, outside `EFFECTFUL`, so it never gets a receipt. If the model repeats the identical call in the same run, the operation ID is the same, and `approval_gate` finds the request approved, with no receipt and not expired. It returns None, so a second browser session and its paid model calls start with no new approval. Only the metered cap (20 per root run tree) and the run budget limit this. No check in tests/db/browse_goal_check.py repeats an approved call.
- **Why it matters:** Decision 0018 B6 and Decision 0020 L5 require approval on every browse_goal call. Any future read tool that requires approval inherits the same reuse.
- **Recommendation:** Consume an approval when it releases a call that leaves no receipt: record `consumed_at` (forward migration) in the releasing transaction, and treat a consumed approval as needing a new request. A crash after release then asks again, which fails safe. Add a db check that repeats an approved browse_goal call and expects approval_pending. Do this inside the approvals owner proposed in PTOL-03.
- **Rule check:** Strengthens a guardrail: Decisions 0018 B6 and 0020 L5 (approval on every call) and SP-013 (a replayed approval cannot authorize more work). Any new column is a forward migration.
- **Verification:** confirmed. Traced: browse_goal is arbitrary_execution, so _dispatch sends it to _read with no receipt, and approval_gate's approved branch returns None at 201 for the same operation ID until expiry; no loop-level duplicate-call check exists, and no browse_goal_check case repeats an approved call.

### <a id="ptol-07"></a>PTOL-07: tool_gateway.py is a hub: lease fencing and the tool vocabulary live in it, and it has a cycle with tool_uses

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** low · **Occurrences** 27
- **Where:**
  - [services/agent/src/autobots/application/tool_gateway.py:256-298](../../../../services/agent/src/autobots/application/tool_gateway.py#L256): ownership_refusal, hold_lease, NotRunning, hold_running: run-lease fencing
  - [services/agent/src/autobots/application/tool_gateway.py:310](../../../../services/agent/src/autobots/application/tool_gateway.py#L310): function-level import of begin_use and complete_use
  - [services/agent/src/autobots/application/tool_gateway.py:402](../../../../services/agent/src/autobots/application/tool_gateway.py#L402): function-level import of admit_metered
  - [services/agent/src/autobots/application/tool_uses.py:17-23](../../../../services/agent/src/autobots/application/tool_uses.py#L17): tool_uses imports ToolDefinition, ToolScope, ToolRegistry, ToolResult and hold_lease from the gateway
  - [services/agent/src/autobots/adapters/loop_middleware.py:64](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L64): an adapter imports ownership_refusal from the gateway
  - [services/agent/src/autobots/adapters/browser_executor.py:443](../../../../services/agent/src/autobots/adapters/browser_executor.py#L443): another adapter does the same with a local import
  - [services/agent/src/autobots/application/worker_leases.py:12](../../../../services/agent/src/autobots/application/worker_leases.py#L12): the existing lease module, where fencing belongs
- **Evidence:** `rg -l 'from autobots.application.tool_gateway import'` lists 27 modules. Eight of them (tools, tool_uses, plans, artifacts, assignments, workflow_runner, adapters/loop_middleware, adapters/browser_executor) import the lease helpers. The gateway needs begin_use, complete_use and admit_metered from tool_uses, which needs the gateway's types, so the gateway imports them inside functions.
- **Why it matters:** Any edit to the gateway invalidates a large share of the package. Adapters reach into the gateway for a lease check, and the cycle forces function-level imports that hide the dependency. The file is 594 lines partly because it holds three concerns.
- **Recommendation:** Move ToolScope, ToolContext, ToolDefinition, ToolResult, ToolRegistry, ToolFailed and NotDelivered (lines 20-176) to `application/tool_definitions.py`. Move ownership_refusal, hold_lease, hold_running and NotRunning to `worker_leases.py`. If needed, re-export them from tool_gateway for a short transition, then update importers. tool_gateway then imports tool_uses at the top and keeps dispatch, effects and receipts, under 400 lines.
- **Rule check:** DH-06: explicit ownership and narrow interfaces. No behavior change, and the DH-03 layer layout is unchanged.
- **Verification:** confirmed. Recounted 27 importing modules in src (14 more in tests); an AST scan finds exactly the eight lease-helper importers named; tool_gateway imports tool_uses only inside execute (310) and _dispatch (402).

### <a id="ptol-08"></a>PTOL-08: Tool registration has no single source, so the catalog rebuilds the worker's registry with dummies

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/application/goal_loop.py:162-197](../../../../services/agent/src/autobots/application/goal_loop.py#L162): loop_registry: a hard-coded tuple plus factories that need limits, an object store and delegation
  - [services/agent/src/autobots/application/tool_catalog.py:57-79](../../../../services/agent/src/autobots/application/tool_catalog.py#L57): catalog_registry: `_never` drive, `object_store=object()`, and APPROVAL_GATE and browse_tool added by hand
  - [services/agent/src/autobots/application/workflow_runner.py:304-305](../../../../services/agent/src/autobots/application/workflow_runner.py#L304): workflow runs add APPROVAL_GATE
  - [services/agent/src/autobots/application/worker_inference.py:330-344](../../../../services/agent/src/autobots/application/worker_inference.py#L330): the worker adds browse_tool according to the workspace switch
  - [services/agent/tests/test_execution_contract.py:23-29](../../../../services/agent/tests/test_execution_contract.py#L23): a third registry built with dummy dependencies
  - [services/agent/tests/test_tool_catalog.py:23-32](../../../../services/agent/tests/test_tool_catalog.py#L23): the parity test compares catalog_registry with itself
  - [services/agent/src/autobots/application/tool_catalog.py:12-17](../../../../services/agent/src/autobots/application/tool_catalog.py#L12): the catalog imports goal_loop, assignments, run_usage, workflow_runner and workflows
- **Evidence:** catalog_registry's docstring says it is built as the worker builds it, but the extras (APPROVAL_GATE, browse_tool) are mirrored by hand. test_every_registered_tool_appears_once_and_nothing_else derives both sides from `catalog_registry()`. tool_catalog.py is 348 lines covering registry assembly, JSON-schema walking, guides, descriptors, filtering and grant availability.
- **Why it matters:** A tool added to or removed from a worker's extras can be missing from the catalog, or wrongly listed in it, and no test fails. PRD-Tool-Catalog TC-01 says the catalog derives from the registry the worker runs. The dummy `object()` dependency breaks as soon as a factory touches its dependency at build time.
- **Recommendation:** Add `application/tool_set.py` with one `tool_definitions(runtime: ToolRuntime | None, ...)` used by every site. Follow browse_tool's pattern: with no runtime, a definition still describes itself, and its handler fails before any effect. loop_registry, the workflow runner, the worker, the catalog and test_execution_contract all call it. Move the schema walking (`_SCHEMA_KEYS`, `_type`, `_fields`) to `tool_schema.py`, which brings tool_catalog.py under 300 lines. Add one parity test: the catalog's registered set equals the set a qualified worker builds, workflow extras included.
- **Rule check:** PRD-Tool-Catalog TC-01 (the catalog derives from the worker's registry). AB-02 and Decision 0025 V6 are kept: browse_goal is registered only while qualified and switched on, and the switch stays an input.
- **Verification:** confirmed. catalog_registry adds APPROVAL_GATE and browse_tool by hand (tool_catalog.py:66-79), as workflow_runner.py:304-306 and worker_inference.py:330-344 do separately (that range corrected from 338-343), and test_tool_catalog.py:23-32 derives both sides of its comparison from catalog_registry().

```text
application/tool_set.py
  @dataclass(frozen=True) class ToolRuntime: limits, object_store, delegation, browsing
  def tool_definitions(runtime: ToolRuntime | None, *, workflow=False, browsing_ready=False)
      -> tuple[ToolDefinition, ...]
application/tool_schema.py   _SCHEMA_KEYS, schema_type(), fields()          # from tool_catalog
application/tool_catalog.py  describe, describe_planned, all_descriptors, tool_catalog, filters
```

### <a id="ptol-09"></a>PTOL-09: Gateway result codes are bare strings matched by hand-kept sets in four modules

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 22
- **Where:**
  - [services/agent/src/autobots/application/tool_gateway.py:316](../../../../services/agent/src/autobots/application/tool_gateway.py#L316): whether complete_use is fenced depends on result.code == 'approval_pending'
  - [services/agent/src/autobots/application/tool_gateway.py:119-125](../../../../services/agent/src/autobots/application/tool_gateway.py#L119): ToolResult.code: str | None
  - [services/agent/src/autobots/application/goal_loop.py:116](../../../../services/agent/src/autobots/application/goal_loop.py#L116): NOT_OURS
  - [services/agent/src/autobots/application/workflow_runner.py:87-97](../../../../services/agent/src/autobots/application/workflow_runner.py#L87): STOPS
  - [services/agent/src/autobots/adapters/loop_middleware.py:76-87](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L76): REPAIRABLE and STOPPING
  - [services/agent/src/autobots/application/approvals.py:159](../../../../services/agent/src/autobots/application/approvals.py#L159): gate codes returned as literals (159, 163, 165, 168, 181, 200, 202)
- **Evidence:** Reading every `_denied(`, ToolResult code and gate return in tool_gateway.py and approvals.py gives 22 distinct codes. goal_loop, workflow_runner and loop_middleware each keep their own frozenset of the codes that stop a loop or are 'not ours'.

  ```python
  # A call now waiting for a person released the lease in its own approval gate.
  waiting = result.code == "approval_pending"
  await complete_use(
      connection, scope, self.registry, use, name, result, fenced=not waiting
  )
  ```

- **Why it matters:** A typo or a renamed code in any set silently changes control flow (stop or continue, fenced or unfenced write), and type checking can't help. Each new code means finding every set by search.
- **Recommendation:** Define `GatewayCode(StrEnum)` in domain/tools.py for the codes the gateway produces, with the classifications (STOPS_LOOP, NOT_OURS, REPAIRABLE) declared beside it and imported by the loops. Make `ToolResult.code` `GatewayCode | str`, since handlers keep their own codes. StrEnum values equal the stored strings, so events, receipts and the generated contract don't change.
- **Rule check:** Contracts are untouched because StrEnum serializes as today; no generated file is edited.
- **Verification:** confirmed. Recounted 22 distinct codes from _denied calls, ToolResult codes and gate returns in tool_gateway.py and approvals.py. PPRD-03 in py-product proposes the same vocabulary from the workflow side, so plan the two together.

### <a id="ptol-10"></a>PTOL-10: Unexpected failures leave no cause anywhere, and one cleanup can swallow a cancellation

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 8
- **Where:**
  - [services/agent/src/autobots/application/tool_gateway.py:542-544](../../../../services/agent/src/autobots/application/tool_gateway.py#L542): an exception from an effect becomes 'unknown' with no failure detail
  - [services/agent/src/autobots/application/tool_gateway.py:514-515](../../../../services/agent/src/autobots/application/tool_gateway.py#L514): a failing readback is treated as 'nothing found'
  - [services/agent/src/autobots/application/tool_gateway.py:422-423](../../../../services/agent/src/autobots/application/tool_gateway.py#L422): a read's exception becomes 'tool_failed'
  - [services/agent/src/autobots/application/tool_gateway.py:372-373](../../../../services/agent/src/autobots/application/tool_gateway.py#L372): a review-detail exception becomes 'review_unavailable'
  - [services/agent/src/autobots/application/tool_uses.py:103-104](../../../../services/agent/src/autobots/application/tool_uses.py#L103): `except Exception` around validation, where ValidationError is meant
  - [services/agent/src/autobots/application/browsing_tool.py:142](../../../../services/agent/src/autobots/application/browsing_tool.py#L142): suppress(BaseException) around `await watcher`
  - [services/agent/src/autobots/application/browsing_tool.py:133](../../../../services/agent/src/autobots/application/browsing_tool.py#L133): watcher.result() re-raises the watcher's own error inside the except block
  - [services/agent/src/autobots/application/browsing_tool.py:100](../../../../services/agent/src/autobots/application/browsing_tool.py#L100): sweep failures suppressed silently (cdp.close too, at 139)
- **Evidence:** None of the 13 modules logs anything. operations/logs.py provides `log_event` with type-only exception fields and secret redaction, and [services/agent/src/autobots/operations/worker.py:142-147](../../../../services/agent/src/autobots/operations/worker.py#L142) uses it with `error=type(error).__name__`.

  ```python
  except Exception:
      await _record(context, operation_id, "unknown", None)
      return ToolResult(ToolOutcome.UNKNOWN, "outcome_unknown", operation_id=operation_id)
  ```

- **Why it matters:** An operator asked to rule on an unknown effect (reconciliation.py) has no record of what failed, and repeated provider errors go unseen. A cancellation that arrives while the browse handler awaits the watcher is discarded, and the handler can return normally. A failing watcher replaces the browsing error with an unrelated exception, which is reported as 'tool_failed'.
- **Recommendation:** Record `failure_detail=type(error).__name__` on 'unknown' and 'failed' receipts. Log `tool.outcome_unknown` and `tool.readback_failed` with tool_id, operation_id and the exception type through `log_event`. Catch `ValidationError` in begin_use. Replace `suppress(BaseException)` with a shared `cancel_and_wait(task)` that suppresses the watcher's CancelledError but re-raises when `asyncio.current_task().cancelling()` is set. Check `watcher.exception()` before calling `result()`.
- **Rule check:** DH-06: preserve causes in private logs, expose safe typed errors, and propagate cancellation after cleanup. Logging only the type follows operations/logs.py and keeps secrets and model text out.
- **Verification:** confirmed. None of the 13 modules logs; the five blind except Exception and the suppress(BaseException) are at the cited lines. Under Python 3.12, wait_for runs the handler in the caller's task, so a CancelledError swallowed at browsing_tool.py:142-143 lets the handler return its result normally.

### <a id="ptol-11"></a>PTOL-11: Run-file and plan readers are copied instead of shared

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** low · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/application/tools.py:45-49](../../../../services/agent/src/autobots/application/tools.py#L45): latest version of a run file, in the v1 read
  - [services/agent/src/autobots/application/tools.py:116-125](../../../../services/agent/src/autobots/application/tools.py#L116): _latest: the same query with media_type
  - [services/agent/src/autobots/application/code_tools.py:120-129](../../../../services/agent/src/autobots/application/code_tools.py#L120): _latest: the same query again, returning a different tuple
  - [services/agent/src/autobots/application/tools.py:56-66](../../../../services/agent/src/autobots/application/tools.py#L56): _existing_save: readback by operation_id
  - [services/agent/src/autobots/application/code_tools.py:173-184](../../../../services/agent/src/autobots/application/code_tools.py#L173): _written: the same readback; a reconciled patch loses `replacements`
  - [services/agent/src/autobots/application/tool_uses.py:64-88](../../../../services/agent/src/autobots/application/tool_uses.py#L64): served_task re-runs latest_plan's and completed_tasks' SQL on untyped dicts
  - [services/agent/src/autobots/application/plans.py:107-123](../../../../services/agent/src/autobots/application/plans.py#L107): latest_plan returns typed PlanTask; completed_tasks returns the done IDs
  - [services/agent/src/autobots/application/tools.py:69](../../../../services/agent/src/autobots/application/tools.py#L69): write_run_file, which code_tools also uses, lives in the 'first tool set' module
- **Evidence:** The 'latest version of a run file' query appears three times with different column lists, and two private helpers both named `_latest` return different tuples. `_existing_save` and `_written` are the same readback. `served_task` repeats the SQL of `latest_plan` and `completed_tasks` word for word, walks `task.get('depends_on', [])` on raw JSON, and restates the readiness rule that plans.py:231 writes as `set(task.depends_on) <= done`.
- **Why it matters:** A change to run-file storage (a column, a retention rule, a path policy) must find every copy, and the code tools already differ: a reconciled patch reports `replacements=None`. Task attribution can drift from plan readiness.
- **Recommendation:** Create `application/run_files.py` (latest, latest_all, by_operation, write) and use it from tools.py and code_tools.py, giving reconciled and fresh writes the same result shape. In `served_task`, call `plans.latest_plan`, `plans.completed_tasks` and a new `plans.ready_tasks(plan, done)`, keeping begin_use tolerant: latest_plan validates every task, so a stored plan that fails validation must still not stop the use from being recorded. tools.py then holds only tool definitions.
- **Rule check:** SP-013: readback by operation ID stays the proof that a write committed; otherwise none.
- **Verification:** revised. Confirmed the three latest-version queries, the two identical operation-ID readbacks and replacements=None on a reconciled patch (CodeFileWritten defaults it); served_task deliberately tolerates malformed plan JSON inside begin_use, so the recommendation now keeps that.

### <a id="ptol-12"></a>PTOL-12: Key precedence is coded in four resolvers, and item names live in up to three modules

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 4
- **Where:**
  - [services/agent/src/autobots/application/tool_keys.py:128](../../../../services/agent/src/autobots/application/tool_keys.py#L128): resolve_item: for availability
  - [services/agent/src/autobots/application/tool_keys.py:184](../../../../services/agent/src/autobots/application/tool_keys.py#L184): resolve_tool_key: Tavily and Jina at call time; reads the environment by requirement.variables[0]
  - [services/agent/src/autobots/application/tool_keys.py:200](../../../../services/agent/src/autobots/application/tool_keys.py#L200): resolve_value: for values
  - [services/agent/src/autobots/application/tool_keys.py:225](../../../../services/agent/src/autobots/application/tool_keys.py#L225): github_target: token, with a literal 'GITHUB_TOKEN' at 234
  - [services/agent/src/autobots/application/tool_keys.py:57-58](../../../../services/agent/src/autobots/application/tool_keys.py#L57): TOOL_KEY_PROVIDERS: its keys gate resolve_tool_key's saved-secret lookup (190), and its values repeat ITEMS' variables and are never read
  - [services/agent/src/autobots/application/tool_keys.py:122](../../../../services/agent/src/autobots/application/tool_keys.py#L122): saved_providers, and key_source at 142: no callers in services, tests or scripts
  - [services/agent/src/autobots/application/tool_key_settings.py:49-52](../../../../services/agent/src/autobots/application/tool_key_settings.py#L49): validation chosen by item name
  - [services/agent/src/autobots/adapters/tavily.py:36](../../../../services/agent/src/autobots/adapters/tavily.py#L36): TAVILY_API_KEY again in the adapter's KeyRequirement; likewise jina.py:30 and github_issues.py:31-32, 43
- **Evidence:** The documented order is implemented correctly: Settings, then the process environment, then .env files in MP-03 order, and a saved secret that can't be unsealed blocks fallback. But four functions each restate 'settings first, then environment' for one kind of item, and two more (saved_providers, key_source) have no callers. TAVILY_API_KEY and JINA_API_KEY appear in ITEMS, as the never-read values of TOOL_KEY_PROVIDERS and in the adapters. GITHUB_TOKEN appears in ITEMS, github_target and adapters/github_issues.py. AUTOBOTS_BROWSER_EXECUTOR appears in ITEMS and browsing_tool.py:46. The repository regex is in tool_keys.py:30 and github_issues.py:43, and refusal text is a third name-keyed table (api/settings_routes.py:184-194).
- **Why it matters:** Adding or renaming a key means editing up to five modules. Availability reads `ITEMS[...].variable` and call time reads `requirement.variables[0]`, so the two can read different variables with no failing test.
- **Recommendation:** Make `Item` the only description of a key or value: variable, kind, validator and refusal text. Build the adapters' KeyRequirements from ITEMS. Replace the four resolvers with one `resolve(item, saved, environ, unseal) -> Resolved(source, value)` that keeps `ToolKeyUnavailable` blocking fallback, and drop TOOL_KEY_PROVIDERS together with resolve_tool_key. Delete saved_providers and key_source now, since nothing calls them.
- **Rule check:** model-gateway.md: honor the configured key precedence; a nonblank invalid higher-priority key blocks fallback. The Decision 0024 and 0025 order is unchanged, and availability still never unseals or returns a secret.
- **Verification:** revised. TOOL_KEY_PROVIDERS is still read by resolve_tool_key (tool_keys.py:190), which adapters/provider_http.py:33-36 calls for Tavily and Jina, so it can't be deleted on its own; saved_providers and key_source have no callers. Note and recommendation corrected.

### <a id="ptol-13"></a>PTOL-13: The database boundary is untyped: `Any` connections and rows read by position

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** low · **Occurrences** 39
- **Where:**
  - [services/agent/src/autobots/application/tool_gateway.py:57](../../../../services/agent/src/autobots/application/tool_gateway.py#L57): ToolContext.connection: Any; 39 `connection: Any` in the 13 files
  - [services/agent/src/autobots/application/tool_uses.py:282-307](../../../../services/agent/src/autobots/application/tool_uses.py#L282): 22 columns mapped as item[0] to item[21] (list_tool_uses, 60 lines)
  - [services/agent/src/autobots/application/approvals.py:344-370](../../../../services/agent/src/autobots/application/approvals.py#L344): 24 names zipped onto a 24-column select, returned as dict[str, Any]
  - [services/agent/src/autobots/api/approval_routes.py:78-108](../../../../services/agent/src/autobots/api/approval_routes.py#L78): read back by string keys with no type check
  - [services/agent/src/autobots/application/reconciliation.py:42](../../../../services/agent/src/autobots/application/reconciliation.py#L42): UnknownOperation(row[0], row[1], row[2], row[3])
  - [services/agent/src/autobots/application/tool_gateway.py:500](../../../../services/agent/src/autobots/application/tool_gateway.py#L500): `status, result = await cursor.fetchone()` unpacks a possible None
  - [services/agent/src/autobots/persistence/rows.py:8](../../../../services/agent/src/autobots/persistence/rows.py#L8): the RunRow TypedDict shows the intended pattern; it isn't used here
  - [services/agent/src/autobots/application/tool_keys.py:190](../../../../services/agent/src/autobots/application/tool_keys.py#L190): `connection is not None` seams for tests (also 205, 231 and tool_uses.py:95)
- **Evidence:** rg counts 39 `connection: Any` in these files and 208 in application/. Results are read by index. In list_approvals, `zip(..., strict=True)` catches a count mismatch but not two swapped columns. `(await cursor.fetchone())[0]` appears at approvals.py:68, tool_uses.py:138 and 178, tools.py:88 and reconciliation.py:53.
- **Why it matters:** mypy strict checks nothing on any query. A reordered SELECT, a misspelled row key in the API or a None row shows up only at runtime, usually in the db profile. The None-connection seams exist so unit tests can pass `None`, which mixes test support into production paths.
- **Recommendation:** Introduce a narrow `DbConnection` Protocol, or an alias of psycopg's AsyncConnection, in persistence, and use it in these signatures. Read list results with psycopg `class_row` into row dataclasses or TypedDicts in persistence/rows.py (ToolUseRow, ApprovalRow, UnknownOperationRow), mapped to DTOs explicitly as RunRow is. Add a `fetch_one(cursor)` helper that raises a named error on None.
- **Rule check:** DH-06 (no broad any or untyped dictionaries) and SP-009 (rows, DTOs and domain types stay distinct, and adapters convert explicitly). Rows stay separate from the contract views.
- **Verification:** confirmed. Recounted 39 connection: Any in scope, 208 in application/ and 225 in src; list_tool_uses maps item[0] to item[21] and list_approvals zips 24 names onto 24 selected columns. PPRD-12 proposes the same persistence types for the product services, so one change serves both.

### <a id="ptol-14"></a>PTOL-14: The cronjob handler falls through to `run`, and narrows with asserts

- **Severity** medium · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/cronjob_tool.py:85-151](../../../../services/agent/src/autobots/application/cronjob_tool.py#L85): handle: 67 lines, one if-chain over seven actions
  - [services/agent/src/autobots/application/cronjob_tool.py:143-149](../../../../services/agent/src/autobots/application/cronjob_tool.py#L143): any action not matched above runs the routine now
  - [services/agent/src/autobots/application/cronjob_tool.py:107](../../../../services/agent/src/autobots/application/cronjob_tool.py#L107): assert narrowing (also 119 and 122)
  - [services/agent/src/autobots/application/cronjob_tool.py:168](../../../../services/agent/src/autobots/application/cronjob_tool.py#L168): approval_when: action != 'list'
  - [services/agent/src/autobots/application/cronjob_tool.py:76-79](../../../../services/agent/src/autobots/application/cronjob_tool.py#L76): _target builds the approval label from the action
  - [services/agent/src/autobots/contracts/cronjob.py:54-62](../../../../services/agent/src/autobots/contracts/cronjob.py#L54): _FIELDS: the per-action field table
- **Evidence:** Excerpt from cronjob_tool.py:139-146, dedented. Knowledge of each action lives in four places: the contract's `_FIELDS`, this if-chain, `approval_when` and `_target`.

  ```python
  if action == "remove":
      await remove_routine(connection, workspace, routine)
      return CronjobOutput(action=action, status="removed", routine_id=routine)

  async def ready(workspace_id: UUID) -> str:
      return await check(connection, workspace_id)

  status, reason, run_id = await run_routine_now(connection, workspace, routine, ready)
  ```

- **Why it matters:** An eighth action added to `CronjobAction` and `_FIELDS` would start a paid run instead of failing, and mypy can't flag it. The asserts are stripped under `python -O`. If one failed, the effect path would record the outcome as unknown instead of invalid.
- **Recommendation:** Keep one tool with seven actions (Decision 0026 C1), but dispatch with `match arguments.action:`, an explicit `case 'run':` and a `case _: assert_never(action)` arm, or with a `dict[CronjobAction, handler]` whose completeness a test checks. Replace the asserts with per-action narrowing that raises `ToolFailed('invalid_arguments')`.
- **Rule check:** Decision 0026 C1 (one tool, seven actions) and C3 (every action but list is approved) are kept; only the internal dispatch changes.
- **Verification:** confirmed. The chain has no branch for run, so any unmatched action reaches run_routine_now; the contract validator (contracts/cronjob.py:74-81) makes today's asserts unreachable, so the risk is the next action, not today's calls.

### <a id="ptol-15"></a>PTOL-15: Decision commands widen the contracts' Literals to `str` and repeat the idempotent-command skeleton

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/application/approvals.py:251-255](../../../../services/agent/src/autobots/application/approvals.py#L251): `decision: str`; anything but 'approve' is a rejection
  - [services/agent/src/autobots/application/reconciliation.py:64-71](../../../../services/agent/src/autobots/application/reconciliation.py#L64): `outcome: str`; anything but 'delivered' reopens the effect for another attempt (also 92)
  - [services/agent/src/autobots/contracts/approvals.py:115](../../../../services/agent/src/autobots/contracts/approvals.py#L115): the API's Literal['approve', 'reject']
  - [services/agent/src/autobots/contracts/run_commands.py:71](../../../../services/agent/src/autobots/contracts/run_commands.py#L71): the API's Literal['delivered', 'not_delivered']
  - [services/agent/src/autobots/application/approvals.py:256-262](../../../../services/agent/src/autobots/application/approvals.py#L256): scope tuple, fingerprint, existing_receipt; store_receipt at 309
  - [services/agent/src/autobots/application/reconciliation.py:69-75](../../../../services/agent/src/autobots/application/reconciliation.py#L69): the same skeleton; store_receipt at 104
  - [services/agent/src/autobots/application/reconciliation.py:36-37](../../../../services/agent/src/autobots/application/reconciliation.py#L36): the run-tree CTE is written three times here (36, 47, 78) and once in recovery.py (50)
- **Evidence:** The routes validate both values with Literals; the application signatures then accept any string. 14 application commands take `idempotency_key: str`. These two rebuild the (workspace, actor, operation, target, key) scope and fingerprint by hand, and their 7 and 9 parameters are the PLR0913 leads at approvals.py:244 and reconciliation.py:56.

  ```python
  wanted = "approved" if decision == "approve" else "rejected"
  ...
  status = "succeeded" if outcome == "delivered" else "failed"
  ```

- **Why it matters:** An internal caller passing the stored status 'approved' records a rejection. One passing 'Delivered' rules the effect not delivered, which allows a fresh attempt and possibly a duplicate external effect. A copied idempotency skeleton is easy to get subtly wrong.
- **Recommendation:** Type the parameters with the contracts' Literals, or domain enums, and match exhaustively. Introduce a `CommandKey(workspace_id, actor_id, idempotency_key)` parameter object and an `idempotent(connection, key, operation, target, payload)` helper around existing_receipt and store_receipt. That shortens both parameter lists, and the other 12 commands can adopt it when touched. Write the run-tree CTE once, as a named constant.
- **Rule check:** Pydantic contracts own the public values (contracts.md), and the application accepts them unchanged. SP-012 reconciliation semantics are unchanged.
- **Verification:** confirmed. Literals confirmed at contracts/approvals.py:115 and contracts/run_commands.py:71; internal callers (operations/browse_trial.py:246 and the db checks) pass valid values today. The third CTE is at line 78, not 77. PPRD-08 proposes the same receipt helper for the product commands; plan one helper.

### <a id="ptol-16"></a>PTOL-16: Type narrowing is done with assert, ignore, cast and getattr where a precise type would do

- **Severity** low · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 8
- **Where:**
  - [services/agent/src/autobots/application/browsing_loop.py:169-180](../../../../services/agent/src/autobots/application/browsing_loop.py#L169): action_of returns tuple[str, BaseModel], losing the action type
  - [services/agent/src/autobots/application/browsing_loop.py:258](../../../../services/agent/src/autobots/application/browsing_loop.py#L258): assert isinstance(action, _Action)
  - [services/agent/src/autobots/application/browsing_loop.py:269](../../../../services/agent/src/autobots/application/browsing_loop.py#L269): `action.url  # type: ignore[attr-defined]` in the else branch
  - [services/agent/src/autobots/application/tool_catalog.py:112](../../../../services/agent/src/autobots/application/tool_catalog.py#L112): `# type: ignore[arg-type]` because direction is typed str
  - [services/agent/src/autobots/application/tool_catalog.py:217](../../../../services/agent/src/autobots/application/tool_catalog.py#L217): cast(list[GrantSiteName], ...); grant_sites returns list[str]
  - [services/agent/src/autobots/application/tool_catalog.py:135](../../../../services/agent/src/autobots/application/tool_catalog.py#L135): getattr(environ, 'sources', {}) on a Mapping
  - [services/agent/src/autobots/application/tool_keys.py:146-160](../../../../services/agent/src/autobots/application/tool_keys.py#L146): KeySources.sources is only annotated; key_sources sets it after construction
  - [services/agent/src/autobots/application/tool_keys.py:173](../../../../services/agent/src/autobots/application/tool_keys.py#L173): assert item.credential is not None
- **Evidence:** `browse` (61 lines, complexity 13) branches on isinstance and falls back to `# type: ignore` for GoTo. The catalog ignores a Literal mismatch it could declare. `_key_source` depends on an attribute that only `key_sources()` sets. Ruff's S101 finds 5 asserts in scope, cronjob's 3 included.
- **Why it matters:** Each bypass hides the next mismatch. A new browsing action would reach the ignore silently, and a KeySources built any other way raises AttributeError or quietly reports 'environment'.
- **Recommendation:** Make `action_of` return `OpenLink | GoTo | Scroll | Finish` and use `match`, which also splits browse into a per-action step. Type `_fields(direction: Literal['input', 'output'])`. Give `grant_sites` a return type the contract accepts without a cast: a grant-site Literal alias the domain owns, checked equal to `GrantSiteName` by a test, or one typed mapping from GrantSite to it. Make KeySources a frozen Mapping that takes `sources` in its constructor, and pass the sources to `_key_source` explicitly. Narrow `item.credential` with an `if` that raises.
- **Rule check:** DH-06: keep typing exceptions narrow and documented. Decision 0020's one-action rule (BM-03) is unchanged.
- **Verification:** revised. grant_sites (domain/tool_catalog.py:115) appends GrantSite values to a list[str]; returning list[GrantSite] would still need a cast against the contract's Literal under mypy, so the recommendation now names a typed alias or mapping instead.

```text
Action = OpenLink | GoTo | Scroll | Finish
def action_of(message) -> tuple[str, Action] | None
async def _step(page, state, view, action: Action) -> Stopped | None:
    match action:
        case Finish(): return 'done'
        case Scroll(): ...
        case OpenLink(number=n): target = view.links[n - 1].url
        case GoTo(url=u): target = u
async def browse(...): loop -> limits -> reply -> _step
```

### <a id="ptol-17"></a>PTOL-17: A few comments are stale, misplaced or omit a non-obvious invariant

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/application/tool_gateway.py:104-109](../../../../services/agent/src/autobots/application/tool_gateway.py#L104): the TU-04 comment for public fields sits above review_detail, cut off from its field by GH-06's comment
  - [services/agent/src/autobots/application/tools.py:1](../../../../services/agent/src/autobots/application/tools.py#L1): 'Nothing else exists', though the module also holds read_run_file v2, read_csv and the shared write_run_file
  - [services/agent/src/autobots/application/tool_uses.py:33](../../../../services/agent/src/autobots/application/tool_uses.py#L33): claims the gateway's normalization but hashes the raw arguments, not the parsed ones
  - [services/agent/src/autobots/application/approvals.py:258-311](../../../../services/agent/src/autobots/application/approvals.py#L258): decide commits an expiry, then refuses after the transaction (expired_row), with no why-comment
  - [services/agent/src/autobots/application/tool_gateway.py:158-159](../../../../services/agent/src/autobots/application/tool_gateway.py#L158): versions() keeps whichever version was registered last; undocumented
- **Evidence:** Most comments in these files explain why and cite decisions; these five mislead or omit an invariant. The thread comment at code_tools.py:116 is covered by PTOL-01.

  ```python
  # Top-level fields a run's screens may show, TU-04. The default shows none.
  # PRD-Studio GH-06: what the reviewer sees beyond the arguments, read before the approval
  # request exists. It may read the destination, never write it.
  review_detail: Callable[[Any, "ToolContext"], Awaitable[dict[str, Any]]] | None = None
  public_input_fields: tuple[str, ...] = ()
  ```

- **Why it matters:** A maintainer may simplify decide by raising inside the transaction, which rolls back the expiry and the pause. They may join tool uses to approvals on input_digest, expecting it to equal the argument hash, or treat tools.py as the whole built-in tool set.
- **Recommendation:** Move the TU-04 line onto public_input_fields. Rewrite tools.py's docstring, or move write_run_file as PTOL-11 proposes. Say that input_digest covers what the model sent, before validation, so it differs from the argument hash. Add a one-line why to decide's deferred refusal. Document versions() as 'last registered', or make it return the highest version.
- **Rule check:** Keeps the practice of citing decisions and stories in comments; each comment is judged on its own.
- **Verification:** revised. Dropped the TOOL_KEY_PROVIDERS comment (tool_keys.py:57): the dict is read by resolve_tool_key on the Tavily and Jina adapters' behalf, through adapters/provider_http.py, so 'kept for the adapters' is accurate. The other five comments are as described; occurrences 6 to 5.

### <a id="ptol-18"></a>PTOL-18: Reading Keys & vars inserts rows and makes two queries per item

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/tool_key_settings.py:64-77](../../../../services/agent/src/autobots/application/tool_key_settings.py#L64): _version inserts the settings row if it is missing, then selects
  - [services/agent/src/autobots/application/tool_key_settings.py:86-101](../../../../services/agent/src/autobots/application/tool_key_settings.py#L86): status() calls _version for each of the five items
  - [services/agent/src/autobots/api/settings_routes.py:217-222](../../../../services/agent/src/autobots/api/settings_routes.py#L217): GET /settings/keys-and-vars, for every member
  - [supabase/migrations/20261108000051_tool_provider_keys.sql:12](../../../../supabase/migrations/20261108000051_tool_provider_keys.sql#L12): version defaults to 0
- **Evidence:** status() makes two queries for saved items, then an insert and a select for each item: 12 queries per GET, which can write five rows. Each item's resolve_item may also read the .env files from disk on the event loop.
- **Why it matters:** A read path needs insert privilege and does N+1 work, and a failed write turns a read into an error.
- **Recommendation:** Read every version with one `select provider, version ... where workspace_id = %s` and treat a missing row as version 0, the column default, so results are unchanged. Keep the insert in save and remove, which lock the row.
- **Rule check:** none
- **Verification:** confirmed. status() runs saved_items (2 queries) and _version (insert plus select) for each of the five ITEMS, so 12 statements per GET; migration 20261108000051 line 12 defaults version to 0.

### <a id="ptol-19"></a>PTOL-19: Small rules are copied: the browsing URL check, URL scrubbing, JSON hashing and a contract ceiling

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 9
- **Where:**
  - [services/agent/src/autobots/application/browsing_tool.py:68-76](../../../../services/agent/src/autobots/application/browsing_tool.py#L68): permitted() repeats the contract's https, no-credentials and within-domains check
  - [services/agent/src/autobots/contracts/browsing.py:44-48](../../../../services/agent/src/autobots/contracts/browsing.py#L44): the contract's copy in BrowseGoalInput._inside
  - [services/agent/src/autobots/application/browsing_loop.py:163-166](../../../../services/agent/src/autobots/application/browsing_loop.py#L163): bare() drops the query and fragment
  - [services/agent/src/autobots/application/tool_uses.py:41-45](../../../../services/agent/src/autobots/application/tool_uses.py#L41): _scrub() does the same
  - [services/agent/src/autobots/application/tool_gateway.py:178-180](../../../../services/agent/src/autobots/application/tool_gateway.py#L178): _hash: compact canonical JSON SHA-256
  - [services/agent/src/autobots/application/approvals.py:54-56](../../../../services/agent/src/autobots/application/approvals.py#L54): scope_hash: default separators; stored with each request and pinned by test_tools.py:131
  - [services/agent/src/autobots/application/tool_uses.py:32-38](../../../../services/agent/src/autobots/application/tool_uses.py#L32): input_digest: compact with default=str (also tool_catalog.catalog_digest at 264)
  - [services/agent/src/autobots/application/browsing_tool.py:172](../../../../services/agent/src/autobots/application/browsing_tool.py#L172): `300 + GRACE_SECONDS + 30` repeats max_seconds le=300 (contracts/browsing.py:36)
- **Evidence:** There are four canonical-JSON hashes in scope (`_hash`, `scope_hash`, `input_digest`, `catalog_digest`), plus runs.request_hash, using two separator styles. There are two URL scrubbers and two copies of the https-within-domains rule, and the browsing timeout restates the contract ceiling as a literal: nine copies in all.
- **Why it matters:** The egress check in the tool and the one in the contract can diverge silently. Raising the browsing ceiling without changing the timeout would cut off long approved calls.
- **Recommendation:** Add `plain_https_within(url, domains)` to contracts/browsing and use it in both places. Use one `strip_query(url)` and one `canonical_sha256(value, *, separators=COMPACT)`; scope_hash passes its current separators explicitly, because stored approvals are compared against it. Define `MAX_SECONDS = 300` once and use it in both the Field and the timeout.
- **Rule check:** Decision 0015: the stored scope hash must keep its format, so scope_hash passes its separators explicitly. The AB-03 egress rules are unchanged.
- **Verification:** revised. Recounted 9 rather than 8: four canonical-JSON hashes in scope, two URL scrubbers, two copies of the https-within-domains rule and one restated ceiling.

### <a id="ptol-20"></a>PTOL-20: Names collide or say too little: two REPOSITORYs, a bare `Item` and an unnamed 100-character cut

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 6
- **Where:**
  - [services/agent/src/autobots/application/tool_keys.py:30](../../../../services/agent/src/autobots/application/tool_keys.py#L30): REPOSITORY is a compiled regex, imported by tool_key_settings
  - [services/agent/src/autobots/application/browsing_tool.py:41](../../../../services/agent/src/autobots/application/browsing_tool.py#L41): REPOSITORY is the repository root Path
  - [services/agent/src/autobots/application/tool_key_settings.py:21-28](../../../../services/agent/src/autobots/application/tool_key_settings.py#L21): imports ITEMS, REPOSITORY, SWITCH_VALUES and Item as bare names
  - [services/agent/src/autobots/application/tool_keys.py:35](../../../../services/agent/src/autobots/application/tool_keys.py#L35): public `Item`, one key or value of Keys & vars
  - [services/agent/src/autobots/application/tool_uses.py:124](../../../../services/agent/src/autobots/application/tool_uses.py#L124): `name[:100]` three times (124, 153, 239) with no named limit
- **Evidence:** tool_key_settings.py:21-28 imports `ITEMS, REPOSITORY, SWITCH_VALUES, Item` from tool_keys, where `REPOSITORY` reads like a value but is a pattern, while browsing_tool.py's `REPOSITORY` is a directory. tool_uses.py cuts the tool name to 100 characters in three places.
- **Why it matters:** Search results and imports mislead: the same name is a regex in one module and a path in its sibling, and a cut repeated three times can drift apart.
- **Recommendation:** Rename to intent: REPOSITORY_PATTERN and REPOSITORY_ROOT, and KeyItem for Item. Name the cut once (TOOL_ID_CHARS = 100) and use it at all three places.
- **Rule check:** none
- **Verification:** revised. Dropped `_read`, `_latest`, `checked`, `latest` and `Saved` as taste or as covered by PTOL-11 (`Saved` is module-local); kept the REPOSITORY collision, the bare `Item` that tool_key_settings imports and the three `name[:100]` cuts.

### <a id="ptol-21"></a>PTOL-21: Tool code has no home: flat modules, three naming forms, and tools split across two layers with no rule

- **Severity** low · **Dimension** structure · **Effort** M · **Risk** low · **Occurrences** 17
- **Where:**
  - [services/agent/src/autobots/application/browsing_tool.py:23-34](../../../../services/agent/src/autobots/application/browsing_tool.py#L23): an application module built from four adapters
  - [services/agent/src/autobots/application/browsing_loop.py:280-316](../../../../services/agent/src/autobots/application/browsing_loop.py#L280): adapter glue (StepRequest, StepResponse, admitted_steps) beside the pure loop
  - [services/agent/src/autobots/adapters/tavily.py:36](../../../../services/agent/src/autobots/adapters/tavily.py#L36): external-client tools are defined in adapters/
  - [services/agent/src/autobots/application/tools.py:1](../../../../services/agent/src/autobots/application/tools.py#L1): tools.py, code_tools.py, cronjob_tool.py, browsing_tool.py and tool_*.py
  - [services/agent/src/autobots/application/code_tools.py:1](../../../../services/agent/src/autobots/application/code_tools.py#L1): '*_tools' form
  - [services/agent/src/autobots/application/cronjob_tool.py:1](../../../../services/agent/src/autobots/application/cronjob_tool.py#L1): '*_tool' form
  - [services/agent/src/autobots/application/tool_gateway.py:1](../../../../services/agent/src/autobots/application/tool_gateway.py#L1): the gateway among 41 top-level application files
- **Evidence:** `rg -l 'ToolDefinition('` finds 10 application modules and 7 adapter modules. The GitHub, Tavily, Jina and market tools live in adapters/, but browse_goal, which drives Docker and CDP through four adapters, lives in application/. application/ already has one subpackage, credentials/.
- **Why it matters:** Nothing says where a new tool goes or what its module is called, so readers search two layers, and application and adapters depend on each other in both directions.
- **Recommendation:** State the placement rule in docs/engineering: in-process tools in application/tools/, external-client tools in adapters/. Group the gateway, definitions, registry, uses, catalog, grants, keys, key settings, approvals and receipts in an `application/tools/` subpackage, as with credentials/. Move browsing_tool.py and admitted_steps to adapters/browsing.py and keep the pure loop in application.
- **Rule check:** DH-03 fixes only the top-level layers; a subpackage inside application/ keeps it, as credentials/ does.
- **Verification:** revised. Recounted: application/ has 41 top-level files (46 with credentials/), not 46 flat modules; ToolDefinition( appears in 10 application and 7 adapter modules, and browsing_loop.py imports adapters.loop_middleware, so the layers do depend on each other both ways.

## Rejected during verification

| ID | Title | Reason |
|---|---|---|
| None | | Every finding was kept. Corrections are recorded on each revised finding. |

## Not covered

This review is static. The only runtime evidence is the regex timing, measured with a standalone scratch script under Python 3.12.16, not inside the project's worker. Its scratch scripts sit in the session scratchpad, and the ruff output in .checks/reviews/review-2026-11-12-09-52-30/py-tools/. No other finding was exercised. I read the tests/db checks only for the names of their cases, not run or reviewed in depth, since they belong to db-tests. I read only the cited parts of PRD-Development-Harness.md (DH-03, DH-06), option-b-contract.md (sections 6-7), metrics.md, goal_loop.py, worker_inference.py, plans.py, runs.py, workflow_runner.py, recovery.py, loop_middleware.py, browser_executor.py, github_pulls.py, github_issues.py, operations/logs.py, operations/worker.py, api/approval_routes.py, api/settings_routes.py, domain/execution.py and the unit tests for the catalog, keys, code, cronjob and browsing tools. The project hook refused one read-only search because its pattern named the provider master-key file. I repeated it without that term, so the default key-file path constant in tool_keys.py was not compared with other modules. I did not run mypy, and per the ground rules I did not run scripts/verify.py.
