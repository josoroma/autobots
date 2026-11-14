# Lens: errors, logging and view states

Errors in Autobots are safe but rarely diagnosable, and often misclassified. The API edge is strong: one {code, message} envelope with fixed messages, validation input never echoed, `raise ... from None` throughout, and a redacting local JSON logger behind every service log line. No `except` clause catches a cancellation, though one cleanup path's `suppress(BaseException)` can absorb one. The model-call path is the pattern to copy, with a FailureClass taxonomy, an explicit uncertain set, and logs that carry qualified error and cause types. Elsewhere, failures lose either their cause or their class:
- Every process boundary logs only the exception's class name, with no location, step or run.
- The tool gateway turns any unexpected tool exception into tool_failed or outcome_unknown, with no log line and, for effects, an empty failure_detail.
- A database outage during a request becomes a 500 instead of a retryable 503.
- On most screens, a contract mismatch, a denial and an outage reach the user as the same 'unavailable' message. This runs through hand-written loaders in 24 component files and 19 hand-cast error bodies, and 8 load failures tell a signed-in user to sign in whatever the cause.
- Refusals use four code conventions across 61 exception classes. Eleven route modules map them to HTTP, partly by string suffix.
- The codes cross the contract as plain strings, and one client key already matches nothing the service emits.

Most fixes centralize one thing: an error_fields helper, an OutcomeUnknown type with receipt detail, one Refusal base with a status table, and one typed loader with explicit view states.

[Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | DH-06's safety clauses are met (no leaks, redaction, cancellation not caught by any except clause). Its clauses on cause preservation, centralized handling and deliberate view states are not, and no lint rule guards blind or silent handlers. |
| modules | 3 | There is one response envelope and one logger, but refusal-to-status mapping lives in 11 route modules, and the web has no shared error or load-state module. |
| functions | 3 | Error mappers are small but blur roles: as_api_error ends in `raise error`, and settings mirrors it with a HANDLED tuple by hand. Screen loaders fetch, parse, classify and set state inline, and two screens write theirs twice. |
| approach | 3 | The model-call and worker paths classify failures deliberately, and so do workflow-monitor.tsx and continue-run.tsx. The tool gateway, the BFF and most screens collapse failure classes into one. |
| comments | 4 | About 10 of the 27 broad handlers that BLE001 reports carry a reason comment (retention.py:82, operations.py:154, dispatch.py:19), and most others log a named event. The silent ones carry none: the four in the tool gateway, experts.py:72 and tool_uses.py:103. |
| types | 2 | 61 exception classes use four code conventions and share no base. Error and stop codes are plain strings in the contract. The web hand-casts 19 error bodies, and ContractError doubles as an HTTP error. |
| errors | 3 | Errors are safe and almost always cancellation-correct. But causes are dropped at every boundary, unknown tool outcomes cannot be diagnosed, and outages, denials and contract drift are misreported to users. |
| tests | 3 | Tests pin that nothing leaks (test_api.py:137, test_operations.py:64), and tests/db asserts refusal codes by name. Nothing asserts that a cause is logged, that a tool defect is recorded, or that a screen tells denied from unavailable. |
| maintainability | 3 | The foundations are sound. A few central changes would remove most of the friction: a cause-fields helper, an outcome-unknown type, a refusal base and a shared loader. |

## Strengths

- **One safe error envelope at the API edge.** services/agent/src/autobots/api/errors.py:19-40 answers every failure with ErrorResponse {code, message} and fixed text, never echoes rejected input, and hides 500 details. Routes consistently raise `ApiError(...) from None` (e.g. api/approval_routes.py:153-158). services/agent/tests/test_api.py:124-153 pins both the no-echo and no-leak properties. Sources: [services/agent/src/autobots/api/errors.py:19-40](../../../../services/agent/src/autobots/api/errors.py#L19), [services/agent/src/autobots/api/approval_routes.py:153-158](../../../../services/agent/src/autobots/api/approval_routes.py#L153), [services/agent/tests/test_api.py:124-153](../../../../services/agent/tests/test_api.py#L124).
- **A redacting, local-only JSON logger behind every service log line.** services/agent/src/autobots/operations/logs.py:12-90 redacts secret shapes, shortens identifiers, drops uvicorn access lines and quiets httpx URLs. All 25 log_event calls go through it, and no service path prints, only CLI entry points. Pinned by services/agent/tests/test_operations.py:38-79. Sources: [services/agent/src/autobots/operations/logs.py:12-90](../../../../services/agent/src/autobots/operations/logs.py#L12), [services/agent/tests/test_operations.py:38-79](../../../../services/agent/tests/test_operations.py#L38).
- **A real failure taxonomy for model calls.** services/agent/src/autobots/application/model_attempts.py:17-73 defines FailureClass, classify_status (MP-08's table) and the UNCERTAIN set. services/agent/src/autobots/adapters/loop_middleware.py:308-346 logs uncertain calls with the module-qualified error type, the cause type and the status, and never a message. This is the model for the tool path and for logging generally. Sources: [services/agent/src/autobots/application/model_attempts.py:17-73](../../../../services/agent/src/autobots/application/model_attempts.py#L17), [services/agent/src/autobots/adapters/loop_middleware.py:308-346](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L308).
- **Worker process boundaries that fail soft and reconnect.** services/agent/src/autobots/operations/worker.py:74-169 runs on autocommit connections and re-raises psycopg.OperationalError to the reconnect loop. Drain has a deadline, and the cancelled heartbeat is awaited (worker.py:158-160). Per-item isolation names the item: application/routines.py:478-488. Sources: [services/agent/src/autobots/operations/worker.py:74-169](../../../../services/agent/src/autobots/operations/worker.py#L74), [services/agent/src/autobots/operations/worker.py:158-160](../../../../services/agent/src/autobots/operations/worker.py#L158), [services/agent/src/autobots/application/routines.py:478-488](../../../../services/agent/src/autobots/application/routines.py#L478).
- **No except clause catches a cancellation.** No `except CancelledError` exists in services/agent/src, and every `except Exception` leaves cancellation alone. The three `except BaseException` handlers settle the qualification ledger and re-raise (operations/route_qualification.py:277-284, 302-306, 394-400). The one context manager that can absorb a cancellation is `suppress(BaseException)` at application/browsing_tool.py:142 (XERR-13). Sources: [services/agent/src/autobots/operations/route_qualification.py:277-284](../../../../services/agent/src/autobots/operations/route_qualification.py#L277), [services/agent/src/autobots/operations/route_qualification.py:302-306](../../../../services/agent/src/autobots/operations/route_qualification.py#L302), [services/agent/src/autobots/operations/route_qualification.py:394-400](../../../../services/agent/src/autobots/operations/route_qualification.py#L394), [services/agent/src/autobots/application/browsing_tool.py:141-143](../../../../services/agent/src/autobots/application/browsing_tool.py#L141).
- **Unknown is a first-class state.** application/operations.py:153-160 returns *_unknown conditions when the database can't answer instead of guessing. apps/web/components/readiness.tsx:17-29 renders unknown distinctly. Tool receipts separate 'failed for certain' from 'unknown' (application/tool_gateway.py:24-33). Sources: [services/agent/src/autobots/application/operations.py:153-160](../../../../services/agent/src/autobots/application/operations.py#L153), [apps/web/components/readiness.tsx:17-29](../../../../apps/web/components/readiness.tsx#L17), [services/agent/src/autobots/application/tool_gateway.py:24-33](../../../../services/agent/src/autobots/application/tool_gateway.py#L24).
- **Deliberate connection states on the run page, and a loader worth promoting.** apps/web/components/run-workspace.tsx:168-279 models loading, reconnecting with cursor replay, live, ended and gap, and deduplicates by sequence. apps/web/components/tool-catalog.tsx:156-181 has a typed useLoaded union with an AbortController, the best basis for a shared loader. Two more screens already classify failures: workflow-monitor.tsx:44-48 reconnects on 5xx and network errors, and continue-run.tsx:47-51 treats a 5xx after a write as an unknown outcome. Sources: [apps/web/components/run-workspace.tsx:168-279](../../../../apps/web/components/run-workspace.tsx#L168), [apps/web/components/tool-catalog.tsx:156-181](../../../../apps/web/components/tool-catalog.tsx#L156), [apps/web/components/workflow-monitor.tsx:44-48](../../../../apps/web/components/workflow-monitor.tsx#L44), [apps/web/components/continue-run.tsx:47-51](../../../../apps/web/components/continue-run.tsx#L47).
- **Many handlers explain why.** About 10 of the 27 broad handlers that BLE001 reports carry a reason comment: application/retention.py:82, adapters/result_stream.py:242, application/operations.py:154, application/goal_loop.py:536, application/routines.py:481, operations/route_qualification.py:527, operations/reasoning_trial.py:259 and .claude/hooks/dispatch.py:19 and 235. The BaseException handler at route_qualification.py:282 does too. Sources: [services/agent/src/autobots/application/retention.py:82](../../../../services/agent/src/autobots/application/retention.py#L82), [services/agent/src/autobots/adapters/result_stream.py:242](../../../../services/agent/src/autobots/adapters/result_stream.py#L242), [services/agent/src/autobots/application/operations.py:154](../../../../services/agent/src/autobots/application/operations.py#L154), [services/agent/src/autobots/application/goal_loop.py:536](../../../../services/agent/src/autobots/application/goal_loop.py#L536), [services/agent/src/autobots/application/routines.py:481](../../../../services/agent/src/autobots/application/routines.py#L481), [services/agent/src/autobots/operations/route_qualification.py:527](../../../../services/agent/src/autobots/operations/route_qualification.py#L527), [.claude/hooks/dispatch.py:19](../../../../.claude/hooks/dispatch.py#L19), [.claude/hooks/dispatch.py:235](../../../../.claude/hooks/dispatch.py#L235).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [XERR-01](#xerr-01) | high | errors | Private logs keep only the exception's class name, so no failure can be located without reproducing it | M | medium |
| [XERR-02](#xerr-02) | high | errors | The tool gateway turns any unexpected tool exception into a bare code, with no log line and no receipt detail | M | medium |
| [XERR-03](#xerr-03) | high | types | The web reports a contract mismatch as an outage, or hangs on it, and nothing records which field failed | M | medium |
| [XERR-04](#xerr-04) | medium | errors | Screens collapse every load failure into one message, so denied, unavailable and retryable are not represented | M | medium |
| [XERR-05](#xerr-05) | medium | errors | The BFF and its session helpers report an Auth outage as a wrong password, a stopped API as signed out, and a timeout as unavailable, with no server trace | M | medium |
| [XERR-06](#xerr-06) | medium | errors | A database outage during a request becomes a 500 internal_error, after up to 30 seconds, instead of a retryable 503 | S | medium |
| [XERR-07](#xerr-07) | medium | modules | Exception classes use four code conventions with no shared base, and 11 route modules map refusals to HTTP, partly by string suffix | L | medium |
| [XERR-08](#xerr-08) | medium | types | Error and stop codes are plain strings in the contract, so client code maps drift without a type error | M | medium |
| [XERR-09](#xerr-09) | medium | duplication | Nineteen hand-cast error bodies instead of the generated parseErrorResponse, with two competing policies for error wording | S | low |
| [XERR-10](#xerr-10) | medium | errors | A run whose processing raises leaves no durable reason, and nothing bounds how often it is reclaimed | M | high |
| [XERR-11](#xerr-11) | medium | errors | Failures the code deliberately tolerates leave no trace, and contextlib.suppress hides them from the blind-except count | S | low |
| [XERR-12](#xerr-12) | medium | standards | Log events follow no shared convention: field names, levels, rate limits and context keys differ for the same condition | M | low |
| [XERR-13](#xerr-13) | medium | errors | One cleanup path can discard the caller's cancellation, and task cleanup idioms differ across modules | S | medium |
| [XERR-14](#xerr-14) | medium | standards | No lint gate covers blind or silent handlers, and the only BLE001 markers suppress a rule nothing runs | S | low |
| [XERR-15](#xerr-15) | low | errors | Broad catches where a precise type exists turn defects into user refusals, and one qualifier saves exception text | S | low |

### <a id="xerr-01"></a>XERR-01: Private logs keep only the exception's class name, so no failure can be located without reproducing it

- **Severity** high · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 16
- **Where:**
  - [services/agent/src/autobots/operations/logs.py:64-66](../../../../services/agent/src/autobots/operations/logs.py#L64): JsonFormatter keeps the exc_info class name and drops the traceback and cause chain
  - [services/agent/src/autobots/api/errors.py:38-40](../../../../services/agent/src/autobots/api/errors.py#L38): The 500 handler logs nothing. Starlette re-raises after it, and uvicorn's 'Exception in ASGI application' line, reduced to the class name with no route, is the only trace.
  - [services/agent/src/autobots/operations/worker.py:143-149](../../../../services/agent/src/autobots/operations/worker.py#L143): worker.step_failed at ERROR names no step, run or location (again at 276-277)
  - [services/agent/src/autobots/application/routines.py:480-488](../../../../services/agent/src/autobots/application/routines.py#L480): Per-routine isolation logs the routine id and the class name only
  - [services/agent/src/autobots/application/retention.py:171-172](../../../../services/agent/src/autobots/application/retention.py#L171): Per-workspace isolation logs the class name without the workspace
  - [services/agent/src/autobots/adapters/loop_middleware.py:319-328](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L319): The only helper that adds a qualified type and the cause's type, used for model calls only
  - [.claude/hooks/dispatch.py:235-237](../../../../.claude/hooks/dispatch.py#L235): One fixed sentence for every failure, so a defect reads like bad input
  - [services/agent/tests/test_operations.py:64-79](../../../../services/agent/tests/test_operations.py#L64): Pins the no-message half (error == 'RuntimeError'). Nothing pins the cause half.
- **Evidence:** Count: 13 log_event calls pass error=type(error).__name__ (rg over services/agent/src: 5 in worker.py, 3 in operations.py, and one each in result_stream.py, goal_loop.py, worker_inference.py, routines.py and retention.py), plus the formatter, the 500 handler and the hook.

  ```python
  # operations/logs.py:64-66
  if record.exc_info and record.exc_info[0] is not None:
      entry["error"] = record.exc_info[0].__name__
  # api/errors.py:38-40
  @app.exception_handler(Exception)
  async def unexpected(_request: Request, _error: Exception) -> JSONResponse:
      return _response(500, "internal_error", "Something went wrong.")
  ```

- **Why it matters:** DH-06 requires keeping causes in private logs, and PRD 12.2 keeps restricted raw diagnostic traces apart from public activity. Today an ERROR from the unattended worker reads {"event":"worker.step_failed","error":"KeyError"}, with no file, line, step or run. An unexpected API failure reads {"event":"Exception in ASGI application","error":"KeyError"}, with no route. Every diagnosis needs a reproduction, which slows fixes and makes it hard to confirm a regression is gone. The secrecy rationale covers messages, not frame locations or cause types, which carry no input.
- **Recommendation:** Keep the no-message rule and add message-free cause data in one place. Add error_fields(error) to operations/logs.py, returning:
  - the module-qualified type;
  - the types in the cause chain (bounded);
  - the last few traceback frames as package-relative path:line:function, never locals or messages.

  Use it in JsonFormatter for exc_info, replace the 13 error=type(error).__name__ arguments with **error_fields(error), and rebuild uncertain_call_fields on it. In api/errors.py, log api.unhandled at ERROR with the method and route template before returning 500. Let the hook print the exception type, which carries no input. Extend test_operations.py to require frames and forbid planted secrets, and add an API test that a 500 writes one api.unhandled line.
- **Rule check:** DH-06 (preserve causes in private logs) and PRD-LangChain-Deep-Agents 12.2 (restricted, redacted diagnostic traces). The recommendation keeps logs.py's no-message rule and its local stderr sink, adds no hosted tracing, and keeps the leak assertions in test_operations.py.
- **Verification:** confirmed. Every site re-read; rg finds exactly 13 class-name-only log calls, and the installed Starlette 1.10.0 re-raises after the 500 handler (middleware/errors.py:183-186), so uvicorn's reduced line is the only trace.

```text
operations/logs.py
  def error_fields(error: BaseException, frames: int = 6) -> dict[str, Any]
      # error_type 'builtins.KeyError', causes ['psycopg.OperationalError'],
      # frames ['autobots/application/goal_loop.py:357:run_goal', ...]; no messages, no locals
  JsonFormatter.format: if record.exc_info: entry.update(error_fields(record.exc_info[1]))
api/errors.py
  unexpected(request, error): log_event(logger, 'api.unhandled', logging.ERROR,
      method=request.method, route=<route template>, **error_fields(error))
worker.py, goal_loop.py, routines.py, retention.py, operations.py, result_stream.py, worker_inference.py
  log_event(..., **error_fields(error))   # replaces error=type(error).__name__
adapters/loop_middleware.py
  uncertain_call_fields(error) = error_fields(error) | {'status': ...}
```

### <a id="xerr-02"></a>XERR-02: The tool gateway turns any unexpected tool exception into a bare code, with no log line and no receipt detail

- **Severity** high · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 4
- **Where:**
  - [services/agent/src/autobots/application/tool_gateway.py:542-544](../../../../services/agent/src/autobots/application/tool_gateway.py#L542): An effect that raised is recorded as unknown, with failure_code and failure_detail left null
  - [services/agent/src/autobots/application/tool_gateway.py:422-423](../../../../services/agent/src/autobots/application/tool_gateway.py#L422): A read that raised becomes tool_failed and is retried, with nothing kept
  - [services/agent/src/autobots/application/tool_gateway.py:514-515](../../../../services/agent/src/autobots/application/tool_gateway.py#L514): A readback that raised falls through to unknown
  - [services/agent/src/autobots/application/tool_gateway.py:372-373](../../../../services/agent/src/autobots/application/tool_gateway.py#L372): A review detail that raised becomes review_unavailable
  - [supabase/migrations/20261105000030_tool_failure_diagnostics.sql:1-6](../../../../supabase/migrations/20261105000030_tool_failure_diagnostics.sql#L1): These columns were added so a stopped run can be diagnosed: a code and a category
  - [services/agent/src/autobots/adapters/github_issues.py:55-56](../../../../services/agent/src/autobots/adapters/github_issues.py#L55): UnclearReply, the adapters' deliberate 'can't tell' signal, lands in the same except Exception as a defect
  - [services/agent/src/autobots/adapters/github_pulls.py:48-49](../../../../services/agent/src/autobots/adapters/github_pulls.py#L48): A second class with the same name and purpose
  - [services/agent/src/autobots/adapters/loop_middleware.py:530-539](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L530): The model-call path logs worker.call_uncertain with error and cause types for the same 'may have happened' state
- **Evidence:** tool_gateway.py has no logger. Only plans.py ever supplies ToolFailed(detail=...), and nothing in services/agent/src or apps/web reads failure_detail.

  ```python
  # application/tool_gateway.py:542-544 (_attempt)
          except Exception:
              await _record(context, operation_id, "unknown", None)
              return ToolResult(ToolOutcome.UNKNOWN, "outcome_unknown", operation_id=operation_id)
  # tool_gateway.py:422-423 (_read)
              except Exception:
                  code = "tool_failed"
  ```

- **Why it matters:** An unknown effect is the state a person must reconcile against the destination's own records, and the receipt is the evidence they rule on. Today an unclear GitHub reply, a timeout and a KeyError from a changed provider payload all record the same unknown/outcome_unknown. The read path turns a parser defect into a retried tool_failed. External API drift at this trust boundary therefore shows up only as unexplained unknown effects. The failure_detail column, built for diagnosis, stays empty in exactly the case that needs it.
- **Recommendation:** Keep every outcome and retry decision as it is, and record why it happened.
  1. Add OutcomeUnknown(Exception) with a detail category to tool_gateway.py, for adapters that can't tell whether an effect happened. Define one UnclearReply as its subclass and use it in both GitHub adapters.
  2. Effects keep a receipt, so in _attempt and _replay set failure_detail to the OutcomeUnknown category, or to `defect:<qualified type>` for anything else.
  3. Reads and review denials keep no receipt (_denied records nothing), so _read and the review branch get the log line only.
  4. Log tool.operation.unknown (or .failed) with tool id, version, operation id and error_fields.
  5. Add gateway tests with a handler that raises KeyError and one that raises UnclearReply, asserting the receipt detail and the log line.
- **Rule check:** python-worker rule: reconcile unknown outcomes before retry, and replay is not exactly-once execution. Outcome classes, retries and receipt statuses stay as they are. Only the existing nullable failure_detail column (added by migration 20261105000030, which is not edited) gets filled, with a category and never model text, as its comment requires.
- **Verification:** revised. All four handlers, the null detail and the two UnclearReply classes confirmed. Revised: only effects have receipts (_denied at tool_gateway.py:242-243 records nothing, and _read keeps none), so reads and review denials get a log line, not a detail.

```text
application/tool_gateway.py
  class OutcomeUnknown(Exception): detail: str      # the tool can't tell; the outcome stays unknown
  def _diagnosis(error) -> str: OutcomeUnknown -> error.detail; else 'defect:' + qualified type
  _attempt / _replay: except Exception as error:
      await _record(context, op, 'unknown', None, 'outcome_unknown', _diagnosis(error))
      log_event(logger, 'tool.operation.unknown', logging.WARNING, tool=..., operation=..., **error_fields(error))
  _read / review branch: the same log line; no receipt exists, outcome codes unchanged
adapters/github_issues.py, github_pulls.py
  UnclearReply(OutcomeUnknown), defined once and imported by both
```

### <a id="xerr-03"></a>XERR-03: The web reports a contract mismatch as an outage, or hangs on it, and nothing records which field failed

- **Severity** high · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 60
- **Where:**
  - [packages/api-client/src/runtime.ts:22-30](../../../../packages/api-client/src/runtime.ts#L22): ContractError carries the failing path
  - [packages/api-client/src/runtime.ts:168-170](../../../../packages/api-client/src/runtime.ts#L168): requestJson throws the same ContractError for an HTTP status, so drift and refusal look alike
  - [apps/web/components/tool-catalog.tsx:156-181](../../../../apps/web/components/tool-catalog.tsx#L156): useLoaded: a parse failure becomes 'unavailable', shown as 'Check that the local service is running.'
  - [apps/web/components/run-list.tsx:189-202](../../../../apps/web/components/run-list.tsx#L189): A parse failure becomes 'Runs are unavailable. Sign in, and check that the local API is running.'
  - [apps/web/components/run-workspace.tsx:183-196](../../../../apps/web/components/run-workspace.tsx#L183): refresh parses with no catch
  - [apps/web/components/run-workspace.tsx:274](../../../../apps/web/components/run-workspace.tsx#L274): void start(): a throw leaves 'Loading this run.' forever, with no retry
  - [apps/web/components/waiting-notifier.tsx:46-48](../../../../apps/web/components/waiting-notifier.tsx#L46): A parse throw inside void poll() skips the reschedule at line 71, so notifications stop until reload or a setting change
  - [apps/web/lib/service-status.ts:42-49](../../../../apps/web/lib/service-status.ts#L42): Server-side calls swallow ContractError into 'unavailable' or null, with no server log
- **Evidence:** Count: generated parsers are used at 60 sites in 25 component files, counted outside import statements; 44 of them are the literal parse*(await reply.json()) form, in 20 files. ContractError is referenced 0 times and console.* is called 0 times in app, components and lib.

  ```tsx
  // components/tool-catalog.tsx:163-174 (abridged)
  fetch(path, { cache: "no-store", signal: controller.signal })
    .then(async (reply) => {
      if (!reply.ok) { setState({ kind: "unavailable" }); return; }
      setState({ kind: "ready", value: parse(await reply.json()) });
    })
    .catch(() => { if (active) setState({ kind: "unavailable" }); });
  ```

- **Why it matters:** The generated parsers exist so that drift fails loudly at the boundary; the contracts rule says TypeScript types do not validate JSON. Every screen catches that failure with the same handler as a network error and tells the user to sign in or start the API. After a partial upgrade, a renamed field looks like an outage, the run page can stay on 'Loading this run.' with no retry, and the waiting notifier stops until the page reloads or the setting changes. Meanwhile the browser console and the server logs stay empty.
- **Recommendation:** Separate the failure kinds at the client boundary, and report the one only developers can fix.
  1. In runtime.ts, add an HttpError (status, code) for non-ok replies, so ContractError means drift only. packages/api-client/tests/contract.test.ts:33-36 pins ContractError for a failed status today and changes with it.
  2. Add apps/web/lib/load.ts (loadJson) and move useLoaded from tool-catalog.tsx into lib. Return a union with a contractMismatch kind, which calls console.error with ContractError.path (no values) and shows 'This page and the local service disagree. Reload after updating.'
  3. Wrap the run page's start and refresh and the notifier's poll so a throw sets that state instead of rejecting.
  4. In service-status.ts, log the mismatch on the server.
- **Rule check:** contracts rule (TypeScript types do not validate JSON) and nextjs rule (runtime parsing at untrusted boundaries). The generated parsers and generated.ts stay untouched; runtime.ts is the hand-written runtime that generated.ts imports (packages/api-client/README.md says so). No business state moves into Next.js.
- **Verification:** revised. The hangs are traced from the code (unhandled rejections from void start() and void poll()), not observed. Revised: counts redone with an import-stripping scan, and the contract test that pins ContractError for a failed status is named as part of the change.

```text
packages/api-client/src/runtime.ts
  export class HttpError extends Error { status: number; code?: string }   // requestJson throws this when !ok
apps/web/lib/load.ts
  type LoadResult<T> = {kind:'ready', value:T} | {kind:'signedOut'} | {kind:'denied'} | {kind:'notFound'}
                     | {kind:'unavailable', retry:true} | {kind:'contractMismatch', path:string}
  async function loadJson<T>(path, parse, init?): Promise<LoadResult<T>>
apps/web/lib/use-loaded.ts      // moved from tool-catalog.tsx, built on loadJson, returns {state, reload}
apps/web/components/ui/load-state.tsx  // one renderer for every non-ready kind
```

### <a id="xerr-04"></a>XERR-04: Screens collapse every load failure into one message, so denied, unavailable and retryable are not represented

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 24
- **Where:**
  - [apps/web/components/run-list.tsx:283-299](../../../../apps/web/components/run-list.tsx#L283): One failed boolean covers every cause
  - [apps/web/components/experts-panel.tsx:160-164](../../../../apps/web/components/experts-panel.tsx#L160): 'Sign in, then try again.' for any failure, with no retry control
  - [apps/web/components/approvals-panel.tsx:136-187](../../../../apps/web/components/approvals-panel.tsx#L136): The loader is written twice, and setCounts runs twice in a row at 170-171
  - [apps/web/components/operations-panel.tsx:165-206](../../../../apps/web/components/operations-panel.tsx#L165): The only screen that names 403; its loader is also written twice
  - [apps/web/components/operations-panel.tsx:208-222](../../../../apps/web/components/operations-panel.tsx#L208): save has no rejection handler and shows one validation sentence for 403 and 503 alike
  - [apps/web/components/tool-catalog.tsx:587-593](../../../../apps/web/components/tool-catalog.tsx#L587): ToolDetail says 'isn't in the catalog' for any failure, including an outage
  - [apps/web/components/run-list.tsx:210-220](../../../../apps/web/components/run-list.tsx#L210): loadMore uses try/finally with no catch, so it fails silently or rejects unhandled
  - [apps/web/components/workflow-monitor.tsx:44-48](../../../../apps/web/components/workflow-monitor.tsx#L44): The read pattern to copy: 5xx and network errors reconnect, any other refusal is unavailable
- **Evidence:** Counts: 24 component files load in a mount effect (30 effects, by a brace-matching scan of useEffect bodies that fetch or call a loader); only tool-catalog.tsx shares one hook between its reads. 4 branch on 401, 403 or 404, 2 treat 5xx deliberately (workflow-monitor.tsx:44 reconnects, continue-run.tsx:48 reports an unknown outcome), and none branches on 409. 8 load-failure messages advise signing in whatever the cause. data-state markers appear in 11 of 50 component files.

  ```tsx
  // components/experts-panel.tsx:37-45 (abridged)
  fetch("/api/v1/experts", { cache: "no-store" })
    .then(async (reply) => {
      if (reply.ok) setExperts(parseExpertList(await reply.json()).experts);
      else setFailed(true);
    })
    .catch(() => { if (active) setFailed(true); });
  // failed renders 'Experts could not be loaded. Sign in, then try again.'
  ```

- **Why it matters:** DH-06 asks for loading, empty, denied, unavailable and retryable states represented deliberately. A signed-in user facing a stopped API is told to sign in. A non-owner and an outage look the same on most screens: only Operations names 403, and only the workflow monitor separates 5xx from other refusals. 'Try again' is text without a control, so recovery means a full reload. Each new screen copies a loader and invents its wording, and the copies already drift: approvals and operations write their loader twice, approvals sets its counts twice in a row, and ToolDetail calls an outage 'not in the catalog'.
- **Recommendation:** Build on the loader proposed in XERR-03.
  - Use one status-to-kind table for reads: 401 signed out, 403 denied, 404 not found, 409 conflict, 5xx or network unavailable with retry, parse failure contract mismatch. workflow-monitor.tsx:44-48 already does the 5xx part.
  - Add one LoadState component with fixed wording per kind, data-state markers, and a Retry button that re-runs the loader.
  - Migrate screens as they are touched, starting with approvals and operations, whose loaders are written twice.
  - Keep empty states in each screen, since their wording is domain-specific.
  - Give secondary actions (run-list loadMore, operations save) the same refusal reader, so they never fail silently or with an unrelated message. For writes, keep continue-run.tsx:47-51's rule that a 5xx proves no more than a lost reply.
- **Rule check:** DH-06 Next.js (represent loading, empty, denied, unavailable and retryable states deliberately) and the nextjs rule (explicit error, empty and loading states). Retry re-reads durable state and schedules nothing in the browser.
- **Verification:** revised. The duplicated approvals and operations loaders, the double setCounts and the eight sign-in messages confirmed. Revised: two screens do branch on 5xx (workflow-monitor.tsx:44, continue-run.tsx:48), so 'none on 503' was wrong; loader counts restated from a fresh scan.

```text
apps/web/lib/use-loaded.ts
  useLoaded(path, parse) -> { state: LoadResult<T>, reload(): void }
apps/web/components/ui/load-state.tsx
  <LoadState state={state} noun='Experts' onRetry={reload} />   // role=status|alert, data-state, Retry
screens keep only their ready branch and their own empty text
```

### <a id="xerr-05"></a>XERR-05: The BFF and its session helpers report an Auth outage as a wrong password, a stopped API as signed out, and a timeout as unavailable, with no server trace

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 4
- **Where:**
  - [apps/web/app/api/session/route.ts:51-55](../../../../apps/web/app/api/session/route.ts#L51): Any Auth error, including AuthRetryableFetchError when Auth is down, becomes 401 'That email and password did not work.'
  - [apps/web/lib/service-status.ts:52-61](../../../../apps/web/lib/service-status.ts#L52): fetchSession returns null both when signed out and when the API is unreachable
  - [apps/web/app/api/workspace/route.ts:40-43](../../../../apps/web/app/api/workspace/route.ts#L40): That null becomes 401 'Sign in first.'
  - [apps/web/lib/bff.ts:98-104](../../../../apps/web/lib/bff.ts#L98): Every forwarded request, mutations included, aborts at 30 s
  - [apps/web/lib/bff.ts:119-125](../../../../apps/web/lib/bff.ts#L119): A refused connection, a timeout and an abort all become 503 'unavailable', with no log
  - [apps/web/lib/bff.ts:168-174](../../../../apps/web/lib/bff.ts#L168): The same for streams
  - [apps/web/app/api/workspace/route.ts:8-13](../../../../apps/web/app/api/workspace/route.ts#L8): One of three local copies of the {code, message} constructor (also bff.ts:21, session/route.ts:25)
- **Evidence:** In the installed @supabase/auth-js 2.119.0, a failed fetch becomes AuthRetryableFetchError (status 0, or 5xx; lib/fetch.js) and signInWithPassword returns it as `error`. fetchSession has four callers: two pages, account-footer.tsx and the workspace route.

  ```ts
  // app/api/session/route.ts:51-55
  const { error } = await client.auth.signInWithPassword({ email, password });
  if (error !== null) {
    return NextResponse.json(REFUSED, { status: 401 }); // 'That email and password did not work.'
  }
  // lib/bff.ts:119-124: refused, timed out (30 s) and aborted alike
  } catch {
    return safeError(503, "service_unavailable", "The local API is unavailable.");
  ```

- **Why it matters:** The BFF decides every screen's failure class, because only it sees transport errors. An Auth outage tells the user their password is wrong. fetchSession's null answers 'Sign in first.' when the API is down during workspace choice. A forwarded POST that hits the 30-second abort may still be applied by the API, yet it reads as 'unavailable' rather than 'unknown, retry with the same key'. None of these leaves a server-side line.
- **Recommendation:** Classify at the BFF and keep the classes stable:
  - A refused connection stays 503 service_unavailable, which boundary.spec.ts:165-174 pins.
  - An abort after the request was sent becomes 504 upstream_timeout, retryable with the same Idempotency-Key. continue-run.tsx:48 already treats any 5xx after a write as an unknown outcome, so it keeps working.
  - An Auth fetch failure (isAuthRetryableFetchError, which supabase-js re-exports) becomes 503 auth_unavailable.
  - fetchSession returns {kind: signedOut | unavailable | ready}, so the workspace route can answer 503.

  Write one server-side line per classified failure with the route template (never the path, which can hold a run ID; logs.py:81 drops access lines for that reason), the status and the error type only. This keeps bff.ts's promise that bodies are never read or logged. Share one safeError (with no-store) from lib/bff.ts in the session and workspace routes.
- **Rule check:** nextjs rule (verify the session per BFF operation; server keys never reach responses) and DH-06 (safe typed errors). Bodies stay unread and unlogged, logged routes are templates, and the existing 503 service_unavailable for a refused connection is kept.
- **Verification:** revised. Auth behavior confirmed in the installed auth-js 2.119.0 (lib/fetch.js and GoTrueClient.signInWithPassword). Revised: the server line logs a route template rather than the path, and effort rises to M for four fetchSession callers plus boundary tests.

```text
lib/bff.ts
  export function safeError(status, code, message)       // shared, no-store
  function transportFailure(error, sent: boolean): 'api_unreachable' | 'upstream_timeout'
lib/service-status.ts
  fetchSession(): Promise<{kind:'signedOut'} | {kind:'unavailable'} | {kind:'ready', session}>
app/api/session/route.ts
  isAuthRetryableFetchError(error) ? 503 auth_unavailable : 401 sign_in_failed
```

### <a id="xerr-06"></a>XERR-06: A database outage during a request becomes a 500 internal_error, after up to 30 seconds, instead of a retryable 503

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/api/app.py:35-38](../../../../services/agent/src/autobots/api/app.py#L35): No timeout is set, so psycopg_pool's 30 s default applies
  - [services/agent/src/autobots/api/run_routes.py:66-70](../../../../services/agent/src/autobots/api/run_routes.py#L66): _pool answers 503 only when no pool was configured (13 route modules repeat this)
  - [services/agent/src/autobots/api/errors.py:38-40](../../../../services/agent/src/autobots/api/errors.py#L38): PoolTimeout and OperationalError fall to the generic 500 handler
  - [services/agent/src/autobots/operations/worker.py:141-157](../../../../services/agent/src/autobots/operations/worker.py#L141): The worker treats OperationalError as 'database lost, reconnect'
  - [apps/web/lib/bff.ts:102](../../../../apps/web/lib/bff.ts#L102): The BFF also aborts at 30 s, so the status depends on which timer fires first
  - [apps/web/tests/browser/boundary.spec.ts:165-174](../../../../apps/web/tests/browser/boundary.spec.ts#L165): The browser suite already expects 503 service_unavailable when the API is down
- **Evidence:** No handler exists for psycopg.OperationalError. In the installed psycopg_pool 3.3.3, PoolTimeout subclasses it (errors.py:16) and the pool timeout defaults to 30.0 (pool_async.py:63).

  ```python
  # api/app.py:35-38 (no timeout: psycopg_pool's default is 30 s)
      return AsyncConnectionPool(
          url, open=False, min_size=1, max_size=5, check=AsyncConnectionPool.check_connection
      )
  # api/run_routes.py:68-69: 503 only when no pool is configured
      if pool is None:
          raise ApiError(503, "service_unavailable", "The database is unavailable.")
  ```

- **Why it matters:** One condition gets three answers:
  - 503 'The database is unavailable.' when the pool was never configured;
  - 500 'Something went wrong.' when the database stops while the API runs;
  - the BFF's 503 when its own 30-second timer fires first.

  A 500 reads as a defect rather than a retryable outage, so the UI can't offer a retry. The API also disagrees with the worker about the same failure.
- **Recommendation:** Register one handler for psycopg.OperationalError in api/errors.py. It answers 503 with the code the no-pool path already uses, service_unavailable, and a fixed retryable message such as 'The database is unavailable. Try again.' The class also covers PoolTimeout and transaction conflicts such as SerializationFailure, DeadlockDetected, QueryCanceled and LockNotAvailable, all retryable, so the wording must not claim an outage for certain. The handler logs api.database_unavailable with error_fields. Give the pool an explicit timeout shorter than the BFF's abort (for example 10 s), and name both constants together. Replace the 13 copies of the no-pool check with one dependency in api/. Pin today's statuses first, then add an API test with a fake pool whose connection() raises PoolTimeout.
- **Rule check:** DH-06 Python (bound timeouts) and the python-worker rule (resources belong in lifespan). The lifespan still owns the pool; only its timeout and the error mapping change. The response envelope and the service_unavailable code are unchanged, so boundary.spec.ts:165-174 stays valid.
- **Verification:** revised. The 30 s default and the PoolTimeout hierarchy confirmed in the installed psycopg_pool. Revised: reuse service_unavailable instead of a new code, word the message for retry because OperationalError also covers transaction conflicts, and raise risk to medium since statuses change for a whole exception family.

### <a id="xerr-07"></a>XERR-07: Exception classes use four code conventions with no shared base, and 11 route modules map refusals to HTTP, partly by string suffix

- **Severity** medium · **Dimension** modules · **Effort** L · **Risk** medium · **Occurrences** 61
- **Where:**
  - [services/agent/src/autobots/application/approvals.py:36-39](../../../../services/agent/src/autobots/application/approvals.py#L36): The code is set in __init__ (18 classes)
  - [services/agent/src/autobots/application/runs.py:23-30](../../../../services/agent/src/autobots/application/runs.py#L23): The code is a class attribute (20 classes)
  - [services/agent/src/autobots/domain/runs.py:76-77](../../../../services/agent/src/autobots/domain/runs.py#L76): CommandRefused has no code; run_routes.py:86-88 invents 'transition_refused'
  - [services/agent/src/autobots/application/tool_gateway.py:24-33](../../../../services/agent/src/autobots/application/tool_gateway.py#L24): ToolFailed carries its code as the message, read back with str(error)
  - [services/agent/src/autobots/api/run_routes.py:73-90](../../../../services/agent/src/autobots/api/run_routes.py#L73): as_api_error ends in `raise error`
  - [services/agent/src/autobots/api/settings_routes.py:91-117](../../../../services/agent/src/autobots/api/settings_routes.py#L91): A HANDLED tuple must match as_api_error by hand
  - [services/agent/src/autobots/api/expert_routes.py:48-55](../../../../services/agent/src/autobots/api/expert_routes.py#L48): ExpertRefused is mapped by code sets (else 422) here, but by suffix (else 409) at run_routes.py:225-227
  - [services/agent/src/autobots/api/improvement_routes.py:42-44](../../../../services/agent/src/autobots/api/improvement_routes.py#L42): The status comes from endswith('not_found')
- **Evidence:** Count (AST over services/agent/src): 61 exception classes. 20 set the code as a class attribute, 18 in __init__, and 23 have none, including ToolFailed, whose message is its code. 11 route modules catch and map refusals; endswith('not_found') decides the status in 4 of them (routine, improvement, workflow and run routes). The idempotency message is repeated 4 times.

  ```python
  # api/improvement_routes.py:42-44
  def _error(error: ImprovementRefused) -> ApiError:
      status_code = 404 if error.code.endswith("not_found") else 409
      return ApiError(status_code, error.code, "That can't be done to this proposal.")
  # api/approval_routes.py:153-155
          except ApprovalRefused as error:
              status_code = 404 if error.code == "approval_not_found" else 409
  ```

- **Why it matters:** DH-06 asks for centralized error handling. The response envelope is central, but each router rebuilds which status and message a refusal gets. Adding a code means finding every mapper that might see it. ExpertRefused follows two different rules in two modules. The 409-versus-422 rule for ProfileNotOffered is written down only at run_routes.py:249. With no shared base, routes need multi-class except clauses, and memory_routes.py:58-59 maps every MemoryRefused to 404, which is right today only because MemoryRefused has one code (memory.py:49).
- **Recommendation:** Give the refusal classes one shape without tying the domain to HTTP. This covers the classes whose code reaches a response, not signals such as NotDelivered, ProviderFailure or UnclearReply.
  1. Add a Refusal base in domain with a code and a RefusalKind (not_found, conflict, invalid, forbidden, unavailable). Make the existing refusal classes subclass it, keeping their names and codes, and give ToolFailed and CommandRefused real codes.
  2. In api/errors.py, register one handler for Refusal that maps kind to status and code to a fixed message from one table, with a default per kind.
  3. Routes then stop catching, except where the status depends on the request (the named-profile rule), which sets kind at the raise.

  First pin today's statuses with a table-driven test over every code.
- **Rule check:** DH-06 (centralize error handling; keep domain decisions independent of HTTP). The kind enum carries no status, and the status table lives in api/. Domain, DTO and UI types stay separate, and the ErrorResponse contract is unchanged.
- **Verification:** revised. An AST scan reproduces the 61 classes and their conventions, and rg the four suffix rules. Revised: not all 61 are refusals, so the base covers only codes that reach a response, and the memory mapping is latent rather than wrong today.

```text
domain/errors.py
  class RefusalKind(StrEnum): NOT_FOUND, CONFLICT, INVALID, FORBIDDEN, UNAVAILABLE
  class Refusal(Exception): code: str; kind: RefusalKind
application/*: ApprovalRefused(Refusal), IdempotencyConflict(Refusal), ...   # names and codes unchanged
api/errors.py
  STATUS = {NOT_FOUND: 404, CONFLICT: 409, INVALID: 422, FORBIDDEN: 403, UNAVAILABLE: 503}
  MESSAGES = {'idempotency_conflict': 'This key was already used with different content.', ...}
  @app.exception_handler(Refusal) -> _response(STATUS[kind], code, MESSAGES.get(code, DEFAULT[kind]))
api/*_routes.py: drop _error, as_api_error, HANDLED and the inline mappings
```

### <a id="xerr-08"></a>XERR-08: Error and stop codes are plain strings in the contract, so client code maps drift without a type error

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/contracts/runs.py:150-154](../../../../services/agent/src/autobots/contracts/runs.py#L150): ErrorResponse.code: str, with no enumeration
  - [services/agent/src/autobots/contracts/run_workspace.py:157](../../../../services/agent/src/autobots/contracts/run_workspace.py#L157): stop_reason: str | None
  - [apps/web/components/run-list.tsx:80-83](../../../../apps/web/components/run-list.tsx#L80): STOP_TEXT keys budget_exhausted, which nothing emits
  - [services/agent/src/autobots/application/model_admission.py:21-24](../../../../services/agent/src/autobots/application/model_admission.py#L21): The service's code is budget_exceeded
  - [services/agent/src/autobots/application/goal_loop.py:92-95](../../../../services/agent/src/autobots/application/goal_loop.py#L92): budget_exceeded pauses the run rather than failing it
  - [apps/web/components/approvals-panel.tsx:24-33](../../../../apps/web/components/approvals-panel.tsx#L24): A client map keyed by codes the contract does not name
  - [apps/web/components/unknown-effects.tsx:15-20](../../../../apps/web/components/unknown-effects.tsx#L15): Another map, whose owner_required wording overrides the server's
- **Evidence:** rg finds budget_exhausted only in run-list.tsx. The fallback at run-list.tsx:151 then shows the raw code with spaces, budget exceeded.

  ```text
  # contracts/runs.py:150-154
  class ErrorResponse(BaseModel):
      code: str = Field(min_length=1, max_length=100)
  // apps/web/components/run-list.tsx:80-83
  const STOP_TEXT: Record<string, string> = {
    tool_budget_exceeded: "tool budget",
    budget_exhausted: "budget",   // the service writes budget_exceeded
  };
  ```

- **Why it matters:** Codes are the real interface between Python and the screens, which switch on them, yet the generated client types them as string. A renamed or removed code still compiles and quietly falls back to generic text. A rough cross-check of the 108 snake_case map keys and comparands in apps/web found four that the service and SQL never use; three are goal-composer.tsx's own outcome names, so budget_exhausted is the one server code nothing emits. The contracts rule asks for defined behavior for unknown enum values; with plain strings there is nothing to check.
- **Recommendation:** Publish the known codes from Pydantic as their own enum schemas (for example RefusalCode and StopReason), so the generator exports them as TypeScript unions. ErrorResponse.code and stop_reason stay open strings on the wire, so an unknown code still parses and shows the server's message. Type client maps as `Partial<Record<RefusalCode, string>>`, so removing a code fails tsc. Fix the budget_exhausted key now.
- **Rule check:** contracts rule (Pydantic/OpenAPI owns public definitions, generated TypeScript consumes them, and unknown enum values need defined behavior). Generated files are regenerated, never edited, and the wire format stays compatible.
- **Verification:** revised. The contract fields and the dead key confirmed. Revised: the reviewer's count of 88 literals could not be reproduced; a broader recount gives 108 with the same single dead server code, and the evidence now says how the fallback renders it.

### <a id="xerr-09"></a>XERR-09: Nineteen hand-cast error bodies instead of the generated parseErrorResponse, with two competing policies for error wording

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 19
- **Where:**
  - [apps/web/components/run-controls.tsx:38-43](../../../../apps/web/components/run-controls.tsx#L38): Shows the server's message
  - [apps/web/components/unknown-effects.tsx:57-60](../../../../apps/web/components/unknown-effects.tsx#L57): Ignores the server's message and maps the code to its own wording
  - [apps/web/components/approvals-panel.tsx:216-221](../../../../apps/web/components/approvals-panel.tsx#L216): Another client map
  - [apps/web/components/model-policy-panel.tsx:179](../../../../apps/web/components/model-policy-panel.tsx#L179): A cast plus a code check
  - [apps/web/components/workflow-editor.tsx:220](../../../../apps/web/components/workflow-editor.tsx#L220): One of four casts in this file
  - [apps/web/components/account-form.tsx:33-40](../../../../apps/web/components/account-form.tsx#L33): A cast plus an inline code check
  - [apps/web/components/session-panel.tsx:68](../../../../apps/web/components/session-panel.tsx#L68): The same cast
  - [packages/api-client/src/generated.ts:7698](../../../../packages/api-client/src/generated.ts#L7698): parseErrorResponse exists and is used 0 times in apps/web
- **Evidence:** Count: 20 casts in 15 files match `json().catch(() => null)) as {` (rg); 19 read error bodies, and continue-run.tsx:53 reads a success body.

  ```tsx
  // components/run-controls.tsx:38-43
  const failure = (await reply?.json().catch(() => null)) as {
    message?: string;
  } | null;
  return failure?.message ?? "That could not be done. Nothing changed.";
  // components/unknown-effects.tsx:57-60: the same cast, then
  setMessage(REFUSALS[failure?.code ?? ""] ?? "That couldn't be recorded.");
  ```

- **Why it matters:** Every mutation re-implements reading the error envelope with a type assertion, which DH-06 asks to avoid. Each picks its own wording policy: some screens show the server's fixed message, others replace it by code, and nothing says which a new screen should do. Changing the envelope or adding a code touches 15 files, and none of them validates what it read.
- **Recommendation:** Add one readRefusal(reply, wording?) to apps/web/lib. It parses with the generated parseErrorResponse; a parse failure or a null reply yields a generic refusal. Write down one policy: the server's fixed message by default, and a per-screen override by code where the screen's wording is better, such as the action-specific owner_required sentences. Replace the 19 casts as screens are touched, together with the typed codes from XERR-08.
- **Rule check:** nextjs rule (generated API types plus runtime parsing at untrusted boundaries) and DH-06 (no blanket type assertions). It uses the generated parser as it is.
- **Verification:** revised. All cited casts re-read. Revised: one of the 20 matches is a success body, so 19 error bodies; the claim that owner_required reads four ways was dropped, since those sentences name each action on purpose.

### <a id="xerr-10"></a>XERR-10: A run whose processing raises leaves no durable reason, and nothing bounds how often it is reclaimed

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** high · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/worker_leases.py:89-96](../../../../services/agent/src/autobots/application/worker_leases.py#L89): attempts goes up on every claim; nothing in src reads it
  - [services/agent/src/autobots/application/goal_loop.py:373-376](../../../../services/agent/src/autobots/application/goal_loop.py#L373): An unexpected exception re-raises out of run_goal, correctly, but no stop reason is written
  - [services/agent/src/autobots/application/goal_loop.py:343-357](../../../../services/agent/src/autobots/application/goal_loop.py#L343): The work before the first model call: building the stage and reading graph state
  - [services/agent/src/autobots/operations/worker.py:139-150](../../../../services/agent/src/autobots/operations/worker.py#L139): serve logs worker.step_failed with the class name and moves on; the job stays claimed until its lease expires
  - [services/agent/src/autobots/adapters/loop_middleware.py:393-397](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L393): The active-time limit is checked only before a model call
  - [supabase/migrations/20261105000007_run_admission.sql:14](../../../../supabase/migrations/20261105000007_run_admission.sql#L14): The attempts column
- **Evidence:** Lease.attempts (worker_leases.py:56, 104) is returned and read nowhere, and process_next and _drive (goal_loop.py:383-441) put no handler around run_goal.

  ```python
  # application/worker_leases.py:90-93, on every claim
  "update app_private.run_jobs set status = 'claimed', generation = generation + 1, "
  "attempts = attempts + 1, lease_owner = %s, "
  # rg over services/agent/src: attempts is written here and read nowhere.
  # application/goal_loop.py:373-375
      except Exception as error:
          if not is_stale_owner(error):
              raise
  ```

- **Why it matters:** As written, a run that raises before its first model call (loading the goal, building the stage, reading graph state) re-raises out of run_goal. The worker logs only worker.step_failed with a class name, and the job stays claimed until its lease expires and is claimed again. The active-time limit and the budgets are only checked at model calls, so this path never reaches them. The user sees a run that stays running with no stop reason; the operator sees one unlocalized ERROR per pass.
- **Recommendation:** Record each failed attempt durably before moving on, in private state: a forward migration adding, for example, last_failure_type and failed_attempts to app_private.run_jobs, written with the qualified exception type and never its message. A public run event, if one is added, carries only the attempt number, since public projections are sanitized. Then decide, as a durable-worker change recorded in a decision, a bound on consecutive failed attempts. Reaching it moves the run to a visible paused or failed state through the canonical transition table. Add a db check with a fake that raises before the first model call, and assert the recorded reason and the bound.
- **Rule check:** Option B contract (workers claim with attempts and fencing; canonical transitions) and the python-worker rule (canonical transitions, sanitized public projections; test restart). Migrations only move forward. No decision in docs/engineering/decisions sets a bound, so the review proposes one for a decision instead of picking a number.
- **Verification:** revised. The claim query, the unread counter, the re-raise and the missing handler in process_next confirmed; the reclaim loop is traced from the code, not reproduced. Revised: the failure type goes to private state through a forward migration, not into a public run event.

### <a id="xerr-11"></a>XERR-11: Failures the code deliberately tolerates leave no trace, and contextlib.suppress hides them from the blind-except count

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [services/agent/src/autobots/application/browsing_tool.py:99-101](../../../../services/agent/src/autobots/application/browsing_tool.py#L99): The BX-04 sweep of sessions left by crashed workers fails silently
  - [services/agent/src/autobots/api/event_routes.py:137-141](../../../../services/agent/src/autobots/api/event_routes.py#L137): Live text silently falls back to polling
  - [services/agent/src/autobots/adapters/result_stream.py:241-246](../../../../services/agent/src/autobots/adapters/result_stream.py#L241): The producer side logs result_text.unavailable for the same failure
  - [services/agent/src/autobots/application/retention.py:79-84](../../../../services/agent/src/autobots/application/retention.py#L79): Object removal failures are counted, but their cause is never recorded
  - [services/agent/src/autobots/api/operation_routes.py:106-114](../../../../services/agent/src/autobots/api/operation_routes.py#L106): An unreadable restore record is skipped with no count and no log
- **Evidence:** The live-text producer logs its side of the same failure (result_stream.py:241-246); the consumer logs nothing.

  ```python
  # application/browsing_tool.py:100-101 (comment at 99 cites BX-04)
      with contextlib.suppress(Exception):
          await runtime.executor.sweep(lease_alive(context.connection))
  # api/event_routes.py:137-141 (abridged)
      try:
          connection = await psycopg.AsyncConnection.connect(url, autocommit=True)
      except psycopg.Error:
          return None
  ```

- **Why it matters:** Each tolerance is a product choice, and the comments say why, but an operator can't see it happening:
  - browser sessions left behind by crashed workers;
  - a run page that never goes live;
  - artifact bytes that never leave Storage;
  - restore records that drop out of the history.

  ruff's BLE001 does not flag contextlib.suppress(Exception), so these escape the only metric that counts blind handlers.
- **Recommendation:** Keep each tolerance and add a trace: one WARNING log_event per degradation with error_fields, rate-limited where it can repeat (goal_loop.py:537-538 shows the pattern). For restore history, log the number of skipped records; showing that count in LocalStatus would be a separate contract change, regenerated rather than hand-edited. Replace contextlib.suppress(Exception) with an explicit except that logs, so a lint rule or a grep can see it.
- **Rule check:** DH-06 (no swallowed exceptions). BX-04 cleanup, live text and object removal stay best-effort as designed; only a trace is added, and any new response field goes through the generated contract.
- **Verification:** revised. All five sites re-read, and the excerpt trimmed to eight lines. Revised: a skipped count in the response is a public contract change, so the first step is a log line.

### <a id="xerr-12"></a>XERR-12: Log events follow no shared convention: field names, levels, rate limits and context keys differ for the same condition

- **Severity** medium · **Dimension** standards · **Effort** M · **Risk** low · **Occurrences** 25
- **Where:**
  - [services/agent/src/autobots/operations/logs.py:89-90](../../../../services/agent/src/autobots/operations/logs.py#L89): log_event accepts free-form fields and defaults to INFO
  - [services/agent/src/autobots/adapters/loop_middleware.py:319-328](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L319): error_type (qualified) and cause_type, where every other call uses error
  - [services/agent/src/autobots/operations/worker.py:89-91](../../../../services/agent/src/autobots/operations/worker.py#L89): Heartbeat connection lost: a WARNING on every failure, every 2 s
  - [services/agent/src/autobots/application/goal_loop.py:535-545](../../../../services/agent/src/autobots/application/goal_loop.py#L535): Lease keeper connection lost: INFO, on the first and every 30th failure
  - [services/agent/src/autobots/application/retention.py:171-172](../../../../services/agent/src/autobots/application/retention.py#L171): Per-item isolation without the item (no workspace)
  - [services/agent/src/autobots/application/routines.py:480-488](../../../../services/agent/src/autobots/application/routines.py#L480): The same isolation at ERROR, with the routine id
  - [services/agent/src/autobots/api/app.py:64-92](../../../../services/agent/src/autobots/api/app.py#L64): No module in api/ logs at all
- **Evidence:** Count: 25 log_event calls in 10 modules, with 24 distinct event names. 13 use error=, one helper uses error_type, and 0 modules in api/ log (api/main.py only configures logging).

  ```python
  # operations/worker.py:89-90
          except Exception as error:
              log_event(logger, "worker.heartbeat_lost", logging.WARNING, error=type(error).__name__)
  # application/goal_loop.py:537-542 (abridged), the same condition
              if failures == 1 or failures % 30 == 0:
                  log_event(logger, "worker.keeper_reconnecting", error=type(error).__name__, failures=failures)
  ```

- **Why it matters:** PRD 12.2 asks for records keyed by workspace and run, with categories such as run.*, model.* and tool.operation.*. Today:
  - the same condition, a background loop losing its connection, is a WARNING every 2 s in one module and an INFO every 30th failure in another;
  - the two per-item isolation loops differ in level and in whether they name the item;
  - a search for failures must know both error and error_type;
  - the API emits no events, so nothing ties a 4xx or 5xx to a log line;
  - no event uses the PRD's categories.
- **Recommendation:** Write the conventions beside log_event and let the helper carry them:
  - event names from a registered table, using PRD 12.2's categories;
  - standard context keys (workspace, run, operation);
  - **error_fields(error) for causes;
  - levels by audience: ERROR needs a person, WARNING is degraded and retrying, INFO is lifecycle;
  - one rate-limit helper for reconnect loops.

  Add a test that scans log_event call sites and fails on an unregistered name.
- **Rule check:** PRD-LangChain-Deep-Agents 12.2 (records keyed by workspace and run; explicit event categories) and LM-07 (local, redacted logs). No external sink is added.
- **Verification:** confirmed. rg finds 25 calls in 10 modules and 24 event names, none in a PRD 12.2 category; the heartbeat and keeper loops log as described.

### <a id="xerr-13"></a>XERR-13: One cleanup path can discard the caller's cancellation, and task cleanup idioms differ across modules

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/application/browsing_tool.py:141-143](../../../../services/agent/src/autobots/application/browsing_tool.py#L141): watcher.cancel(), then await watcher inside suppress(BaseException)
  - [services/agent/src/autobots/operations/worker.py:117-119](../../../../services/agent/src/autobots/operations/worker.py#L117): The drain cut cancels the step and waits for it, so a swallowed cancel lets the step run on
  - [services/agent/src/autobots/operations/worker.py:158-160](../../../../services/agent/src/autobots/operations/worker.py#L158): The safe idiom: cancel, then gather with return_exceptions
  - [services/agent/src/autobots/application/goal_loop.py:377-378](../../../../services/agent/src/autobots/application/goal_loop.py#L377): beating.cancel(), not awaited
  - [services/agent/src/autobots/application/goal_loop.py:454-455](../../../../services/agent/src/autobots/application/goal_loop.py#L454): The same
  - [services/agent/src/autobots/application/workflow_runner.py:318-319](../../../../services/agent/src/autobots/application/workflow_runner.py#L318): The same
  - [services/agent/src/autobots/operations/reasoning_trial.py:184-189](../../../../services/agent/src/autobots/operations/reasoning_trial.py#L184): Settles the ledger on Exception
  - [services/agent/src/autobots/operations/route_qualification.py:277-284](../../../../services/agent/src/autobots/operations/route_qualification.py#L277): Settles the same ledger on BaseException
- **Evidence:** rg: 0 `except CancelledError` in src; all 3 `except BaseException` handlers re-raise; suppress(BaseException) appears once.

  ```python
  # application/browsing_tool.py:141-143
          watcher.cancel()
          with contextlib.suppress(BaseException):
              await watcher
  # operations/worker.py:159-160
          beat.cancel()
          await asyncio.gather(beat, return_exceptions=True)
  ```

- **Why it matters:** DH-06 says to propagate cancellation after cleanup. suppress(BaseException) also discards a cancel aimed at the tool's own task if it arrives while the watcher is awaited. The window is narrow, but in it a worker's drain cut (worker.py:117-119 cancels the step and waits for it without a bound) may fail to stop a browsing step, and the gateway's own wait_for timeout can be lost too, so the tool returns after its deadline. The keeper tasks are cancelled but not awaited, so each module reasons separately about a heartbeat still in flight; fencing makes that harmless today. The trial ledger settles on BaseException in one module and on Exception in its sibling, for the same reserve-then-settle step.
- **Recommendation:** Add one stop_task(task) helper: cancel, then await asyncio.wait({task}), which neither raises the child's exception nor hides the caller's cancellation, and mark the child's exception retrieved. Use it in browsing_tool, goal_loop (two places), workflow_runner and worker. Settle the trial ledger on BaseException in reasoning_trial.py, or reuse route_qualification's _call. Add a test that cancels a browse step while its finally block runs and asserts that CancelledError propagates.
- **Rule check:** DH-06 Python and the python-worker rule (propagate cancellation after cleanup; bounded async work). Drain, lease and fencing behavior are otherwise unchanged.
- **Verification:** revised. Reasoned from asyncio's Task.cancel: a cancel that lands while the task awaits the already cancelled watcher surfaces as that watcher's CancelledError, which suppress(BaseException) absorbs; not reproduced. Revised: the title said no broad handler swallows cancellation, which this one can.

### <a id="xerr-14"></a>XERR-14: No lint gate covers blind or silent handlers, and the only BLE001 markers suppress a rule nothing runs

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 27
- **Where:**
  - [services/agent/pyproject.toml:46-47](../../../../services/agent/pyproject.toml#L46): The selection has no BLE, S110/S112 or TRY rules
  - [tests/db/restore_check.py:71](../../../../tests/db/restore_check.py#L71): One of 8 `noqa: BLE001` markers in tests/db, for a rule that is never selected
  - [services/agent/src/autobots/application/tool_gateway.py:542](../../../../services/agent/src/autobots/application/tool_gateway.py#L542): An unannotated blind handler that passes the gate
  - [services/agent/src/autobots/application/browsing_tool.py:100](../../../../services/agent/src/autobots/application/browsing_tool.py#L100): suppress(Exception), invisible even to BLE001
- **Evidence:** ruff --select BLE001 (rerun, isolated): 22 hits in services/agent/src, 3 in scripts and 2 in .claude/hooks, none with a noqa. The 8 markers in tests/db sit in 7 files. S110 and S112 report 0 everywhere.

  ```text
  # services/agent/pyproject.toml:46-47
  [tool.ruff.lint]
  select = ["E", "F", "W", "I", "B", "UP", "ASYNC", "RUF"]
  # tests/db/restore_check.py:71
              except Exception as error:  # noqa: BLE001 - only the type is reported, never a message.
  ```

- **Why it matters:** DH-06's 'no swallowed exceptions' has no enforcement. A new except Exception needs no justification: about 10 of the 27 current ones carry a reason comment, and no tool asks for one. The 8 markers in tests/db document an intent the configuration never carries out. contextlib.suppress(Exception) escapes even BLE001, which is how the silent sweep in browsing_tool.py escaped the metric.
- **Recommendation:** Ratchet:
  1. Enable BLE001, S110 and S112 in services/agent's ruff selection. S110 and S112 report 0 today.
  2. Give each of the 22 justified boundaries a noqa with its reason; about half already have a comment to reuse.
  3. Fail on new ones.
  4. Add a small check to the fast profile that flags suppress(Exception) and suppress(BaseException) in services/agent/src.

  Apply the same selection to scripts and .claude/hooks once they get a repository-level ruff configuration.
- **Rule check:** Makes DH-06's 'no swallowed exceptions' enforceable. The ratchet adds a check and weakens none, and the justified process boundaries keep working with per-line reasons.
- **Verification:** revised. Counts reproduce with ruff 0.17.3. Revised: the impact said the 22 src handlers carry no justification, but about 10 of the 27 have a reason comment; what none has is a lint annotation. S110 and S112 were checked and start at 0.

### <a id="xerr-15"></a>XERR-15: Broad catches where a precise type exists turn defects into user refusals, and one qualifier saves exception text

- **Severity** low · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/application/experts.py:69-73](../../../../services/agent/src/autobots/application/experts.py#L69): except Exception around approved_role, so any defect becomes 422 expert_role_unknown
  - [services/agent/src/autobots/domain/models.py:116-120](../../../../services/agent/src/autobots/domain/models.py#L116): approved_role raises only UnknownModelProfile
  - [services/agent/src/autobots/application/tool_uses.py:100-104](../../../../services/agent/src/autobots/application/tool_uses.py#L100): except Exception around the same validation that tool_gateway.py:338-341 catches as ValidationError
  - [scripts/qualify_github_connector.py:96-103](../../../../scripts/qualify_github_connector.py#L96): Line 100 saves str(error) in the live report; line 102 says only the type may be saved
- **Evidence:** check() stores str(observed) in the report it saves (qualify_github_connector.py:56), and _write_redacted only refuses a report that contains the token.

  ```python
  # application/experts.py:69-73
      try:
          for role in config.role_bindings:
              approved_role(role)
      except Exception:
          raise ExpertRefused("expert_role_unknown") from None
  # scripts/qualify_github_connector.py:100 passes the exception object as the observed value:
  #   check(..., error, str(error) == 'github_refused_401')
  ```

- **Why it matters:** A defect inside the guarded call is reported as the user's mistake (422 expert_role_unknown) or silently dropped (tool_uses.py records no public input). Tests that expect the refusal keep passing while the defect hides. The connector qualifier may save provider text in a live report, against the rule its own comment states two lines later.
- **Recommendation:** Catch UnknownModelProfile in experts.py, and ValidationError in tool_uses.py, as tool_gateway.py already does for the same parse. In the qualifier, record type(error).__name__ unless the error is a ToolFailed, whose message is a code.
- **Rule check:** DH-06 (no swallowed exceptions) and AGENTS.md completion evidence (no secrets or user content saved as proof).
- **Verification:** confirmed. approved_role raises only UnknownModelProfile, and check() saves str(observed), so line 100 can save exception text; all three sites re-read.

## Rejected during verification

No finding was rejected. All 15 were kept, 12 of them revised.

Verification re-opened every cited location and recounted each pattern with rg, ruff 0.17.3 (isolated, no cache), AST and tokenize scans, command-line ESLint rules and the installed library sources. It changed no file outside this folder.

## Not covered

This was a static, read-only sweep. Nothing was run beyond ruff, rg, grep, sed and AST scans.

Coverage of the 545 in-scope files:
- 34 were read in full.
- About 60 more were read around every broad handler, error mapper, log call, and web load or failure path.
- The rest were covered only by the scans named in each finding.

Not reviewed:
- error handling inside SQL functions (plpgsql raise and exception blocks in supabase/migrations);
- Makefile and shell error handling;
- each tests/db script's exit-code semantics beyond its broad handlers;
- runtime behavior of Server Components when they throw (no error.tsx or loading.tsx exists, so Next.js defaults apply; not exercised).

The run-reclaim finding and the cancellation window in browsing_tool.py come from reading the code, not from a reproduction.

No command was refused. Two commands failed on zsh's `===` expansion and on a bracketed glob, and were rerun with quoting. Nothing was written under .checks/reviews/review-2026-11-12-09-52-30/sweep-errors/ beyond creating the directory.

Overlaps with other lenses: the loader, hand-cast-body and lint-gate findings touch the web-architecture, types, duplication and tooling lenses. They are framed here by their error consequences.
