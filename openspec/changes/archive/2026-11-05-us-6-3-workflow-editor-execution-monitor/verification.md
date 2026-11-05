# Verification — us-6-3-workflow-editor-execution-monitor

Change: us-6-3-workflow-editor-execution-monitor
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `902d1cd`, working tree with this change. The real API and web app in Chromium on a disposable stack, with the fixture worker running executions. `scripts/qualify_identity.py` exit 0, 239 cases, including 3 new browser tests. `--profile full` passed.

## Scenarios

**Inspect a validated graph run: observed in a browser.**
- A broken graph shows `foreach bound required at each`, and publishing it is refused with that code, so no version appears.
- A valid graph shows its hash and publishes as version 1, and the block table shows typed ports. Choosing that version with inputs opens the monitor, which shows the binding.
- The worker ran it up to an approval step: `up#0` and `up#1` show their own emissions, `all` shows `["A", "B"]`, and `out` shows `waiting`.
- Approving through the inbox continued it to `succeeded`, with the final emission shown.
- A failure shows `failed` with its reason, `blocked` after it, and a failed run.
- axe reports no WCAG A or AA violation on the editor or monitor. Another workspace gets a clear refusal on both screens.

**Keep UI state a projection: observed.**
- With requests blocked, the monitor shows `reconnecting` and its last known state. Unblocked, it shows `live`. After a reload, the emissions and instances are identical to before, compared through the API.
- The monitor only issues GET requests, from its code, so it can't start or repeat work. The worker's job and lease are unchanged by it.

## Findings

- **Fixed during this story:** the Playwright filter `workflows` also matched `slice-workflows.spec.ts`, which ran it twice, the first time with no worker. The filter is now the full path.
- **The graph is edited as JSON,** with a table of blocks and typed ports. There's no visual canvas. PRD 12.1 lists "typed ports, validation, run bindings, node-instance status, output emissions", and a canvas appears only among surfaces to theme, so I read JSON as meeting this story. You may want a canvas later.
- **The monitor polls once a second,** rather than using the event stream, since instance changes aren't public events yet. Polling stops at a terminal status.
- **Not checked:** a member's view of these screens, the run page's link back to its workflow, and the model-key check for agent steps through the route.
- **No independent review.**
