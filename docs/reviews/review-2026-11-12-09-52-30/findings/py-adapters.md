# Python: adapters

The 22 adapter files (4,103 lines) pass the service's ruff, format and mypy-strict gates and contain practices worth spreading: failure codes that say whether an external write certainly did not happen, injectable transports and resolvers tested with sockets blocked, per-attempt credentials, a fail-closed OpenRouter factory, one URL guard and a fenced checkpointer. The cost sits in three hotspots. Each tool module is one factory closure of 68 to 226 lines. github_pull_request_tool's complexity of 37 is the sum of 13 nested functions, the largest of which is 62 lines. Request, status and reply handling is re-implemented for each provider and has drifted: three refused-status sets, two UnclearReply classes, six client constructors with different proxy and timeout defaults, and untyped JSON replies. loop_middleware.py (674 lines) holds model-route and stop policy that application code imports back; its _admitted_call passes state through four lists and treats any ValueError as a lost lease. browser_executor.py packs five concerns into one file covered by the qualification fingerprint. Two defects were reproduced in memory. First, the live-result tap raises on malformed save_artifact arguments, which stops a paid reply as partial_stream or uncertain_acceptance, depending on when the tap flushes. Second, a date-only `since` crashes github_list_pull_requests. Reading also found three more problems: the PR connector resets approvals with inline SQL outside a transaction and without the lease, the URL guard lets httpx resolve a name again after checking it (certificate verification, not the guard, is what stops a rebound request), and the worker converts reported charges with float arithmetic. Apart from those two reproductions, the review is static. [Back to the review](../README.md)

Area `py-adapters`, revision `156534da0bd5b19417f05d313077d767804b175b`, run `2026-11-12-09-52-30`. Every finding below was re-opened at its cited lines and recounted by an adversarial verifier.

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Ruff, format and mypy strict pass on all 22 files. But some DH-06 requirements are met unevenly (lease-fenced writes, trust-boundary validation, client lifecycles, exact money), and the rule path scopes miss loop_middleware. |
| modules | 2 | Approval state is written from a GitHub adapter, application imports loop policy back from adapters, and a 500-line fingerprinted browser module all add recurring cost. models/, url_guard and checkpoints are cohesive. |
| size | 3 | There are seven factory closures of 68 to 226 lines and two files over 300 lines, though each nested handler is small (the largest, open_pull_request, is 62 lines). |
| functions | 3 | Handlers are mostly single-purpose. _admitted_call passes state through four mutable lists, and open_pull_request chains six steps. |
| structure | 3 | The flat adapters/ folder mixes providers, LangChain middleware, a Docker executor and a sidecar. DH-03's graphs/ and adapters/persistence/ don't exist. |
| approach | 3 | Per-attempt keys, injected transports and certainty-aware failures are strong. Against that, the URL guard resolves DNS twice, clients are built six ways, and GitHub reads resolve the target per request. |
| comments | 4 | Module docstrings cite decisions and comments explain why. Two docstrings promise more than the code delivers (result_stream, url_guard). |
| types | 3 | mypy strict passes, but middleware hooks, connections and every provider reply are Any, and ToolDefinition keywords are passed through dict[str, Any] splats. |
| errors | 3 | Typed codes with explicit certainty are a model for the repository. They are undercut by a tap that turns parse errors into uncertain calls, ValueError used as a signal, and drifting status maps. |
| tests | 3 | Every adapter test uses fake transports with sockets blocked. There are no fast tests for the PR connector, the gateway middleware or storage, and the parsers have no malformed-input cases. |
| maintainability | 3 | Small, well-commented helpers surround three hotspots (the PR connector, the loop middleware and the browser executor) that need planned refactors. |

## Strengths

