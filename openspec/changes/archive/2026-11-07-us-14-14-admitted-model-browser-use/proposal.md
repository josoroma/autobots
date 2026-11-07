## Why

US-14.14 and [Decision 0020](../../../docs/engineering/decisions/0020-own-browsing-loop.md): browser-use can't be installed beside the qualified OpenRouter SDK, so the owner chose Autobots' own read-only browsing loop. Every step it takes must be an admitted call of its run on the frozen `researcher` route, with no model client of its own and no new package.

## What Changes

- A browsing loop in the worker (`application/browsing_loop.py`). Each step shows the model the current page as text: its URL, title, a cut of its readable text and its numbered links. The model must answer with exactly one of four typed tool calls, required on every step: `open_link`, `go_to`, `scroll` or `finish`. Anything else ends the call with `invalid_action`, keeping the notes so far (Decision 0020 L6).
- Each step goes through the loop middleware's admission on a route the caller passes in: the reservation, invocation ticket and receipt, the run's `model_calls` and budget, and the shared transport. The model is wrapped as an `AdmittedModel`, so a call made outside an admitted dispatch fails as unadmitted.
- The worker's inference source can bind any role of the run's frozen policy (`role_route`), and so serves the `researcher` route. A route whose catalog entry lacks tool support is refused with `unsupported_request_option` before anything is sent.
- A CDP page over the isolated executor's session reads a page's text and links, navigates and scrolls, using the locked `websockets` client. No package is added or removed.

## Capabilities

### New Capabilities

- `browsing-loop`: the admitted, read-only browsing loop.

### Modified Capabilities

None.

## Impact

`application/browsing_loop.py`, `application/worker_inference.py`, `adapters/loop_middleware.py`, `adapters/browser_executor.py`, a disposable-database check and offline tests. `browse_goal` itself stays unregistered until US-14.12.
