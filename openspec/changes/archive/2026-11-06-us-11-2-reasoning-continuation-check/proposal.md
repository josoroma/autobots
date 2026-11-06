## Why

US-10.2's finding B10: LC-23 asks that reasoning metadata survive a tool continuation, and nothing checks it. Decision 0009 chose a deterministic check and a capped live trial, as LC-23 stands, under a shared US$1 cap.

## What Changes

- A comparison of what a route returned with what the application sends back: survived only when content and ordering are unchanged, dropped when dropped or altered, and not returned when there's nothing to preserve.
- The worker's own continuation path is checked with a fake transport, with no metadata in logs or activity events.
- A paid trial runner, off unless told otherwise, that continues a real tool call on each enabled route, against a ledger shared with US-11.3, and refuses before sending when the trial's worst case would pass US$1.
- The result is recorded with route, date, configuration and reported cost. Loss goes to the owner, and LC-23's text doesn't change.

## Capabilities

### New Capabilities

- `reasoning-continuation`: how reasoning metadata across a tool continuation is checked, tried live, capped and reported.

### Modified Capabilities

None.

## Impact

New `operations/reasoning_trial.py` and tests, `tests/db/product_inference_worker.py`, `scripts/qualify_worker_inference.py`, the operations runbook. Paid calls to OpenRouter only in the trial, under Decision 0009's cap, using the key in `.env`. The worker's behavior doesn't change.
