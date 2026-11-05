# Verification — us-4-4-versioned-tool-registry-operation

Change: us-4-4-versioned-tool-registry-operation
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `b52a848`, working tree with this change. Real Postgres through the runtime role on a disposable target, the pinned `deepagents` 0.7.32 with a fake model, and no paid call. `scripts/app_db.py types`: 217 cases passed. `--profile full` passed. `qualify_identity` was not rerun, since this story adds no route or web change and doesn't edit what those tests call.

## Scenarios

**Validate before execution: observed.**
- Refused with `invalid_arguments` and no effect: an unknown operation, an extra field, a missing field, a required field left out, and a truncated JSON prefix passed as arguments. `executable_tool_calls` from US-3.3 already drops every call from an incomplete response.
- Refused before the handler: a run not owned, a run outside `running`, a stale generation and another workspace's scope.
- A slow pure tool fails with `tool_timeout` after its one bounded retry, and a timed out effect is `unknown`.
- A consequential write is refused with `approval_required`, and its handler is never called.

**Reject inherited capabilities: observed, including a real SDK loop.**
- `execute`, `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `task`, `delete`, `write_todos`, an MCP-style name and `shell` are all `tool_not_granted`.
- Arbitrary execution can't be registered. An unregistered version is refused.
- Eight paths outside the grant are refused, including `..`, absolute, `outputsx/` and `.env`. Another run's file isn't readable.
- A real `create_deep_agent` graph keeps `execute`, `write_file`, `task` and others in its tool node. With the middleware, the model was offered only the 3 granted tools. A fake model then called six forbidden tools, and every reply was `tool_not_granted`. The file the `execute` and `write_file` calls would have made doesn't exist. `calculate` and `save_artifact` worked through the same loop.

**Keep effect identity durable: observed.**
- A repeated save returns the same operation ID and output, with 1 row. Different content is a different operation and version 2. A read isn't receipted, so it sees the current version.
- A replacement generation with a new gateway instance reuses the receipt.
- A lost response, arranged by resetting the receipt to `started`, is reconciled by reading back the row: `succeeded`, still 1 row.
- An effect that raises is `unknown`, and repeating it doesn't call it again. A confirmed failure may be tried again.
- A result arriving after the lease is lost is recorded as `succeeded`, and refused with `lease_lost`, so a replacement won't repeat it.
- A tool's exception text, arranged to hold a key-like string, doesn't reach what the model sees.

## Findings

- **The middleware is required, not optional.** Deep Agents attaches shell, file and subagent tools even when given none. US-4.3 must use `GatewayMiddleware`, and its tests must keep the check on the tool node.
- **Operation identity is run, tool, version and arguments.** Saving identical content twice in a run is one operation by design, so it stays stable when a replayed model call gets a new tool-call ID. Whether a tool needs a stronger key is for that tool's story.
- **A small crash window remains.** `save_artifact` can commit with its receipt still `started`, which reconciliation handles. A consequential tool with no readback stays `unknown` until an operator decides, and there is no operator path yet.
- **Limits:** MCP has no adapter, so here it's only denied by name. URL validation has no tool yet. `run_files` are database rows, and private storage is US-4.5. The cap values, 256,000 characters and 300,000 bytes, are my choice, since the sources set none. Middleware order is covered by this one configuration.
