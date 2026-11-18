# Autobots runtime: developer questions and answers

**The model proposes the next action; application code controls execution, permissions, budgets and completion.** A run can repeat the model → tool → result cycle many times. Delegation depth counts nested specialist runs, not those cycles.

This guide describes the working-tree implementation inspected on **2026-11-05**, based on revision `ecb34900e46c` plus existing local changes. It is an explanation of code, not a new product specification or a claim of live qualification. Requirements remain in [SPECS.md](SPECS.md) and the [preserved Option B contract](docs/engineering/option-b-contract.md). Related stories: **US-4.2–US-4.7, US-5.1–US-5.4, US-6.2 and US-8.1**. [CODEBASE.md](CODEBASE.md) is an implementation inventory.

## Start here

| Question | Read |
|---|---|
| Does the loop repeat? What stops it? | [Cycles](#1-does-the-loop-repeat-in-cycles), [stopping conditions](#3-what-can-stop-a-loop) |
| What does depth mean? | [Depth](#5-how-does-depth-work), [shared limits](#4-what-are-the-default-limits) |
| Who chooses tools, and when? | [Selection](#7-who-decides-which-tool-to-use), [execution](#9-what-happens-between-a-tool-request-and-its-result) |
| Which tools exist? | [Tool inventory](#8-which-tools-does-an-autobot-actually-have) |
| Why did a run stop or produce no artifact? | [Verification](#12-what-makes-a-run-successful), [debugging](#18-where-should-i-look-when-a-run-stops) |
| How do I extend this safely? | [Adding a tool](#19-how-should-a-developer-add-a-tool) |

## 1. Does the loop repeat in cycles?

Yes. In a goal run, a model response can request tools. The runtime executes permitted requests, adds their results to the conversation, and asks the model what to do next. Those observations make the next cycle different from the previous one.

![A goal run repeats model requests and tool observations; a no-tool reply goes through plan checks and verification.](docs/diagrams/runtime-qa/loop.svg)

[Open the standalone loop diagram](docs/diagrams/runtime-qa/loop.html).

A typical pass is:

1. Claim the admitted run with a worker lease and load its saved goal, scope, model policy and checkpoint.
2. Check that the worker still owns the run and has time, calls and spending allowance available.
3. Send the goal, instructions, relevant history and granted tool schemas to the admitted model.
4. Receive a complete response. Tool calls go through validation and the central gateway; a final reply without tools ends the inner stage.
5. Feed tool results back as `ToolMessage` observations and repeat, or evaluate the candidate result.

One response may request several tools, so **one cycle is not necessarily one tool call**. The current middleware serializes those tool calls because they share a database connection. A tool error can itself become an observation that helps the model choose a permitted alternative.

The system prompt asks the model to call `propose_plan` first, use `complete_task` with real evidence, then finish without a tool call. Those instructions guide the model; persisted checks determine whether it complied.

Code: [`run_goal()` and `build_stage()`](services/agent/src/autobots/application/goal_loop.py), [`LoopMiddleware`](services/agent/src/autobots/adapters/loop_middleware.py), [`GatewayMiddleware`](services/agent/src/autobots/adapters/tool_middleware.py). Sources: **SP-008, SP-011, US-4.3**.

## 2. Is there only one kind of loop?

No. Keep these mechanisms separate when reading logs or changing limits:

| Mechanism | What repeats | What ends this repetition |
|---|---|---|
| Worker polling | Look for an eligible durable job | Shutdown/drain; no job means wait, not run failure |
| Goal model/tool loop | Model response → permitted tools → observations | Final reply, stop condition, wait, pause or lost ownership |
| Provider retry | Attempt one model request again after a classified retryable failure | Success, retry cap, deadline or nonretryable/uncertain failure |
| Argument/output repair | Ask for a usable correction after an eligible invalid response | A valid correction or exhausted shared repair allowance |
| Specialist assignment | Parent waits while a child runs its own bounded loop | Child result, pause, loss or cancellation |
| Workflow readiness loop | Execute ready node instances and persist emissions | Settled instances, failed node, pause or stalled graph |
| Routine scheduling | Admit explicitly scheduled occurrences | Routine policy and occurrence history; each occurrence has its own run |

An idle worker continuing to poll does not mean a completed goal is still reasoning. See [`worker.py`](services/agent/src/autobots/operations/worker.py), [`workflow_runner.py`](services/agent/src/autobots/application/workflow_runner.py) and [`routines.py`](services/agent/src/autobots/application/routines.py).

## 3. What can stop a loop?

**Stopping the current execution pass and finishing the run are different events.** A stopped pass can leave the run paused, waiting, terminal, or owned by another worker.

| Trigger | Current behavior |
|---|---|
| Model returns without tool calls | Check the stored plan. Missing/incomplete plan fails with `plan_missing` / `plan_incomplete`; a complete plan proceeds to `verifying`. |
| Verification passes or fails | Commit `succeeded`, or `failed` with `criteria_unmet`. |
| Model/tool/repair/plan-revision/active-time/graph-step cap | Stop new work. These limit codes ordinarily make the run `failed`; they do not manufacture success. |
| Spend limit, missing credential, unavailable model/pricing, or inference slots unavailable beyond the wait | Usually `paused` with a reason that can be addressed. See the exact `PAUSE_FOR` set. |
| Approval is needed | Enter `waiting_approval`; the effect is not executed while approval is pending. |
| Required input is outstanding | The state machine supports `waiting_input`; a saved obligation is restored on continuation. The default goal registry has no generic `ask_user` tool. |
| User pauses | Stop new dispatch at a safe boundary; retain saved state. Pause does not promise to abort an already accepted model request. |
| User cancels | Fence new work. Settle/classify active work and descendants through `cancelling` when needed, then `cancelled`. |
| Worker loses its lease | That worker loses authority to dispatch or advance execution/checkpoint state. Late receipt reconciliation can still record known outcomes; losing ownership is not authority to mark the run failed or successful. |
| Model/effect outcome is uncertain | Preserve uncertainty and pause for reconciliation; do not blindly resend. |
| Provider or tool failure | Use only the classified retry/repair path. Some refusals return to the model; designated stop codes end the pass. |
| Unexpected unhandled exception | May escape to the worker logger and recovery path; not every Python exception produces an immediate terminal run. |

Canonical terminal states are **`succeeded`, `failed`, `cancelled`**. Terminal runs cannot resume. A continuation of finished work requires a new run. Only `paused` uses the generic `resume` command; waiting states use validated input/approval decisions.

Code: [`DISPOSITION`, `PAUSE_FOR` and `NOT_OURS`](services/agent/src/autobots/domain/stops.py), [`finish()`](services/agent/src/autobots/application/run_lifecycle.py), [`STOPPING` and `REPAIRABLE`](services/agent/src/autobots/adapters/loop_middleware.py), [canonical transitions](services/agent/src/autobots/domain/runs.py). Sources: **SP-010, SP-012, US-4.7**.

## 4. What are the default limits?

These are application defaults, not model capacities or a guarantee that every task fits.

| Limit | Default | What it means |
|---|---:|---|
| Model calls | 24 | Shared across the tree; dispatched retries and admitted summary calls count too |
| Tool dispatches | 40 | Shared; an attempted call consumes a dispatch before the gateway may refuse it |
| Repairs | 1 | Shared allowance for eligible argument/plan errors and length-truncated replies; not one per tool |
| Plan revisions | 2 | Shared across the tree after initial plans; each run's initial plan is free of this counter |
| Child levels | 2 | Root → child → grandchild |
| Total child runs | 4 | All descendants combined, excluding the root |
| Outstanding assignments | 2 | Open assignments across the tree, not a guarantee of parallel execution |
| Active execution | 900 seconds | Checked before dispatch; approval waiting has a separate expiry |
| LangGraph step limit | 202 with these defaults | `3 × (model_calls + tool_dispatches) + 10`; graph steps are not model calls or child depth |
| In-flight model timeout | 120 seconds | Separate timeout for a model attempt |
| Inference slot wait | 30 seconds | Bounded wait when shared model slots are busy |

The source spending defaults are **US$1 per root run**, **US$5 per workspace UTC day**, and **two shared OpenRouter slots per workspace**. Admission reserves cost before dispatch. Cost limits are separate from call counts. Missing price information is not treated as free inference.

The 900-second allowance is **not an exact wall-clock kill switch**: guards run at dispatch boundaries and individual operations have their own timeouts. Crash-left-open execution segments also limit the precision of elapsed-time accounting. The defaults live in [`RootLimits`](services/agent/src/autobots/application/run_usage.py) and [`LoopConfig`](services/agent/src/autobots/application/goal_loop.py); spending is handled by [`model_admission.py`](services/agent/src/autobots/application/model_admission.py). Source: **SP-008**.

## 5. How does depth work?

Depth counts edges in the **delegation tree**. The root is depth 0. A specialist it creates is depth 1. That specialist's child is depth 2. Creating depth 3 is refused.

![Delegation depth counts root-to-child edges; the tree shares budgets and stops delegation at depth two.](docs/diagrams/runtime-qa/depth.svg)

[Open the standalone depth diagram](docs/diagrams/runtime-qa/depth.html).

Depth is independent of cycle count: a depth-0 run could make many model/tool turns without creating any children. It is also unrelated to reasoning-token use, plan length, Python stack depth or LangGraph's `recursion_limit`.

In a coordinator session, the depth-1 child inherits the coordinator session's pinned Expert choices. `narrowed_tools()` re-adds `assign_specialist` only while the parent has it and the child remains below the depth cap. At depth 2, that tool disappears from the offered set; the server also checks the depth when creating a child. A direct Expert session does not gain delegation merely by asking for it in a prompt.

Code: [`narrowed_tools()` and `_create()`](services/agent/src/autobots/application/assignments.py), [`resolve_binding()`](services/agent/src/autobots/application/experts.py). Sources: **US-5.1, US-5.2**.

## 6. Does each specialist get fresh permissions and budgets?

No. A child's configurable tools are the intersection of the parent's grants and the selected Expert's tools, optionally narrowed further by the assignment. Plan tools remain available; delegation has the separate depth rule above. The child gets the allowed input prefix and a dedicated `outputs/child-N` namespace. Virtual file reads remain scoped to that run; sharing a prefix does not expose every parent file.

Model/tool calls, repairs, revisions and total children use atomic counters on the **root** usage row. Creating four children does not multiply the 24-call allowance into 120 calls. A parent releases its inference slot before waiting for the child. Assignment execution is synchronous from the parent's perspective, and replay reattaches to the existing child or reuses its finished result.

Current child summary counters do not provide complete per-child usage attribution: `LoopResult.usage` and the run projection read the selected run's row, while shared counters are charged to the root. Inspect root usage for tree totals and invocation records for call attribution.

Code: [`assignments.py`](services/agent/src/autobots/application/assignments.py), [`ToolScope.budget_run_id`](services/agent/src/autobots/application/tool_gateway.py), [`usage_view()`](services/agent/src/autobots/application/run_usage.py), [`run_projection.py`](services/agent/src/autobots/application/run_projection.py).

## 7. Who decides which tool to use?

There are three decisions:

1. **The application determines availability.** A tool must be registered at the granted version and included in the run's saved scope. Expert configuration, session type and infrastructure availability affect this set.
2. **The model proposes a call.** It sees tool names, descriptions and input schemas alongside the goal, instructions and previous results. It chooses a name and structured arguments. There is no general keyword rule that automatically invokes `calculate` whenever the goal mentions numbers.
3. **The application authorizes execution.** The gateway validates the proposed call against schema, permissions, paths, ownership and approval policy. A model request does not grant permission.

For example, a goal to total provided numbers and deliver a report could lead to `propose_plan` → `calculate` → `save_artifact` → `publish_artifact` → `complete_task` → final reply. This is an illustrative sequence, not a guaranteed model response or an executed example. Multiple calls may share one model response.

An instruction such as “you may use a shell” cannot create a shell tool. The schemas exposed to the model are constructed by [`visible_tools()`](services/agent/src/autobots/adapters/tool_middleware.py); the registry is assembled by [`tool_definitions()`](services/agent/src/autobots/adapters/tool_registry.py).

## 8. Which tools does an autobot actually have?

The current goal-loop inventory is below; all listed versions are **v1**. Registration and permission are separate: a registered tool can still be invisible to a particular run.

| Tool | When it is useful | Availability |
|---|---|---|
| `propose_plan` | Create or revise tasks covering the goal's criteria | Base goal-loop tool |
| `complete_task` | Mark a task complete using validated evidence and completed prerequisites | Base goal-loop tool |
| `read_offload` | Read pages of a long tool result removed from the prompt view | Base goal-loop tool |
| `calculate` | Sum, mean, minimum or maximum of 1–1000 finite numbers | Default goal grant; explicit Expert selection |
| `read_run_file` | Read the latest version of a virtual file belonging to this run | Default goal grant; explicit Expert selection |
| `save_artifact` | Save a versioned internal file with a content hash | Default goal grant; explicit Expert selection |
| `publish_artifact` | Publish an exact saved path/version into private artifact Storage | Grant plus configured object-store adapter required |
| `search_memory` | Keyword search of scoped memory and current run evidence | Default goal grant; explicit Expert selection |
| `propose_improvement` | Propose a memory/skill change for review | Explicit Expert opt-in; absent from ordinary default goals |
| `assign_specialist` | Delegate a bounded task to a pinned Expert and await its result | Coordinator-session family, delegation driver and depth allowance required |

Expert revisions default to an empty configurable tool list; they do not automatically receive every general tool. Their base plan/read-offload tools are supplied by the application. `workflow_approval` is a separate workflow-runner gate, not a general tool offered to the goal model.

The registry now holds web search and extraction (Tavily and Jina, Decision 0017), GitHub issue and pull-request connectors, the `cronjob` tool (Decision 0026) and an isolated browser behind `browse_goal` (Decision 0020), each through the gateway's policy, approvals and receipts; `adapters/tool_registry.tool_definitions` lists them. It has **no shell, unrestricted Python execution, host-file access, dynamic MCP discovery, email send or external publishing connector**. The consequential-effect fixtures use mock destinations. The required gateway policy for future MCP tools does not mean MCP integration is already implemented.

Code: [grant vocabulary](services/agent/src/autobots/domain/tools.py), [runtime registry](services/agent/src/autobots/adapters/tool_registry.py), [version inventory](services/agent/src/autobots/domain/execution.py), [Expert contract](services/agent/src/autobots/contracts/experts.py), [mock effect tools](tests/db/fixtures/effect_tools.py).

## 9. What happens between a tool request and its result?

![The model proposes a call, middleware and the gateway enforce policy, and only then does the handler run and return a validated result.](docs/diagrams/runtime-qa/tool-call.svg)

[Open the standalone tool-call diagram](docs/diagrams/runtime-qa/tool-call.html).

The loop checks ownership/time and consumes a root tool-dispatch allowance. The gateway then checks the grant/version, registered definition, complete Pydantic arguments, resource scope and current run ownership. If approval applies, it resolves that before invoking the handler. Effects receive operation identities and receipts. The handler's output is validated, size-bounded and redacted before the model receives it.

The resulting `ToolMessage` matches the model's tool-call ID and carries structured `outcome`, safe `code`, `output`, and an `operation_id` for effectful calls. That observation becomes input to the next model turn. Tool text is data: it cannot enlarge the saved grants.

Deep Agents may attach built-in file, shell or subagent tools. This application filters model-visible tools and routes every tool request through `GatewayMiddleware`; it does not call the SDK's original tool handler. Synchronous tool execution is refused. Thus hiding a name is not the only control.

Code: [`ToolGateway.execute()`](services/agent/src/autobots/application/tool_gateway.py), [`GatewayMiddleware`](services/agent/src/autobots/adapters/tool_middleware.py), [`LoopMiddleware.awrap_tool_call()`](services/agent/src/autobots/adapters/loop_middleware.py). Sources: **SP-013, US-4.4**.

## 10. What is the difference between retry and repair?

**Retry repeats a classified-safe provider attempt; repair asks the model to correct its output.** Both remain inside the root envelope.

The provider policy permits at most two retries after the first attempt for eligible rate limits, selected provider errors and connection failures before acceptance. Normal backoff is 1 then 2 seconds; `Retry-After` can increase it, but waits over 60 seconds or beyond the remaining deadline are refused. Every dispatched attempt counts. Partial streams or uncertain acceptance keep an uncertainty record and are not blindly retried.

The single shared repair allowance covers eligible plan/argument failures and a reply truncated for length. Incomplete responses are not executable tool requests. A second repair need stops the loop. Other tool denials may return an error observation without consuming this repair counter, but still consume the outer call/dispatch budgets.

Read/pure tools have their own bounded handler retry policy: `calculate` and `read_run_file` each permit one retry. Those internal attempts are not new model requests. Write tools cannot register blind retries; they need replay/reconciliation semantics.

Code: [`model_attempts.py`](services/agent/src/autobots/application/model_attempts.py), [`loop_middleware.py`](services/agent/src/autobots/adapters/loop_middleware.py), [`ToolDefinition` and registry checks](services/agent/src/autobots/application/tool_gateway.py).

## 11. What are receipts, and why do repeated writes not simply run again?

A write operation's identity is derived from **run ID + optional workflow instance + tool ID/version + normalized argument hash**. The runtime records the operation before performing its effect. Replaying the same known-success operation returns its stored result. Different workflow item instances remain distinct even when their arguments are equal.

If a worker crashes after dispatch, the runtime cannot assume the write failed. It uses destination readback/reconciliation or explicitly declared deduplication safety. An unresolved result stays `unknown`. This is recovery from uncertain outcomes, not a universal exactly-once guarantee.

Pure calculations and reads have no effect receipt; repeating a read can observe newer data. Failed effect receipts retain safe diagnostic codes/categories, rather than raw model arguments. An invalid call rejected before effect admission need not have a receipt at all.

Code: [`_operation_id()` and `ToolGateway`](services/agent/src/autobots/application/tool_gateway.py), [`recovery.py`](services/agent/src/autobots/application/recovery.py), [`reconciliation.py`](services/agent/src/autobots/application/reconciliation.py). Sources: **SP-012, SP-013, US-5.4**.

## 12. What makes a run successful?

For goal runs, **the model saying “done” is insufficient**. The stored plan must be complete. Deterministic verification then checks unsettled model calls/effects, reconciles publication, reads required artifacts back and checks the configured `must_contain` strings. Without explicit artifact requirements, at least one published artifact is still required. An object store must be available.

`save_artifact` writes a versioned virtual run file. `publish_artifact` makes the selected version a private downloadable artifact. “Publish” here does not mean post publicly or send to an external service.

These checks have a bounded meaning: evidence exists, publication is consistent, and declared content assertions pass. They do not prove the general semantic correctness of every report. `complete_task` validates task evidence, but cannot replace final artifact verification.

The canonical state machine permits `verifying → running` for bounded repair. **The current goal-run candidate handler directly succeeds or fails after verification; it does not automatically start that repair loop.** Workflow runs have a separate completion path based on settled node instances.

Code: [`verify_candidate()`](services/agent/src/autobots/application/verification.py), [`settle_candidate()`](services/agent/src/autobots/application/settlement.py), [`plan_view()` and evidence checks](services/agent/src/autobots/application/plans.py), [`artifacts.py`](services/agent/src/autobots/application/artifacts.py).

## 13. What happens on pause, cancellation, browser closure or worker restart?

| Event | Meaning |
|---|---|
| Close or refresh the browser | The durable worker job continues; reconnect retrieves the authoritative run state and events |
| Pause | Prevent new work at a safe boundary and preserve state; resume rechecks readiness and saved obligations |
| Cancel | Prevent new dispatch and settle/classify active work; late responses may add reconciliation evidence but cannot turn the cancelled run into success |
| Worker crash or expired lease | Another eligible owner may recover from the checkpoint and receipts; the old generation is fenced from execution/checkpoint writes |
| Saved graph/tool semantics no longer compatible | Pause with `incompatible_version` before using that checkpoint/model path |
| Change the workspace default model | Existing runs retain their frozen policy; switching unfinished work to another model requires a linked new run |

Keys and runtime clients stay outside durable graph state. Credential resolution is late-bound per attempt; rotating a key is different from changing the saved model policy. The product uses the two approved OpenRouter profiles through its shared gateway, without silent provider/model fallback.

Code: [`checkpoints.py`](services/agent/src/autobots/adapters/checkpoints.py), [`worker_leases.py`](services/agent/src/autobots/application/worker_leases.py), [`execution.py`](services/agent/src/autobots/domain/execution.py), [`worker_inference.py`](services/agent/src/autobots/application/worker_inference.py). Sources: **SP-006, SP-010, SP-012**.

## 14. Does approval give a tool permanent permission?

No. Approval is bound to the actor/workspace, operation, tool/version, normalized arguments, scope and expiry. A modified action needs its own valid decision. Pending or expired approval is not consent. A rejected action cannot execute just because the run is re-enqueued.

Consequential external writes, and tools explicitly marked approval-required, pass through the approval gate. The current infrastructure is exercised with controlled effect fixtures; it does not establish a production email or publishing connector. The workflow approval tool releases a value through a gate and performs no remote write.

Code: [`approval_gate()`](services/agent/src/autobots/application/approvals.py), [`workflow_approval`](services/agent/src/autobots/application/workflow_runner.py). Sources: **US-5.3, US-5.4, US-7.2**.

## 15. Are workflow cycles the same as agent cycles?

No. A workflow is an immutable typed definition. Application code selects nodes when their dependencies and inputs are ready; the model does not choose each workflow block.

The current subset rejects arbitrary graph cycles and nested `foreach`. A bounded `foreach` declares `max_items` (at most 100), creates separate instance/emission identities and converges through a join. An `agent` block delegates model work to a specialist. Read, artifact and approval nodes use the gateway directly.

If unfinished workflow instances cannot make progress, the runner reports `workflow_stalled`; a failed node produces `workflow_node_failed`. This deterministic readiness check is different from detecting repetitive or unhelpful model reasoning.

Code: [`validate_graph()`](services/agent/src/autobots/domain/workflows.py), [`workflow_execution.py`](services/agent/src/autobots/domain/workflow_execution.py), [`run_workflow()`](services/agent/src/autobots/application/workflow_runner.py). Sources: **US-6.1, US-6.2**.

## 16. What happens when the conversation gets too long?

The application offloads large tool results and leaves a reference/preview. `read_offload` retrieves pages when needed. Older conversation may be summarized through an admitted summarizer call, consuming the shared model budget. The saved conversation retains the messages; compaction changes the view sent to the model.

The goal, permissions, criteria and open waits are reconstructed from durable records, not entrusted to a lossy summary. Current defaults use a **24,000-character prompt-view threshold**, a **4,000-character large-result threshold** and six recent messages as the retention target. This is a rough character policy, not an exact tokenizer-enforced 8K context guarantee. `read_offload` pages have separate handling to avoid repeatedly offloading the offload reader.

Code: [`CompactionPolicy` and `safe_split()`](services/agent/src/autobots/application/compaction.py), [`LoopMiddleware._compacted()`](services/agent/src/autobots/adapters/loop_middleware.py). Source: **US-8.1**.

## 17. Are these the same tools and agents used by Codex or Claude to develop Autobots?

No. The development assistant's shell, browser, repository skills and collaboration tools belong to the development environment. They are separate from product tools exposed by `tool_definitions()`.

Likewise, [`.claude/agents/`](.claude/agents/) contains development roles. Product Experts are versioned database-backed configurations resolved by [`experts.py`](services/agent/src/autobots/application/experts.py). Product skills contribute reviewed instructions/reference material; they do not grant executable tools or silently expand permissions. A promoted skill does not become an unrestricted Python function.

## 18. Where should I look when a run stops?

Start with the run's **status and reason**, then the records that explain the last attempted action. Avoid inferring success from a final chat message or a spinner disappearing.

| Symptom | Inspect |
|---|---|
| Nothing is being claimed | Worker inference activation, installation hold, qualified checkpoint adapter, job eligibility and current lease |
| Tool missing from model choices | Saved `GoalSpec.allowed_tools`, Expert version/session binding, registry version and required object-store/delegation adapter |
| `invalid_arguments` or `repair_limit:*` | Tool's Pydantic schema, complete response metadata, prior repair usage and safe failure categories |
| `plan_missing` / `plan_incomplete` | Plan version, criterion coverage, task dependencies and recorded evidence |
| `criteria_unmet` | `app_private.run_verifications.unmet`; check saved versus published artifact and required content |
| `*_limit` / `step_limit` | Root `app_private.run_usage`, `RootLimits`, graph-step formula and invocation history |
| `outcome_unknown` / uncertain model call | Tool receipts, invocation reservations and reconciliation records before considering replay |
| `waiting_approval` / repeated wait after resume | Exact pending approval/input obligation, expiry and decision binding |
| Child counters appear empty | Root usage totals and invocation `run_id`; child summaries are not complete attribution |
| Two workers appear involved | Job lease generation, expiry and fenced checkpoint ownership |

The default worker process performs maintenance without claiming inference jobs unless explicitly enabled. See [`operations/worker.py`](services/agent/src/autobots/operations/worker.py) and the [operations runbook](docs/engineering/runbooks/operations.md) for the deliberate activation procedure. Do not start services or use paid inference merely to read this guide.

Useful starting points: [run projection](services/agent/src/autobots/application/run_projection.py), [public event routes](services/agent/src/autobots/api/event_routes.py), [sanitized logs](services/agent/src/autobots/logs.py), [existing loop fixtures](tests/db/checks/goal_loop_check.py), [tool unit tests](services/agent/tests/test_tools.py).

## 19. How should a developer add a tool?

Treat this as a bounded implementation story under the repository contract. The implementation needs more than a Python function:

1. Define versioned Pydantic input/output contracts, a description, effect class, timeout, output limits and resource extraction.
2. Implement the handler using the supplied run scope. Validate permissions in code; prompt instructions are not access control.
3. For writes, define operation/reconciliation and deduplication behavior. Consequential effects require the argument-bound approval path. Registration refuses arbitrary execution until its executor is qualified (`ToolRegistry.register`).
4. Register the definition in the relevant registry and deliberately expose it through eligible grants. Adding a name only to an Expert configuration is rejected.
5. Update the execution-version contract. A semantic change must not silently reinterpret an existing checkpoint.
6. Verify successful use plus denied scope, invalid arguments/output, timeout, replay, cancellation and uncertain-effect recovery as applicable. Keep mocked, disposable and live evidence separate.

Public API changes also require regenerating the TypeScript client from Pydantic/OpenAPI; persistence changes belong in SQL migrations. Follow the [development harness](PRD-Development-Harness.md) and [contract generation procedure](docs/engineering/runbooks/development-harness.md#generate-and-check-contracts).

## 20. Which assumptions should developers avoid?

- **“The model always follows the plan.”** Plans are proposals; the application checks coverage, dependencies and evidence.
- **“No tool call means success.”** It only ends the inner model/tool stage; the plan and artifact checks remain.
- **“Depth 2 means two cycles.”** Depth counts child generations. Cycle counts are bounded separately.
- **“The loop detects every kind of stagnation.”** No dedicated semantic no-progress detector was found in the goal loop. Finite budgets and graph limits bound it; workflows have a distinct readiness-stall check.
- **“A restart creates fresh budgets or repeats every action.”** Durable counters, checkpoint ownership and receipts constrain recovery.
- **“Every denied call kills the run immediately.”** Some errors return as observations; designated stop codes and exhausted limits end the pass.
- **“Published means public.”** Current artifact publication is private local Storage delivery.
- **“A successful test proves production capability.”** Fixture results establish only the behavior exercised. This documentation task does not qualify live model behavior, connectors, H1 or the complete product.

## Diagram design and maintenance

The three diagrams adapt [Cathryn Lavery's Diagram Design](https://github.com/cathrynlavery/diagram-design/tree/f24d98b05e2d7a5e68c2dedfe46e5b7173f50118): small focused figures, sparse accents, orthogonal connectors and accessible SVG descriptions. They use Autobots' [Luma tokens](docs/design/luma.css), following the requested style choice. The HTML sources and SVG exports live in [`docs/diagrams/runtime-qa/`](docs/diagrams/runtime-qa/); see their provenance notes for the font adaptation and license.

When the runtime changes, update the affected answer and figure from the source code and preserved requirements. Keep the distinctions between **specified**, **implemented**, and **verified** visible. Documentation verification and independent review for this change are recorded under [DOC-QA-001](docs/engineering/work-items/DOC-QA-001.md).