- **Failure codes that state certainty.** Effectful adapters raise ToolFailed only when the destination proves nothing happened, and leave every other outcome unknown for a readback. See [services/agent/src/autobots/adapters/github_issues.py:44-45](../../../../services/agent/src/autobots/adapters/github_issues.py#L44) and 180-186 (connection never opened, the refused set, any other status is UnclearReply) and [github_pulls.py:175-184](../../../../services/agent/src/autobots/adapters/github_pulls.py#L175). Readbacks raise NotDelivered only after the settle waits ([github_issues.py:48-52](../../../../services/agent/src/autobots/adapters/github_issues.py#L48), 189-212). The gateway contract they follow is written at [application/tool_gateway.py:24-29](../../../../services/agent/src/autobots/application/tool_gateway.py#L24).
- **Every network seam is injectable, and tests run with sockets blocked.** Transports, resolvers, environ, clocks and waits are parameters: [tavily.py:42-46](../../../../services/agent/src/autobots/adapters/tavily.py#L42), [jina.py:42-46](../../../../services/agent/src/autobots/adapters/jina.py#L42), [market_data.py:78-80](../../../../services/agent/src/autobots/adapters/market_data.py#L78), [github_issues.py:145-150](../../../../services/agent/src/autobots/adapters/github_issues.py#L145), [url_guard.py:90-98](../../../../services/agent/src/autobots/adapters/url_guard.py#L90) and [egress_proxy.py:137-143](../../../../services/agent/src/autobots/adapters/egress_proxy.py#L137). [services/agent/tests/conftest.py:22-27](../../../../services/agent/tests/conftest.py#L22) blocks connect and getaddrinfo for the whole session, and the adapter tests use httpx.MockTransport.
- **Credentials live for one attempt and one client.** [provider_http.py:1-8](../../../../services/agent/src/autobots/adapters/provider_http.py#L1) and 28-40 resolve a key per attempt and name only the credential on failure. [github_issues.py:75-98](../../../../services/agent/src/autobots/adapters/github_issues.py#L75) pins writes and readbacks to the repository the approval recorded. [models/factory.py:90-107](../../../../services/agent/src/autobots/adapters/models/factory.py#L90) hands a SecretStr to one prepared client.
- **A fail-closed OpenRouter factory and catalog.** [models/factory.py:22-64](../../../../services/agent/src/autobots/adapters/models/factory.py#L22) refuses forbidden or unsupported options instead of dropping them. Lines 110-115 turn SDK retries off and set a timeout above the loop's bound, pinned by [services/agent/tests/test_model_attempts.py:297-298](../../../../services/agent/tests/test_model_attempts.py#L297). [models/catalog.py:45-62](../../../../services/agent/src/autobots/adapters/models/catalog.py#L45) and 133-149 price with Decimal ceilings and refuse stale, future-dated, ambiguous or drifted entries without substituting a model.
- **One URL guard with typed refusals, and a proxy that pins its address.** [url_guard.py:51-79](../../../../services/agent/src/autobots/adapters/url_guard.py#L51) and 107-153 check https only, userinfo, length, public DNS answers, every redirect, size and time, each with a typed code. Tavily, Jina and store_remote_file share the guard. The egress proxy connects to the address it checked ([egress_proxy.py:73-99](../../../../services/agent/src/autobots/adapters/egress_proxy.py#L73), 156-162).
- **Streaming without weakening tool-call validation.** [loop_middleware.py:175-205](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L175) re-parses each streamed tool call so a cut-off argument stays an invalid call (tested at [services/agent/tests/test_result_stream.py:159-166](../../../../services/agent/tests/test_result_stream.py#L159)). [tavily.py:37-38](../../../../services/agent/src/autobots/adapters/tavily.py#L37) and 53 merge the no-inference options last, so no caller can turn provider-side generation on.
- **Comments that record why, citing the decision.** [github_issues.py:48-52](../../../../services/agent/src/autobots/adapters/github_issues.py#L48) explains the readback waits by pointing to a live run; [models/catalog.py:13-17](../../../../services/agent/src/autobots/adapters/models/catalog.py#L13) states what RESERVED_PROMPT_TOKENS can't catch; [models/factory.py:110-115](../../../../services/agent/src/autobots/adapters/models/factory.py#L110) explains why SDK retries are off; [url_guard.py:130-132](../../../../services/agent/src/autobots/adapters/url_guard.py#L130) explains why the peer is checked again; [browser_executor.py:267](../../../../services/agent/src/autobots/adapters/browser_executor.py#L267) records a Docker counting quirk.
- **A fenced checkpointer tied to its qualified stack.** [checkpoints.py:59-77](../../../../services/agent/src/autobots/adapters/checkpoints.py#L59) sets the lease generation on the checkpointer's own connection so the database refuses stale writes. Lines 21-47 fingerprint the adapter release, its migrations and the SQL it relies on.

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [PADP-01](#padp-01) | high | errors | The live-result tap's JSON reader can stop a paid reply as partial_stream or uncertain_acceptance | S | medium |
| [PADP-02](#padp-02) | high | modules | The pull-request connector rewrites approval state with inline SQL, outside a transaction and without the lease | M | high |
| [PADP-03](#padp-03) | medium | size | Each tool module is one factory closure of 68 to 226 lines, which hides its helpers from per-function metrics and tests | L | medium |
| [PADP-04](#padp-04) | medium | duplication | Status and error mapping is copied per provider and has drifted | M | medium |
| [PADP-05](#padp-05) | medium | approach | Six httpx client constructors use different defaults, and the GitHub token client honors proxy environment variables | M | medium |
| [PADP-06](#padp-06) | medium | approach | GitHub read tools resolve the target and open a new client for every request, so one call can read two repositories | S | low |
| [PADP-07](#padp-07) | medium | types | Provider replies are parsed as Any with ad hoc .get chains, so malformed replies fail with different codes or crash consumers | M | medium |
| [PADP-08](#padp-08) | medium | functions | LoopMiddleware._admitted_call passes state out of a nested closure through four mutable lists | M | medium |
| [PADP-09](#padp-09) | medium | modules | loop_middleware.py holds application policy that application modules import back from adapters | L | medium |
| [PADP-10](#padp-10) | medium | standards | Rule path scopes miss the adapter that admits model calls and point at folders that don't exist | S | low |
| [PADP-11](#padp-11) | medium | errors | A bare ValueError is read as 'recovery closed this attempt' | S | medium |
| [PADP-12](#padp-12) | medium | standards | Reported charges are converted to micro-USD with float arithmetic and rounded differently on two paths | S | low |
| [PADP-13](#padp-13) | medium | duplication | Adapters query run, lease and approval tables directly and re-spell rules that the domain and gateway own | M | medium |
| [PADP-14](#padp-14) | medium | modules | browser_executor.py bundles five responsibilities into one file covered by the qualification fingerprint | M | high |
| [PADP-16](#padp-16) | medium | types | The two agent middlewares type their hooks as Any and communicate through JSON in ToolMessage.content | S | low |
| [PADP-17](#padp-17) | medium | types | A naive `since`, which the input contract accepts, crashes the pull-request filter | S | low |
| [PADP-18](#padp-18) | medium | tests | The most complex connector, the gateway middleware and storage have no fast unit tests | M | low |
| [PADP-15](#padp-15) | low | approach | The URL guard checks one DNS answer and then lets httpx resolve the name again | M | high |
| [PADP-19](#padp-19) | low | naming | Seven `*target` definitions under five names cover three ideas in the GitHub connectors | S | low |
| [PADP-20](#padp-20) | low | duplication | The proxy's copy of the public-address check has no parity test with the URL guard's | S | low |
| [PADP-21](#padp-21) | low | duplication | Two superseded credential helpers remain: one unused and one called only by tests | S | low |

### <a id="padp-01"></a>PADP-01: The live-result tap's JSON reader can stop a paid reply as partial_stream or uncertain_acceptance

- **Severity** high · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/adapters/result_stream.py:196-205](../../../../services/agent/src/autobots/adapters/result_stream.py#L196): flush parses every save_artifact call before checking its path, and nothing catches the parser
  - [services/agent/src/autobots/adapters/result_stream.py:57-91](../../../../services/agent/src/autobots/adapters/result_stream.py#L57): _read_string raises through json.loads (66, 91) and int(..., 16) (73)
  - [services/agent/src/autobots/adapters/result_stream.py:7-8](../../../../services/agent/src/autobots/adapters/result_stream.py#L7): Docstring: a failure here never stops the run
  - [services/agent/src/autobots/adapters/result_stream.py:241-246](../../../../services/agent/src/autobots/adapters/result_stream.py#L241): Only send failures are caught
  - [services/agent/src/autobots/adapters/loop_middleware.py:152-171](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L152): _streamed turns any exception after the first chunk into PARTIAL_STREAM
  - [services/agent/src/autobots/application/goal_loop.py:359-361](../../../../services/agent/src/autobots/application/goal_loop.py#L359): Every goal run sets a tap
  - [services/agent/tests/test_result_stream.py:145](../../../../services/agent/tests/test_result_stream.py#L145): Only a failing send is tested
- **Evidence:** flush parses each save_artifact call before checking its path, and nothing catches the parser. _streamed then converts any exception raised after the first chunk:

  ```text
  call.changed = False
  fields, growing = partial_object(call.arguments)        # result_stream.py:201-202
  ...
  except Exception:
      if assembled is not None:
          raise ProviderFailure(FailureClass.PARTIAL_STREAM) from None   # loop_middleware.py:163-165
  ```

  Reproduced in memory with the service venv, using a fake stream and a fake notify and no database or network. A save_artifact call whose content holds a raw newline gives one invalid tool call without a tap. With a tap it gives ProviderFailure(partial_stream) when the bad text arrives in a feed that flushes, and a bare JSONDecodeError out of tap.finish() in the finally clause when it arrives inside the 0.15-second coalescing window; dispatch then classifies that one as uncertain_acceptance. partial_object also raises JSONDecodeError on an invalid escape such as backslash-q, and ValueError on backslash-u followed by non-hex characters.
- **Why it matters:** Every goal run sets a tap. Without the tap, a reply with a malformed tool call gets an invalid-tool-call message and the model can try again. With the tap, the call is recorded as uncertain (partial_stream or uncertain_acceptance, depending on when the tap flushes): the reservation stays open for reconciliation and the run stops. The module's own invariant, 'A failure here never stops the run', holds only for send failures. Parsing happens before the outputs/ path check, so any save_artifact call can trigger it.
- **Recommendation:** Make the tap total. In flush, catch ValueError (JSONDecodeError is a subclass) around partial_object and stop streaming that call. In _streamed, call tap.begin, feed and finish through a helper that logs result_text.unavailable once, disables the tap and never raises. Add tests with a tap present for a raw control character, an invalid escape and a bad unicode escape; each should assert that the reply comes back with an invalid tool call. Add one more test showing that an error in finish() doesn't escape. Reword the 'tolerant reader' comment at line 48 to say it tolerates incomplete input, not malformed input.
- **Rule check:** Decision 0022 D4 and US-15.24 (the module docstring) say a tap failure never stops the run; the fix enforces that. Real stream failures keep the model-gateway classification (partial_stream, reconciled, not retried), and tests stay on fake streams (python-worker rule).
- **Verification:** revised. Reproduced both paths in memory with fakes: a parse error during feed gives partial_stream, and one inside finish() escapes as JSONDecodeError that dispatch classifies uncertain_acceptance; severity stays high.

```text
# result_stream.py
async def flush(self) -> None:
    for call in self._calls.values():
        if call.name != RESULT_TOOL or not call.changed or call.unreadable:
            continue
        call.changed = False
        try:
            fields, growing = partial_object(call.arguments)
        except ValueError:      # malformed, not just incomplete: the stored artifact stays the record
            call.unreadable = True
            continue
        ...
# loop_middleware._streamed
await _tap_safely(tap.feed, chunk)   # any Exception: logged once, tap disabled, nothing raised
```

### <a id="padp-02"></a>PADP-02: The pull-request connector rewrites approval state with inline SQL, outside a transaction and without the lease

- **Severity** high · **Dimension** modules · **Effort** M · **Risk** high · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/adapters/github_pulls.py:122-154](../../../../services/agent/src/autobots/adapters/github_pulls.py#L122): approved_detail and return_to_review: four writes, no transaction, no lease check
  - [services/agent/src/autobots/adapters/github_pulls.py:194-199](../../../../services/agent/src/autobots/adapters/github_pulls.py#L194): Called when the base branch moved
  - [services/agent/src/autobots/application/approvals.py:183-199](../../../../services/agent/src/autobots/application/approvals.py#L183): The owning module's re-request, inside approval_gate's transaction (109)
  - [services/agent/src/autobots/application/approvals.py:25](../../../../services/agent/src/autobots/application/approvals.py#L25): DEFAULT_TTL_SECONDS = 86_400; the adapter hard-codes interval '1 day'
  - [services/agent/src/autobots/application/tools.py:76-77](../../../../services/agent/src/autobots/application/tools.py#L76): Handler-side writes take hold_lease inside a transaction
  - [services/agent/src/autobots/application/runs.py:80-93](../../../../services/agent/src/autobots/application/runs.py#L80): append_event is two statements; the gapless sequence relies on the caller's transaction
  - [services/agent/src/autobots/operations/worker.py:135-136](../../../../services/agent/src/autobots/operations/worker.py#L135): The step connection the tool context runs on is autocommit
- **Evidence:** When the base has moved, return_to_review runs four separate statements on the worker's autocommit connection, with no hold_lease or hold_running first:

  ```text
  await context.connection.execute(
      "update app_private.tool_receipts set reconciled_at = now() where operation_id = %s", ...)
  cursor = await context.connection.execute(
      "update public.approval_requests set status = 'pending', decided_by = null, "
      "decided_at = null, review_detail = %s, "
      "expires_at = clock_timestamp() + interval '1 day' " ...)
  ```

  It then calls append_event, which updates runs.event_sequence and inserts into run_events. Elsewhere, a handler-side write takes the lease inside a transaction (tools.py:76-77), and approval_gate's own re-request runs in one transaction with a TTL parameter.
- **Why it matters:** The approvals state machine is split between application/approvals.py and a GitHub adapter. Each statement commits on its own. A crash or cancel between them can leave the receipt reconciled while the approval stays approved, or skip a run_events sequence number that append_event documents as gapless. A worker that lost its lease during the GitHub reads can still reset a person's decision, which the python-worker rule forbids. The TTL duplicates DEFAULT_TTL_SECONDS, and any new approval column or rule must also be remembered in this adapter.
- **Recommendation:** Move the transition into application/approvals.py as one function that runs in a single transaction. It takes the lease first (hold_lease, as write_run_file does), reconciles the receipt, resets the approval with the new detail and the standard TTL, and appends approval.requested. tool_gateway imports approvals, so move hold_lease into application/worker_leases.py to avoid an import cycle. The adapter keeps only the reads that build the new diff, then raises base_moved. Move approved_detail and github_issues.approved_repository next to the new function as read helpers. Before the move, add a stale-generation case to tests/db/pull_request_check.py next to its base-moved and re-approval cases.
- **Rule check:** python-worker rule: enforce leases and fencing on product writes and persist outbox events. SP-010: transitions need guards and an atomic update with their event. Decision 0022 D15's behavior (return to pending with a diff against the new head) is kept, only moved into the module that owns approvals. Nothing in the approval binding is relaxed.
- **Verification:** revised. Four unfenced autocommit statements and the hard-coded day confirmed; the tool context's step connection is opened autocommit at operations/worker.py:135-136, not line 79 (the heartbeat), so that location was corrected.

```text
# application/worker_leases.py (moved from tool_gateway, which imports approvals)
async def hold_lease(connection, run_id: UUID, generation: int) -> None: ...

# application/approvals.py
async def rerequest_review(connection, *, run_id: UUID, generation: int, operation_id: str,
                           tool_id: str, detail: dict[str, Any],
                           ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    """Decision 0022 D15: nothing was sent, so a person sees the diff against the new head."""
    async with connection.transaction():
        await hold_lease(connection, run_id, generation)
        await _mark_receipt_reconciled(connection, operation_id)
        approval_id = await _reset_to_pending(connection, operation_id, detail, ttl_seconds)
        await append_event(connection, run_id, _requested(approval_id, tool_id))

async def approved_review_detail(connection, operation_id: str) -> dict[str, Any]: ...

# adapters/github/pulls.py, when the base moved
await rerequest_review(ctx.connection, run_id=ctx.scope.run_id, generation=ctx.scope.generation, ...)
raise ToolFailed("base_moved")
```

### <a id="padp-03"></a>PADP-03: Each tool module is one factory closure of 68 to 226 lines, which hides its helpers from per-function metrics and tests

- **Severity** medium · **Dimension** size · **Effort** L · **Risk** medium · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/adapters/github_pulls.py:68-293](../../../../services/agent/src/autobots/adapters/github_pulls.py#L68): 13 nested functions; C901 37 and 92 statements are their sum; largest handler is open_pull_request at 186-247
  - [services/agent/src/autobots/adapters/github_reads.py:61-272](../../../../services/agent/src/autobots/adapters/github_reads.py#L61): 5 nested handlers; C901 18
  - [services/agent/src/autobots/adapters/tavily.py:42-229](../../../../services/agent/src/autobots/adapters/tavily.py#L42): 7 nested functions; tool() at 148 takes 9 positional arguments
  - [services/agent/src/autobots/adapters/market_data.py:78-211](../../../../services/agent/src/autobots/adapters/market_data.py#L78): C901 15 across two handlers
  - [services/agent/src/autobots/adapters/jina.py:42-152](../../../../services/agent/src/autobots/adapters/jina.py#L42)
  - [services/agent/src/autobots/adapters/github_issues.py:145-239](../../../../services/agent/src/autobots/adapters/github_issues.py#L145): Three 'if version == 2' expressions and a getattr on the input union (173)
  - [services/agent/src/autobots/adapters/remote_files.py:29-96](../../../../services/agent/src/autobots/adapters/remote_files.py#L29)
  - [services/agent/src/autobots/adapters/github_reads.py:204-213](../../../../services/agent/src/autobots/adapters/github_reads.py#L204): common: dict[str, Any] splatted into ToolDefinition; also jina.py:112, market_data.py:167, remote_files.py:74
- **Evidence:**

  ```text
  def github_pull_request_tool(
      transport: httpx.AsyncBaseTransport | None = None,
      environ: Mapping[str, str] = os.environ,
  ) -> ToolDefinition:
      async def read(http: httpx.AsyncClient, path: str, params: Any = None) -> httpx.Response:
      ...                                     # 12 more nested functions, 226 lines in all
  GITHUB_PULL_REQUEST = github_pull_request_tool()
  ```

  The same shape appears in github_read_tools (212 lines), tavily_tools (188), market_tools (134), jina_tools (111), github_issue_tool (95) and store_remote_file_tool (68), 1,034 lines in all. Ruff's C901 counts nested bodies, so the scores 37, 18, 15 and 12 are totals for each container. An AST count per closure puts the largest handlers at open_pull_request (62 lines), workflow_runs (48) and inflation (47).
- **Why it matters:** Helpers such as head_of, content_at, existing and write can't be imported or tested on their own, and handlers are reached only by building the whole definition with a fake transport, as test_github_reads.py does. The riskiest connector, the PR one, is exercised only by the db profile. Shared state (transport, environ) is captured implicitly, so each module re-creates its own client, error and parsing helpers; the drift is described in the next findings. Complexity limits can't be applied per handler: the metric flags containers while the real hotspot, open_pull_request, stays hidden. ToolDefinition keywords passed through dict[str, Any] escape mypy.
- **Recommendation:** Adopt one shape for tool adapters and migrate module by module, starting with the PR connector behind new fast tests. The shape has four parts. (1) A small frozen connector per provider owns transport and environ and opens one client per attempt. (2) Handlers are module-level functions taking (api, arguments, context), so each can be tested directly. (3) A typed, keyword-only builder replaces the dict splats and Tavily's positional tool(). (4) Exported singletons, tool IDs, versions and schemas stay unchanged.
- **Rule check:** Tool IDs, versions, input and output models and public fields stay identical, so version-pinned grants and catalogs are unaffected. Keys and targets are still resolved per attempt (PK-01, Decisions 0017, 0024 and 0025). No generated contract changes.
- **Verification:** revised. Closure sizes, nesting and C901 totals (37, 18, 15, 15, 12) confirmed with ast and ruff; handlers are already unit-tested through the built definitions, so severity lowered to medium and the impact reworded.

```text
adapters/github/
  connector.py  @dataclass(frozen=True) class GithubConnector: transport, environ
                  async with connector.attempt(ctx) as api   # target, token, one client per attempt
                class GithubApi: read(path, params) / write(path, payload)   # one status and error table
  issues.py     create_issue(api, args, ctx), find_issue(api, ctx), ISSUE_VERSIONS = {1: ..., 2: ...}
  pulls.py      review_detail(api, args); open_pull_request(api, args, ctx):
                  _check_base -> _commit_files (tree, commit, ref) -> _find_open_pull or _open_pull
  reads.py      list_pull_requests, list_workflow_runs, search_issues, read_file: (api, args)
adapters/web/tavily.py, jina.py; adapters/market/yahoo.py, world_bank.py   # same three parts
adapters/tool_builders.py  def read_only_tool(*, tool_id, title, description, input_model,
                           output_model, handler, ...) -> ToolDefinition   # typed, keyword-only
GITHUB_READ_TOOLS = github_read_tools()   # exported names, tool IDs and versions unchanged
```

### <a id="padp-04"></a>PADP-04: Status and error mapping is copied per provider and has drifted

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 14
- **Where:**
  - [services/agent/src/autobots/adapters/github_issues.py:45](../../../../services/agent/src/autobots/adapters/github_issues.py#L45): _REFUSED without 409
  - [services/agent/src/autobots/adapters/github_issues.py:55-56](../../../../services/agent/src/autobots/adapters/github_issues.py#L55): First UnclearReply
  - [services/agent/src/autobots/adapters/github_pulls.py:45-49](../../../../services/agent/src/autobots/adapters/github_pulls.py#L45): _REFUSED with 409, and a second UnclearReply
  - [services/agent/src/autobots/adapters/github_pulls.py:72-84](../../../../services/agent/src/autobots/adapters/github_pulls.py#L72): Any HTTPError becomes destination_unreachable; any non-200, 5xx included, becomes github_refused_N
  - [services/agent/src/autobots/adapters/github_reads.py:40-58](../../../../services/agent/src/autobots/adapters/github_reads.py#L40): _REFUSED without 400; 5xx becomes github_unavailable
  - [services/agent/src/autobots/adapters/provider_http.py:61-69](../../../../services/agent/src/autobots/adapters/provider_http.py#L61): failure_for: 429 becomes rate_limited; GitHub doesn't use it
  - [services/agent/src/autobots/adapters/tavily.py:47-61](../../../../services/agent/src/autobots/adapters/tavily.py#L47): Re-implements client, transport-error, status and JSON mapping; also jina.py:47-63 and market_data.py:83-99
- **Evidence:**

  ```text
  _REFUSED = frozenset({400, 401, 403, 404, 410, 422, 429})        # github_issues.py:45
  _REFUSED = frozenset({400, 401, 403, 404, 409, 410, 422, 429})   # github_pulls.py:45
  _REFUSED = frozenset({401, 403, 404, 410, 422, 429})             # github_reads.py:40
  raise ToolFailed(f"github_refused_{reply.status_code}")  # github_pulls.py:83, any non-200 incl. 5xx
  raise ToolFailed("github_unavailable")                   # github_reads.py:57, the same 5xx
  if status == 429: return ToolFailed("rate_limited")      # provider_http.py:63-64
  ```

  Counted by grep: four status-to-code mappings (three _REFUSED sets and failure_for), two identical UnclearReply classes, and eight 'except httpx' blocks in six tool modules.
- **Why it matters:** The model and the receipts see different codes for the same condition. A GitHub 429 is github_refused_429 while Tavily's is rate_limited. A GitHub 503 is github_refused_503 in the PR connector and github_unavailable in the read tools. Each new connector copies one of the variants, and two UnclearReply classes with one meaning leave readers unsure which one to raise.
- **Recommendation:** Give the mechanics one home in provider_http (or a new adapters/http module): one UnclearReply, a read helper (transport error becomes ToolFailed(unreachable), a non-2xx status a mapped code, bad JSON malformed) and a write helper (only connect errors and statuses that prove nothing was written become ToolFailed; anything unclear raises UnclearReply). Keep each destination's write-refused set in one named constant, with a comment on why each status proves no write (409 for refs). Make every GitHub read map 5xx the same way.
- **Rule check:** tool_gateway.ToolFailed: on a write, only a status that proves nothing was created may become ToolFailed; everything else stays unknown and is reconciled. Codes are stored on receipts and asserted by tests (test_github_issues.py:147, tests/db/connector_check.py:172), so rename them only deliberately.
- **Verification:** confirmed. Three refused sets, two UnclearReply classes, failure_for and eight except-httpx blocks in six tool modules recounted with grep.

```text
# adapters/provider_http.py
class UnclearReply(Exception): ...                       # one, shared by every write
async def read_json(client, path, *, params=None, code_for=failure_for) -> Any
async def write_json(client, path, payload, *, refused: frozenset[int], code_for) -> Any
# adapters/github/connector.py
GITHUB_WRITE_REFUSED = frozenset({...})   # why each status proves nothing was created
def github_code(status: int) -> str       # one read mapping: 5xx -> github_unavailable everywhere
```

### <a id="padp-05"></a>PADP-05: Six httpx client constructors use different defaults, and the GitHub token client honors proxy environment variables

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 6
- **Where:**
  - [services/agent/src/autobots/adapters/github_issues.py:127-138](../../../../services/agent/src/autobots/adapters/github_issues.py#L127): Token client without trust_env=False; 15 s
  - [services/agent/src/autobots/adapters/provider_http.py:43-58](../../../../services/agent/src/autobots/adapters/provider_http.py#L43): trust_env=False, no redirects, 20 s
  - [services/agent/src/autobots/adapters/url_guard.py:115-117](../../../../services/agent/src/autobots/adapters/url_guard.py#L115): trust_env=False, no timeout (httpx's 5 s) under a 20 s cap
  - [services/agent/src/autobots/adapters/models/openrouter_metadata.py:15-18](../../../../services/agent/src/autobots/adapters/models/openrouter_metadata.py#L15): trust_env left at the default; 15 s
  - [services/agent/src/autobots/adapters/object_storage.py:38-46](../../../../services/agent/src/autobots/adapters/object_storage.py#L38): trust_env left at the default; a new client per operation for a process-wide key; 30 s
  - [services/agent/src/autobots/adapters/browser_executor.py:74](../../../../services/agent/src/autobots/adapters/browser_executor.py#L74): trust_env=False; 10 s
  - [services/agent/src/autobots/api/main.py:49](../../../../services/agent/src/autobots/api/main.py#L49): The store is built at startup but opens a client per call
- **Evidence:** Abridged:

  ```text
  return httpx.AsyncClient(base_url=base_url, headers=dict(headers), transport=transport,
      timeout=seconds, follow_redirects=False, trust_env=False)                  # provider_http.py:51-58
  return httpx.AsyncClient(base_url=API_URL, transport=transport, timeout=_REQUEST_SECONDS,
      follow_redirects=False, headers={"Authorization": f"Bearer {token}", ...})  # github_issues.py:128-138
  ```

  openrouter_metadata.http_client and SupabaseObjectStore._client also leave trust_env at httpx's default of True. Timeouts are 20, 15, 15, 30 and 10 seconds plus httpx's 5-second default, and none is derived from the tool's timeout_seconds.
- **Why it matters:** The GitHub client carries a token with write scope on the repository (Decision 0022 D6) and will use whatever HTTPS_PROXY or ALL_PROXY the worker's environment sets, while the Tavily and Jina clients and the URL guard refuse the environment. The storage client's service key is process-wide, yet the client is rebuilt for every operation instead of being owned by the lifespan, as DH-06 asks. A reader can't tell which timeout bounds a given call.
- **Recommendation:** Create clients through one factory with follow_redirects=False and trust_env=False fixed and a required, named timeout. Keep per-attempt clients where a per-attempt key requires them (tools, PK-01). Own one client in the API and worker lifespans for process-level credentials (storage, OpenRouter metadata). Define each timeout next to the tool timeout it must fit inside, and pin that relation in a test, as test_model_attempts.py:297-298 does for the model client.
- **Rule check:** DH-06: own HTTP clients in process lifecycles and bound timeouts. PK-01 keeps tool keys per attempt, so tool clients stay per attempt. The OpenRouter SDK client in models/factory.py is outside this change (model-gateway rule).
- **Verification:** confirmed. Six constructors and their defaults confirmed; with trust_env left on, httpx 0.28.1 also reads SSL_CERT_FILE and SSL_CERT_DIR, so a proxy plus a custom CA could see the GitHub token.

```text
# adapters/http.py
def new_client(base_url: str = "", *, timeout: float, headers: Mapping[str, str] | None = None,
               transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, headers=dict(headers or {}), timeout=timeout,
                             transport=transport, follow_redirects=False, trust_env=False)
# per attempt (PK-01): tool connectors; per process (lifespan): SupabaseObjectStore, OpenRouter metadata
```

### <a id="padp-06"></a>PADP-06: GitHub read tools resolve the target and open a new client for every request, so one call can read two repositories

- **Severity** medium · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/adapters/github_reads.py:65-72](../../../../services/agent/src/autobots/adapters/github_reads.py#L65): get resolves the target and opens a client per request
  - [services/agent/src/autobots/adapters/github_reads.py:117-127](../../../../services/agent/src/autobots/adapters/github_reads.py#L117): workflow_runs: one get for the runs plus one per failed run, up to 10
  - [services/agent/src/autobots/adapters/github_reads.py:154-163](../../../../services/agent/src/autobots/adapters/github_reads.py#L154): search_issues resolves the target, then get resolves it again
  - [services/agent/src/autobots/application/tool_keys.py:225-235](../../../../services/agent/src/autobots/application/tool_keys.py#L225): Each resolution reads the repository setting and loads and decrypts the token (170-181)
  - [services/agent/src/autobots/adapters/github_pulls.py:189-192](../../../../services/agent/src/autobots/adapters/github_pulls.py#L189): By contrast, one resolution and one client per attempt
- **Evidence:**

  ```text
  async def get(context: ToolContext, path: str, params: Mapping[str, Any] | None = None) -> Any:
      repository, token = await attempt_target(context, environ)
      async with github_client(token, transport) as http:
          try:
              reply = await http.get(path.format(repository=repository), params=params)
  ```
- **Why it matters:** In one attempt, github_list_workflow_runs makes up to 11 target resolutions (each a settings read, a credential load and a decryption) and 11 TLS connections. If the workspace's repository setting changes mid-call, the jobs come from a different repository than the runs list they annotate.
- **Recommendation:** Resolve (repository, token) once per attempt and pass one open client and repository to the handler, as open_pull_request does. search_issues then uses the same resolution for its repo: qualifier. GithubConnector.attempt() from the factory-closure finding provides this.
- **Rule check:** PK-01 and Decision 0025 resolve the key and repository per attempt; resolving once per attempt meets that. The approved-repository pinning in attempt_target is unchanged.
- **Verification:** confirmed. get resolves the target per request; workflow_runs makes up to 11 resolutions, each a settings read plus a credential load and decryption in tool_keys.github_target.

```text
async def list_workflow_runs(api: GithubApi, arguments) -> GithubListWorkflowRunsOutput:
    found = (await api.read(runs_path(arguments), params(arguments))).get("workflow_runs") or []
    ...   # each failed run's jobs through the same api: one repository, token and pool per call
```

### <a id="padp-07"></a>PADP-07: Provider replies are parsed as Any with ad hoc .get chains, so malformed replies fail with different codes or crash consumers

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 14
- **Where:**
  - [services/agent/src/autobots/adapters/tavily.py:47-68](../../../../services/agent/src/autobots/adapters/tavily.py#L47): call returns Any; reply.get with no dict check
  - [services/agent/src/autobots/adapters/jina.py:72](../../../../services/agent/src/autobots/adapters/jina.py#L72): Checks isinstance(reply, dict)
  - [services/agent/src/autobots/adapters/market_data.py:96-104](../../../../services/agent/src/autobots/adapters/market_data.py#L96): AttributeError caught for one level only
  - [services/agent/src/autobots/adapters/github_reads.py:53-58](../../../../services/agent/src/autobots/adapters/github_reads.py#L53): _checked returns raw JSON; handlers index item['number'] (89)
  - [services/agent/src/autobots/adapters/models/openrouter_metadata.py:37-49](../../../../services/agent/src/autobots/adapters/models/openrouter_metadata.py#L37): Unvalidated dict[str, Any]; JSON errors not caught; both factories return Any
  - [services/agent/src/autobots/adapters/models/catalog.py:110-119](../../../../services/agent/src/autobots/adapters/models/catalog.py#L110): parse_catalog trusts the payload's shape
  - [services/agent/src/autobots/application/worker_inference.py:99](../../../../services/agent/src/autobots/application/worker_inference.py#L99): The worker's consumer catches AttributeError and TypeError
  - [services/agent/src/autobots/application/provider_settings.py:274-277](../../../../services/agent/src/autobots/application/provider_settings.py#L274): The settings path parses without that catch
- **Evidence:** Counted by grep: 15 .json() calls in 9 adapter modules, 14 in 8 without browser_executor's local DevTools reply, none checked against a declared shape.

  ```text
  items = [item for item in reply.get("results", []) if isinstance(item, dict)]   # tavily.py:68
  data = reply.get("data") if isinstance(reply, dict) else None                    # jina.py:72
  chart = reply.json().get("chart") or {}    # market_data.py:97
  number=int(item["number"]),                # github_reads.py:89
  data: dict[str, Any] = reply.json()        # openrouter_metadata.py:46
  except (OSError, ValueError, TypeError, AttributeError) as error:   # worker_inference.py:99
  ```
- **Why it matters:** Each module validates the trust boundary in its own way, despite DH-06's single requirement. A list where Tavily expects an object fails as the generic tool_failed, while the same shape is provider_reply_malformed from Jina's reader and an empty success from Jina search. A malformed GitHub item is retried once as tool_failed. A non-object catalog reply makes provider_settings.models raise, because only the worker's consumer catches AttributeError and TypeError.
- **Recommendation:** Declare small, lenient, adapter-private Pydantic reply models with extra='ignore' and only the fields used, and parse through one helper that maps ValidationError or ValueError to ToolFailed('provider_reply_malformed') for reads. For effectful writes, a body that can't be parsed after a 201 must stay unknown (raise UnclearReply), never become ToolFailed. Make catalog_fetcher return None on malformed JSON or shape, and type both metadata factories with the existing CatalogFetcher alias and a KeyValidator alias instead of Any.
- **Rule check:** DH-06: validate data at trust boundaries. The reply models are adapter-private, not public contracts, so OpenAPI and the generated client are unaffected. Write semantics from tool_gateway.ToolFailed are preserved.
- **Verification:** revised. Recounted 15 .json() calls in 9 modules (14 in 8 without the local CDP reply); a list reply from Jina search is an empty success rather than provider_reply_malformed, so the impact was corrected.

```text
class _TavilyItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = ""; url: str = ""; content: str = ""; score: float | None = None
class _TavilyResults(BaseModel):
    model_config = ConfigDict(extra="ignore")
    results: list[_TavilyItem] = []
def parse_reply(model: type[T], reply: httpx.Response) -> T:
    try:
        return model.model_validate_json(reply.content)
    except ValueError:                    # pydantic's ValidationError is a ValueError
        raise ToolFailed("provider_reply_malformed") from None
```

### <a id="padp-08"></a>PADP-08: LoopMiddleware._admitted_call passes state out of a nested closure through four mutable lists

- **Severity** medium · **Dimension** functions · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/adapters/loop_middleware.py:491-597](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L491): 107 lines, C901 15, 65 statements
  - [services/agent/src/autobots/adapters/loop_middleware.py:497-500](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L497): Four out-parameter lists
  - [services/agent/src/autobots/adapters/loop_middleware.py:502-549](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L502): The nested dispatch writes to them
  - [services/agent/src/autobots/adapters/loop_middleware.py:400-426](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L400): _bounded appends to its caller's stopped list (423)
  - [services/agent/src/autobots/adapters/loop_middleware.py:579-596](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L579): Lists decoded in priority order; only the last reply and ticket are read
- **Evidence:**

  ```text
  limit: list[LimitReached] = []
  stopped: list[str] = []
  replies: list[Any] = []
  last_ticket: list[Any] = []
  
  async def dispatch(ticket: Any) -> ModelOutput:
      last_ticket.append(ticket)
  ```
- **Why it matters:** Which stop code wins depends on list order and on a callee mutating its caller's list. Replies and tickets are kept as lists although only the last of each is read. One method mixes usage reads, prompt sizing, building the admission request, retry policy, failure translation, late-charge reconciliation and reply facts, so changing any one of them on the paid path means re-reading all of them.
- **Recommendation:** Replace the four lists with one record object, and have _bounded raise a typed interruption instead of appending to a list. Extract _admission_request (usage read, size, price tier), _dispatch_once (guard, consume, bounded call), a pure _classify(error) -> ProviderFailure and _reconcile_late_charge. Keep the stop priority (guard or run stop, then limit, then failure class), and cover it with the existing test_worker_inference.py cases before moving code.
- **Rule check:** model-gateway rule: admission, budget reservation, the no-SDK-retry policy and uncertain classification stay exactly as they are; only control flow moves. Tests first: test_worker_inference.py and the db profile's goal-loop and recovery checks.
- **Verification:** confirmed. 107 lines, C901 15 and 65 statements confirmed with ruff; the four out-parameter lists and _bounded's append to its caller's list confirmed.

```text
@dataclass
class _CallRecord:
    stop_code: str | None = None      # guard, run or limit stop; first wins
    ticket: Ticket | None = None
    reply: ModelResponse | None = None

async def _admitted_call(self, request, handler, remaining, route=None):
    chosen, record = route or self._route, _CallRecord()
    admission_request = await self._admission_request(chosen, request)
    try:
        output = await call_with_policy(self._admission, admission_request,
            partial(self._dispatch_once, record, request, handler), self._policy(remaining))
    except ProviderFailure as failure:
        raise LoopStopped(record.stop_code or failure.failure.value) from None
    except AttemptClosed:
        await self._reconcile_late_charge(record)
        raise LoopStopped("lease_lost") from None
    await self._record_reply(record)
    return record.reply, output.complete
```

### <a id="padp-09"></a>PADP-09: loop_middleware.py holds application policy that application modules import back from adapters

- **Severity** medium · **Dimension** modules · **Effort** L · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/adapters/loop_middleware.py:208-259](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L208): ModelRoute (the run's frozen route) and the reservation arithmetic
  - [services/agent/src/autobots/adapters/loop_middleware.py:70-112](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L70): STOPPING, REPAIRABLE, INTERRUPTING, the ContextVars and LoopStopped
  - [services/agent/src/autobots/adapters/loop_middleware.py:349-674](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L349): Guard, compaction, summarization and admitted calls
  - [services/agent/src/autobots/adapters/loop_middleware.py:32-66](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L32): Imports six application modules
  - [services/agent/src/autobots/application/browsing_loop.py:23](../../../../services/agent/src/autobots/application/browsing_loop.py#L23)
  - [services/agent/src/autobots/application/browsing_tool.py:33](../../../../services/agent/src/autobots/application/browsing_tool.py#L33)
  - [services/agent/src/autobots/application/worker_inference.py:17](../../../../services/agent/src/autobots/application/worker_inference.py#L17)
  - [services/agent/src/autobots/application/goal_loop.py:30](../../../../services/agent/src/autobots/application/goal_loop.py#L30)
- **Evidence:** application/browsing_loop.py:23 has 'from autobots.adapters.loop_middleware import AdmittedModel, LoopMiddleware, LoopStopped, ModelRoute'. ModelRoute's docstring says 'A worker takes this from the run's frozen policy'. reservation_for and past_known_price compute budget reservations. The module imports compaction, model_admission, model_attempts, plans, run_usage and tool_gateway, and four application modules import it back.
- **Why it matters:** A 674-line adapter is the home of policy that the application layer owns, so dependencies run both ways between application and adapters. A change to the reservation arithmetic gets reviewed as LangChain glue, and the model-gateway rule doesn't load for this file (see the rule-scope finding).
- **Recommendation:** Split by layer without changing behavior. Pure loop policy goes to application. Admission and compaction orchestration becomes an application service over plain request and handler protocols. Only AdmittedModel, the streaming helpers and a thin AgentMiddleware subclass stay in the framework layer: DH-03's graphs/, or adapters/ until that folder exists. Application then imports only application modules.
- **Rule check:** DH-03 places LangGraph glue under graphs/, and DH-06 keeps domain decisions independent of LangGraph internals. The move preserves behavior. The model-gateway rule then covers the policy files by path.
- **Verification:** confirmed. Six application imports in loop_middleware and four application modules importing it back (plus operations/browse_trial.py) confirmed; no decision governs the placement.

```text
application/loop_policy.py     ModelRoute, request_bytes, reservation_for, past_known_price,
                               reply_facts, STOPPING, REPAIRABLE, LoopStopped     # pure, no LangChain
application/loop_admission.py  LoopAdmission(connection, scope, limits): guard(), consume(),
                               call(request, send), compact(messages, summarize)  # database and policy
graphs/agent_middleware.py     AdmittedModel, _streamed, _strictly_parsed, and a thin
                               LoopMiddleware(AgentMiddleware) translating ModelRequest and
                               ToolCallRequest into LoopAdmission calls
```

### <a id="padp-10"></a>PADP-10: Rule path scopes miss the adapter that admits model calls and point at folders that don't exist

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [.claude/rules/model-gateway.md:2-7](../../../../.claude/rules/model-gateway.md#L2): adapters/models/**, application/**, graphs/**
  - [.claude/rules/database.md:2-5](../../../../.claude/rules/database.md#L2): adapters/persistence/**
  - [tests/harness/test_assistant_assets.py:54-70](../../../../tests/harness/test_assistant_assets.py#L54): Representative paths are invented files
  - [tests/harness/test_assistant_assets.py:620-633](../../../../tests/harness/test_assistant_assets.py#L620): The check matches globs only against those invented paths
  - [services/agent/src/autobots/adapters/loop_middleware.py:248-259](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L248): Reservation and price-tier logic outside model-gateway's paths
- **Evidence:** services/agent/src/autobots has no graphs/ folder and adapters/ has no persistence/, so those two globs match no file. Meanwhile loop_middleware.py, which reserves budget per call, bounds calls and classifies their failures, matches only python-worker.md. The harness test passes because its representative paths are 'services/agent/src/autobots/graphs/run.py', 'services/agent/src/autobots/adapters/persistence/runs.py' and 'services/agent/src/autobots/adapters/models/gateway.py', none of which exist.
- **Why it matters:** Editing the per-call admission code doesn't load the rule that owns budget reservations, catalog mapping and the no-fallback policy, and the SQL scattered through adapters is outside the database rule's scope. The drift is invisible because the check validates globs against paths that don't exist.
- **Recommendation:** Either move the graph glue into DH-03's graphs/ (see the loop_middleware finding) or add adapters/loop_middleware.py and adapters/tool_middleware.py to model-gateway.md now. In the harness test, include at least one real tracked file per rule among the governed paths and assert that it exists, so moving or renaming governed code fails the check.
- **Rule check:** DH-03: use supported paths frontmatter and test representative paths. This only widens what the rules govern; no rule is relaxed.
- **Verification:** confirmed. No tracked file matches graphs/** or adapters/persistence/**; the real row-type module, services/agent/src/autobots/persistence/rows.py, is outside database.md's globs as well.

```text
# .claude/rules/model-gateway.md, until graph glue moves to graphs/
  - "services/agent/src/autobots/adapters/loop_middleware.py"
  - "services/agent/src/autobots/adapters/tool_middleware.py"
# tests/harness/test_assistant_assets.py
GOVERNED = {'model-gateway.md': ['services/agent/src/autobots/adapters/loop_middleware.py']}
for name, paths in GOVERNED.items():
    for path in paths:
        self.assertTrue((ROOT / path).exists(), path)
        self.assertTrue(any(glob_matches(glob, path) for glob in scoped[name]), path)
```

### <a id="padp-11"></a>PADP-11: A bare ValueError is read as 'recovery closed this attempt'

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 4
- **Where:**
  - [services/agent/src/autobots/adapters/loop_middleware.py:585-592](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L585): Catches any ValueError from call_with_policy
  - [services/agent/src/autobots/application/model_admission.py:195](../../../../services/agent/src/autobots/application/model_admission.py#L195): 'already been settled'
  - [services/agent/src/autobots/application/model_admission.py:205](../../../../services/agent/src/autobots/application/model_admission.py#L205): 'closed before it was sent'
  - [services/agent/src/autobots/application/model_admission.py:292](../../../../services/agent/src/autobots/application/model_admission.py#L292): 'not awaiting reconciliation'
  - [services/agent/src/autobots/adapters/loop_middleware.py:276-278](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L276): _charged runs float() on provider metadata inside dispatch
- **Evidence:**

  ```text
  except ValueError:
      # Recovery classified this call while it was out. Its charge is late evidence.
      charged = _charged(replies[-1].result[-1]) if replies else None
      if charged is not None and last_ticket:
          await ModelAdmission(self._connection).reconcile(...)
      raise LoopStopped("lease_lost") from None
  ```
- **Why it matters:** Every ValueError raised under call_with_policy is read as a recovery race. Suppose _charged's float() raises on a provider's cost inside dispatch. The attempt is never settled or marked uncertain, the except block calls _charged on the same reply and raises the ValueError again, and the loop ends with an unclassified error instead of a stop code. A bug and a recovery race look alike in stop codes and logs.
- **Recommendation:** Raise a typed AttemptClosed from _transition, mark_dispatched and reconcile, and catch only that in _admitted_call. Make _charged total, returning None when the cost is unreadable or not finite, as _retry_after already does (see the money finding), so other ValueErrors surface as bugs.
- **Rule check:** model-gateway: a charge is never invented, and late evidence is reconciled. DH-06: typed, safe errors. The lease_lost outcome for a real recovery race is unchanged.
- **Verification:** confirmed. Three ValueError raises in model_admission and the bare except at loop_middleware.py:585 confirmed; a non-numeric or NaN cost makes _charged raise ValueError inside dispatch.

```text
# application/model_admission.py
class AttemptClosed(Exception):
    """Recovery settled or closed this attempt while it was out."""
# _transition, mark_dispatched and reconcile raise AttemptClosed instead of ValueError
# loop_middleware._admitted_call
except AttemptClosed:
    await self._reconcile_late_charge(record)
    raise LoopStopped("lease_lost") from None
```

### <a id="padp-12"></a>PADP-12: Reported charges are converted to micro-USD with float arithmetic and rounded differently on two paths

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/adapters/loop_middleware.py:276-278](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L276): round(float(cost) * 1_000_000): rounds half to even
  - [services/agent/src/autobots/operations/route_qualification.py:244-246](../../../../services/agent/src/autobots/operations/route_qualification.py#L244): math.ceil(float(cost) * 1_000_000): rounds up
  - [services/agent/src/autobots/adapters/models/catalog.py:45-53](../../../../services/agent/src/autobots/adapters/models/catalog.py#L45): Prices use Decimal with ROUND_CEILING: a price never under-counts
- **Evidence:**

  ```text
  return None if cost is None else round(float(cost) * 1_000_000)          # loop_middleware.py:278
  return None if cost is None else math.ceil(float(cost) * 1_000_000)      # route_qualification.py:246
  return int((number * factor).to_integral_value(rounding=ROUND_CEILING))  # catalog.py:53
  ```

  Checked with python3.12: a reported 0.0000125 USD gives 12 micro-USD with round() and 13 with ceil(); 0.000001234 gives 1 and 2.
- **Why it matters:** DH-06 requires exact decimal or integer monetary units and forbids float arithmetic for money. Because the worker rounds half to even, the ledger charge it settles (model_attempts.py:150) can be one micro-USD below what the qualification path records for the same reply. That contradicts the catalog's policy that a price never under-counts. A non-numeric or non-finite cost raises inside dispatch instead of leaving the charge unreported.
- **Recommendation:** Add one micro_usd(reported) helper next to Pricing or in domain/models.py: Decimal(str(value)), a finite check, ROUND_CEILING, and None when the value is unreadable. Use it in _charged and in route_qualification._cost_micro_usd, and add a test with half-micro values.
- **Rule check:** DH-06 and the python-worker rule require exact monetary units. model-gateway: a charge is never invented, so an unreadable cost stays None and the estimate stays open for reconciliation.
- **Verification:** confirmed. round versus ceil reproduced with python3.12 (12.5 micro-USD gives 12 and 13); DH-06 forbids float arithmetic for money.

```text
def micro_usd(reported: object) -> int | None:
    """A reported USD charge in micro-USD, rounded up; None when unreadable or not finite."""
    try:
        amount = Decimal(str(reported))
    except InvalidOperation:
        return None
    if not amount.is_finite():
        return None
    return int((amount * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
```

### <a id="padp-13"></a>PADP-13: Adapters query run, lease and approval tables directly and re-spell rules that the domain and gateway own

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/adapters/loop_middleware.py:72](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L72): INTERRUPTING spelled as string literals
  - [services/agent/src/autobots/domain/runs.py:22](../../../../services/agent/src/autobots/domain/runs.py#L22): The canonical TERMINAL set
  - [services/agent/src/autobots/adapters/loop_middleware.py:384-392](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L384): Recursive parent-status query with a literal 'running'
  - [services/agent/src/autobots/adapters/loop_middleware.py:418-422](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L418): Run status poll
  - [services/agent/src/autobots/adapters/loop_middleware.py:551-554](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L551): run_usage read
  - [services/agent/src/autobots/adapters/browser_executor.py:448-460](../../../../services/agent/src/autobots/adapters/browser_executor.py#L448): lease_alive repeats ownership_refusal's rule without the workspace check
  - [services/agent/src/autobots/adapters/github_issues.py:101-109](../../../../services/agent/src/autobots/adapters/github_issues.py#L101): Reads approval_requests
  - [services/agent/src/autobots/adapters/remote_files.py:55-72](../../../../services/agent/src/autobots/adapters/remote_files.py#L55): Reads run_files, whose writer is application/tools.write_run_file
- **Evidence:**

  ```text
  INTERRUPTING = frozenset({"cancelling", "cancelled", "failed", "succeeded"})          # loop_middleware.py:72
  TERMINAL = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})   # domain/runs.py:22
  "where j.run_id::text = %s and j.generation = %s and j.status = 'claimed' "           # browser_executor.py:454
  "and j.lease_expires_at > clock_timestamp() and r.status = 'running'",
  ```

  ownership_refusal (tool_gateway.py:256-272) and hold_lease (275) state the same lease rule twice more. Counted: six SQL statements in four adapter modules (loop_middleware 3, browser_executor 1, github_issues 1, remote_files 1) plus one re-spelled state set. The checkpointer's SQL and the NOTIFY call are excluded because they belong to the adapters.
- **Why it matters:** A new interrupting state, a lease column change or a run_files change has to be found in adapters by grep. The lease rule is written three times (ownership_refusal, hold_lease and lease_alive), and the copies already differ in shape: lease_alive drops the workspace filter, which is harmless only because run IDs are unique. The browser executor's copy sits inside the qualification fingerprint, so even aligning it requires a live re-qualification.
- **Recommendation:** Derive INTERRUPTING from domain.runs.TERMINAL plus CANCELLING. Move each query next to the module that owns its table: one lease query in worker_leases used by both the sweeper and the gateway, the run status and parent-chain reads in runs, the usage read in run_usage, the approved target in approvals, and the run-file lookup beside write_run_file. Adapters then call those functions.
- **Rule check:** contracts rule: canonical states and guards are shared, with no second state vocabulary. SP-012: ownership is decided by database time, which the single shared query keeps through clock_timestamp().
- **Verification:** revised. Six SQL statements in four modules and the re-spelled state set recounted; lease_alive's missing workspace filter is harmless with unique run IDs, so the impact now rests on the three copies of the lease rule.

```text
# domain/runs.py
INTERRUPTING = TERMINAL | {RunStatus.CANCELLING}
# application/worker_leases.py
async def generation_alive(connection, run_id, generation) -> bool   # the one lease query
# application/runs.py: run_status(), parents_running(); run_usage.py: model_calls_used()
# application/approvals.py: approved_target(); application/tools.py: run_file_by_operation()
```

### <a id="padp-14"></a>PADP-14: browser_executor.py bundles five responsibilities into one file covered by the qualification fingerprint

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** high · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/adapters/browser_executor.py:82-309](../../../../services/agent/src/autobots/adapters/browser_executor.py#L82): Docker session lifecycle
  - [services/agent/src/autobots/adapters/browser_executor.py:312-360](../../../../services/agent/src/autobots/adapters/browser_executor.py#L312): CDP client
  - [services/agent/src/autobots/adapters/browser_executor.py:363-424](../../../../services/agent/src/autobots/adapters/browser_executor.py#L363): Request guard
  - [services/agent/src/autobots/adapters/browser_executor.py:427-438](../../../../services/agent/src/autobots/adapters/browser_executor.py#L427): images_fingerprint hashes this whole file (434)
  - [services/agent/src/autobots/adapters/browser_executor.py:441-460](../../../../services/agent/src/autobots/adapters/browser_executor.py#L441): Lease checks with SQL
  - [services/agent/src/autobots/adapters/browser_executor.py:489-500](../../../../services/agent/src/autobots/adapters/browser_executor.py#L489): The qualification gate requires that hash
  - [services/agent/src/autobots/adapters/browser_page.py:4-5](../../../../services/agent/src/autobots/adapters/browser_page.py#L4): Split out so the fingerprint isn't touched
  - [services/agent/src/autobots/application/tool_gateway.py:332-337](../../../../services/agent/src/autobots/application/tool_gateway.py#L332): Qualification is checked again on every browse dispatch
- **Evidence:** One 500-line module holds the Docker session lifecycle, a CDP client, the request guard, the qualification gate and lease checks with SQL. images_fingerprint hashes the whole file, and executor_qualified requires that hash. That is why browser_page.py describes itself as 'a separate module from the executor so the executor's qualification fingerprint isn't touched'. ExecutorConfig.environ (57) is never read. executor_qualified reads a JSON report and hashes five files synchronously, and the gateway calls it on every browse dispatch.
- **Why it matters:** Any edit to any of the five concerns, even a docstring, turns browsing off until a live Docker re-qualification. That makes unrelated maintenance expensive and pushes new code into side modules to avoid the file. Reviewing an isolation change means also reading the lease SQL and the report parsing. Hashing the files on every dispatch is small, but it is blocking work on the event loop (DH-06).
- **Recommendation:** Split into cohesive modules in one change, scheduled together with the re-qualification: a Docker session module, a CDP module (client and request guard) and a qualification module. List every one of them explicitly in images_fingerprint, together with egress_proxy.py, the Dockerfiles, the entrypoint and wherever the lease query ends up, so the binding stays as strict as today. Compute the fingerprint off the event loop (asyncio.to_thread) or cache it by file modification times, and remove ExecutorConfig.environ.
- **Rule check:** BX-05 and Decision 0018 B8: the qualification must keep binding everything it exercises, and the split must be re-qualified live, which is an explicitly authorized task. attempt_alive already depends on the unfingerprinted ownership_refusal, so the fingerprint list should name the lease module explicitly rather than drop it. No isolation flag or cap changes.
- **Verification:** confirmed. Five concerns, the self-hashing fingerprint, the never-read ExecutorConfig.environ and the per-dispatch executor_ready call (tool_gateway.py:334) confirmed.

```text
adapters/browser/session.py        ExecutorConfig, BrowserSession, BrowserExecutor (Docker CLI only)
adapters/browser/cdp.py            Cdp, RequestGuard
adapters/browser/qualification.py  FINGERPRINTED = (browser/session.py, browser/cdp.py, egress_proxy.py,
                                   Dockerfiles, entrypoint, the lease query's module)
                                   images_fingerprint (off the event loop), REQUIRED_CASES, executor_qualified
```

### <a id="padp-16"></a>PADP-16: The two agent middlewares type their hooks as Any and communicate through JSON in ToolMessage.content

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 12
- **Where:**
  - [services/agent/src/autobots/adapters/loop_middleware.py:629-674](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L629): awrap_model_call and awrap_tool_call with Any request and handler
  - [services/agent/src/autobots/adapters/loop_middleware.py:668](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L668): Re-parses the inner middleware's JSON for its code
  - [services/agent/src/autobots/adapters/tool_middleware.py:28-58](../../../../services/agent/src/autobots/adapters/tool_middleware.py#L28): The same hooks typed Any; content=result.for_model() (44)
  - [services/agent/src/autobots/application/goal_loop.py:229-243](../../../../services/agent/src/autobots/application/goal_loop.py#L229): The pairing depends on list order
- **Evidence:**

  ```text
  async def awrap_tool_call(
      self, request: Any, handler: Callable[[Any], Awaitable[Any]]
  ) -> ToolMessage:
      ...
      code = json.loads(reply.content).get("code")      # loop_middleware.py:668
  ```

  Counted with ast: 12 hook and helper signatures take request or handler as Any (9 in loop_middleware.py, 3 in tool_middleware.py). LangChain types this handler as returning ToolMessage | Command[Any] (langchain/agents/middleware/types.py:756-759).
- **Why it matters:** With Any, mypy can't see that a handler may return a Command, which has no content, or that LoopMiddleware depends on the inner middleware's JSON format. Reordering the middleware list, or adding a middleware between the two, would fail at runtime. Neither class documents the required order.
- **Recommendation:** Annotate the hooks with ModelRequest, ModelResponse and ToolCallRequest from langchain.agents.middleware.types, and type the connection as psycopg's AsyncConnection or a small Protocol. Have GatewayMiddleware set ToolMessage.artifact to {outcome, code}, and have LoopMiddleware read it after an isinstance check. State the ordering requirement in both class docstrings.
- **Rule check:** DH-06: typing exceptions stay narrow and documented. The model still sees only ToolResult.for_model(). The artifact carries an outcome and a code and no secrets, so checkpoint contents stay safe.
- **Verification:** revised. Recounted with ast: 12 signatures, not 13; LangChain's ToolMessage | Command[Any] handler type confirmed in the installed langchain/agents/middleware/types.py:756-760.

```text
# GatewayMiddleware
return ToolMessage(content=result.for_model(), artifact={"outcome": result.outcome.value,
                   "code": result.code}, tool_call_id=call["id"], name=call["name"], status=...)
# LoopMiddleware (outer; GatewayMiddleware must be the inner middleware)
async def awrap_tool_call(self, request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]) -> ToolMessage:
    reply = await handler(request)
    if not isinstance(reply, ToolMessage) or not isinstance(reply.artifact, dict):
        raise LoopStopped("tool_reply_unrecognized")
    code = reply.artifact.get("code")
```

### <a id="padp-17"></a>PADP-17: A naive `since`, which the input contract accepts, crashes the pull-request filter

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/adapters/github_reads.py:47-50](../../../../services/agent/src/autobots/adapters/github_reads.py#L47): Compares an aware GitHub timestamp with since
  - [services/agent/src/autobots/adapters/github_reads.py:97-98](../../../../services/agent/src/autobots/adapters/github_reads.py#L97): Call site in pull_requests
  - [services/agent/src/autobots/contracts/tools.py:86](../../../../services/agent/src/autobots/contracts/tools.py#L86): since: datetime | None
- **Evidence:**

  ```text
  def _after(value: str | None, since: datetime | None) -> bool:
      if since is None or value is None:
          return True
      return datetime.fromisoformat(value.replace("Z", "+00:00")) >= since
  ```

  Reproduced with the service venv: GithubListPullRequestsInput(since='2026-01-01') parses to a naive datetime, and _after('2026-02-01T00:00:00Z', since) raises TypeError: can't compare offset-naive and offset-aware datetimes.
- **Why it matters:** A model that sends a date-only or offset-less since, which the schema accepts, gets the generic tool_failed after one retry instead of results. DH-06 and the python-worker rule require explicit UTC.
- **Recommendation:** Treat a naive since as UTC in the adapter, say so in the tool description, and add tests for date-only and offset-less values. Use AwareDatetime for since fields in the next version of these tools rather than changing the pinned v1 schema.
- **Rule check:** DH-06 and the python-worker rule require explicit UTC. Grants pin the v1 input schema, so the fix normalizes in the adapter instead of changing a published contract; a stricter AwareDatetime belongs in a new tool version (py-domain).
- **Verification:** confirmed. Reproduced with the service venv: date-only and offset-less since values parse naive and _after raises TypeError; a Z-suffixed value works.

```text
def _after(value: str | None, since: datetime | None) -> bool:
    if since is None or value is None:
        return True
    floor = since if since.tzinfo is not None else since.replace(tzinfo=UTC)   # a date-only since is naive
    return datetime.fromisoformat(value) >= floor                             # 3.11+ reads the Z suffix
```

### <a id="padp-18"></a>PADP-18: The most complex connector, the gateway middleware and storage have no fast unit tests

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 4
- **Where:**
  - [services/agent/src/autobots/adapters/github_pulls.py:68](../../../../services/agent/src/autobots/adapters/github_pulls.py#L68): No importer in services/agent/tests
  - [services/agent/src/autobots/adapters/tool_middleware.py:19](../../../../services/agent/src/autobots/adapters/tool_middleware.py#L19): Exercised only by tests/db scripts
  - [services/agent/src/autobots/adapters/object_storage.py:29](../../../../services/agent/src/autobots/adapters/object_storage.py#L29): Exercised only by tests/db and tests/web scripts
  - [services/agent/src/autobots/adapters/remote_files.py:29](../../../../services/agent/src/autobots/adapters/remote_files.py#L29): Exercised only by tests/db/web_tools_check.py
  - [tests/db/pull_request_check.py:1-2](../../../../tests/db/pull_request_check.py#L1): db-profile JSON cases with a fake GitHub
  - [services/agent/tests/test_result_stream.py:20-35](../../../../services/agent/tests/test_result_stream.py#L20): partial_object fed only well-formed prefixes
- **Evidence:** A grep over services/agent/tests finds no import of github_pulls, tool_middleware, object_storage or remote_files; remote_files appears only as the tool ID string in test_tool_catalog.py:158. github_pulls runs only in tests/db/pull_request_check.py. That script's cases cover approval, the diff, the branch, the marker, a lost reply, readback and a moved base, but no refused or unclear reply at the tree, commit or ref write.
- **Why it matters:** A refactor of the most complex connector (complexity 37) can be proven only on Docker with a disposable database, and the write-step failure paths that decide failed versus unknown aren't proven at all. The malformed-escape defect in the tap survived because the parser had no malformed-input tests.
- **Recommendation:** Before refactoring, add fast tests that use httpx.MockTransport and a small fake connection that records SQL. Cover refused and unclear replies at each PR write step, an existing branch without a pull request, a readback with none open, and content_at on a directory. Add tests for GatewayMiddleware's granted-tool filter and its synchronous refusal, for SupabaseObjectStore's path scoping and status mapping, and for partial_object over every prefix of valid and malformed objects.
- **Rule check:** python-worker rule: fake transports and no paid calls. The refactor plan's principle requires tests first for medium-risk changes.
- **Verification:** confirmed. No services/agent/tests file imports github_pulls, tool_middleware, object_storage or remote_files; pull_request_check.py has no refused or unclear write case.

```text
services/agent/tests/test_github_pulls.py   fake Git + recording connection: refused/unclear at the
    tree, commit, ref and pull writes; base moved; branch exists without a pull; readback -> NotDelivered
services/agent/tests/test_tool_middleware.py  granted-only tools, synchronous refusal, refusing tool bodies
services/agent/tests/test_object_storage.py   scoped paths, 'exists' -> False, 404 -> None
services/agent/tests/test_result_stream.py    partial_object over every prefix, valid and malformed
```

### <a id="padp-15"></a>PADP-15: The URL guard checks one DNS answer and then lets httpx resolve the name again

- **Severity** low · **Dimension** approach · **Effort** M · **Risk** high · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/adapters/url_guard.py:1-7](../../../../services/agent/src/autobots/adapters/url_guard.py#L1): Docstring: no tool can reach loopback, a private network or cloud metadata
  - [services/agent/src/autobots/adapters/url_guard.py:67-79](../../../../services/agent/src/autobots/adapters/url_guard.py#L67): First resolution, through the resolver
  - [services/agent/src/autobots/adapters/url_guard.py:115-136](../../../../services/agent/src/autobots/adapters/url_guard.py#L115): httpx resolves again and sends; the peer check runs after the request and is skipped without a peer
  - [services/agent/src/autobots/adapters/egress_proxy.py:97-99](../../../../services/agent/src/autobots/adapters/egress_proxy.py#L97): The proxy returns the address it checked
  - [services/agent/src/autobots/adapters/egress_proxy.py:161-162](../../../../services/agent/src/autobots/adapters/egress_proxy.py#L161): and connects to that address
- **Evidence:**

  ```text
  answers = await resolver(host, port)                         # url_guard.py:72, first resolution
  async with client.stream("GET", current) as reply:           # :121, httpx resolves and sends
      stream = reply.extensions.get("network_stream")
      peer = stream.get_extra_info("server_addr") if stream is not None else None
      if peer and not public(str(peer[0])):
          raise UrlRefused("url_host_refused")
  ```
- **Why it matters:** Suppose a name answers public to the check and private to the connection (DNS rebinding). The guard's own check then proves nothing about the connection, and when the stream reports no peer nothing is checked at all. In practice the https-only rule and httpx's default certificate verification keep the request line and headers from being sent unless the private address presents a valid certificate for the requested name, so the realistic exposure is a connection and TLS handshake to a private address. The docstring's 'every refusal is a typed code raised before the request it refuses' is stronger than the code: UG-01 is met by TLS, not by the guard. store_remote_file fetches through this path.
- **Recommendation:** Connect to the vetted address, as the egress proxy already does. Have check_url return the public address it checked, then request that address with the original Host header and httpx's sni_hostname extension (the installed httpcore 1.0.9 supports it), so TLS still verifies the name. Keep the peer check, and refuse when no peer is reported. Add a test whose resolver answers public first and private second. Until then, say in the module docstring that certificate verification, not the guard, stops a rebound name.
- **Rule check:** PRD-Tool-Catalog UG-01 ('a refusal is a typed code before any request') and BX-03's 'a connection to the address it checked'. The change enforces both on the worker side and relaxes nothing.
- **Verification:** revised. Double resolution and the post-request peer check confirmed, but https with httpx's default certificate verification blocks a rebound request in practice, so severity lowered to low and the impact reworded.

```text
vetted = await check_url(current, resolver)      # host, port and the public address it checked
async with client.stream("GET", vetted.address_url, headers={"Host": vetted.host_header},
                         extensions={"sni_hostname": vetted.host}) as reply:
    peer = ...                                   # defense in depth
    if peer is None or not public(str(peer[0])):
        raise UrlRefused("url_host_refused")
```

### <a id="padp-19"></a>PADP-19: Seven `*target` definitions under five names cover three ideas in the GitHub connectors

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/adapters/github_issues.py:75-98](../../../../services/agent/src/autobots/adapters/github_issues.py#L75): attempt_target returns the repository and token
  - [services/agent/src/autobots/adapters/github_issues.py:112-124](../../../../services/agent/src/autobots/adapters/github_issues.py#L112): approval_target returns the label recorded on the approval
  - [services/agent/src/autobots/adapters/github_issues.py:154-163](../../../../services/agent/src/autobots/adapters/github_issues.py#L154): Closures review_target, target and resolve_target
  - [services/agent/src/autobots/adapters/github_pulls.py:261-266](../../../../services/agent/src/autobots/adapters/github_pulls.py#L261): A second review_target, unvalidated, and a second resolve_target
  - [services/agent/src/autobots/application/tool_gateway.py:356-359](../../../../services/agent/src/autobots/application/tool_gateway.py#L356): resource_target's value is replaced whenever a target_resolver is set
- **Evidence:** The issues module validates with REPOSITORY_VARIABLE and _REPOSITORY.fullmatch (154-157). The pulls copy does not:

  ```text
  def review_target(_arguments: Any) -> str | None:              # github_pulls.py:261-263
      repository = environ.get("GITHUB_REPOSITORY", "")
      return f"{TARGET_PREFIX}{repository}" if repository else None
  ```
- **Why it matters:** Three ideas (this attempt's repository and token, the label an approval records, and the label a reviewer is shown) share one word, so a reader has to trace each function to learn which one returns credentials. Both review_target closures are dead in practice: the gateway replaces resource_target's value with target_resolver's whenever a resolver is set (tool_gateway.py:356-359), as it is for both GitHub writes. The unvalidated pulls copy is therefore never shown, but it still has to be read and kept in step.
- **Recommendation:** Delete both review_target closures, since target_resolver supersedes them. Name the remaining functions by what they return and define each once in the GitHub connector module: attempt_credentials (was attempt_target) and approval_label (was approval_target), wired to ToolDefinition's target_resolver.
- **Rule check:** ToolDefinition's resource_target and target_resolver fields are the gateway's API and keep their names.
- **Verification:** revised. Definitions confirmed, but tool_gateway.py:356-359 always replaces resource_target's value with target_resolver's, so the unvalidated pulls copy is never shown; the recommendation now removes both closures.

```text
async def attempt_credentials(context, environ) -> tuple[str, str]   # was attempt_target
async def approval_label(context, environ) -> str                   # was approval_target
# both review_target closures removed: the gateway records target_resolver's label (approval_label)
```

### <a id="padp-20"></a>PADP-20: The proxy's copy of the public-address check has no parity test with the URL guard's

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/adapters/egress_proxy.py:33-46](../../../../services/agent/src/autobots/adapters/egress_proxy.py#L33): public and system_resolver, 'as the worker's URL guard decides it'
  - [services/agent/src/autobots/adapters/url_guard.py:34-48](../../../../services/agent/src/autobots/adapters/url_guard.py#L34): The originals
  - [services/agent/tests/test_url_guard.py:200-204](../../../../services/agent/tests/test_url_guard.py#L200): Tests url_guard.public alone
  - [services/agent/tests/test_browser_executor.py:157-159](../../../../services/agent/tests/test_browser_executor.py#L157): Checks only that the proxy imports nothing from Autobots
- **Evidence:** egress_proxy.public (33-41) repeats url_guard.public (39-48) line for line, and system_resolver is repeated as well (44-46 and 34-36). The proxy's decisions are tested through decide (test_browser_executor.py:41-64), and url_guard.public is tested directly; no test compares the two.
- **Why it matters:** The copy is deliberate, because the sidecar must use only the standard library. But if one copy changes what counts as public and the other doesn't, the browser and the fetch tools will disagree about what is private.
- **Recommendation:** Keep both copies and add one parametrized test that runs both functions over a shared table (private, CGNAT, link-local and metadata, multicast, IPv4-mapped IPv6, scoped IPv6, documentation ranges and garbage) and asserts equal answers.
- **Rule check:** Decision 0018 B3 and the sidecar's standard-library-only constraint (test_browser_executor.py:157) stay in place; the test imports both modules from the worker's test suite.
- **Verification:** confirmed. egress_proxy.public and system_resolver repeat url_guard's line for line, and no test compares them.

```text
@pytest.mark.parametrize("address", ["93.184.215.14", "127.0.0.1", "10.0.0.1", "100.64.0.1",
    "169.254.169.254", "224.0.0.1", "::1", "fe80::1%eth0", "::ffff:127.0.0.1", "2001:db8::1", "junk"])
def test_the_proxy_and_the_guard_agree_on_public(address: str) -> None:
    assert egress_proxy.public(address) == url_guard.public(address)
```

### <a id="padp-21"></a>PADP-21: Two superseded credential helpers remain: one unused and one called only by tests

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/adapters/github_issues.py:63-69](../../../../services/agent/src/autobots/adapters/github_issues.py#L63): configured_target: no caller in the repository
  - [services/agent/src/autobots/adapters/provider_http.py:20-25](../../../../services/agent/src/autobots/adapters/provider_http.py#L20): provider_key: environment-only
  - [services/agent/tests/test_tool_catalog.py:224-238](../../../../services/agent/tests/test_tool_catalog.py#L224): Its only service-test caller
  - [tests/db/provider_key_check.py:79](../../../../tests/db/provider_key_check.py#L79): Its only other caller
- **Evidence:** grep finds no caller of github_issues.configured_target outside its definition. provider_http.provider_key is called only by the two tests listed. Tavily and Jina resolve keys with attempt_key (provider_http.py:28-40), which follows PK-04's workspace-first order through resolve_tool_key.
- **Why it matters:** Both helpers implement an environment-only resolution that production has replaced. Tests that pass on provider_key suggest coverage of a path no tool takes.
- **Recommendation:** Delete configured_target. Point the two tests at attempt_key or resolve_tool_key and delete provider_key, or move it into the test helpers if the db check needs an environment-only path.
- **Rule check:** PK-04 and Decisions 0024 and 0025 define the order production uses; removing the unused environment-only helpers changes nothing at runtime.
- **Verification:** confirmed. configured_target has no caller; provider_key is called only at test_tool_catalog.py:230 and 238 and tests/db/provider_key_check.py:79.

## Rejected during verification

None. Every finding held up at its cited lines and was kept. Where a count, an excerpt, a location, the wording of the impact or the severity changed, the finding is marked revised and its verification line says what changed.

## Not covered

mypy and pytest were not run because they are not among the permitted commands. .checks/fast/latest.json and .checks/full/latest.json report that ruff, mypy and pytest passed, at a revision not compared with this run. Two reproductions ran in memory with services/agent/.venv/bin/python -I -B: the tap with a fake stream and a fake notify, and the contract parsing and _after for a naive since. Neither touched a database, the network or a model. ruff check ran without --no-cache, so it refreshed the git-ignored services/agent/.ruff_cache; git status shows no change. The application modules the adapters call (tool_gateway, approvals, model_admission, model_attempts, tool_keys, goal_loop, browsing_tool, worker_inference) were read only around the cited lines; they belong to the py-tools and py-run areas. The Docker-backed behavior of browser_executor and egress_proxy and the live DNS behavior of url_guard were not exercised, so the rebinding finding comes from reading the code. The tests/db scripts were scanned only for which cases they cover. PRD-Development-Harness.md, option-b-contract.md, Decisions 0017 and 0018 and PRD-Tool-Catalog.md were read only in the relevant sections, and metrics.md through its tables and commands.
