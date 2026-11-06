## Why

US-10.2's finding B9: pause, cancel, resume and model-call reconciliation exist only as API routes, so a person can't control a run without calling the API. Decision 0009 adds them to the run page.

## What Changes

- The run page offers Pause, Resume and Cancel by the run's state, using the existing routes and the run's current version, and offers nothing on a terminal run.
- An open model call shows a form for the charge seen in the provider's own records, in US dollars, using the existing owner-only route.
- Each refusal shows the server's reason, and the run stays as it was.
- Browser tests on a disposable stack with the scripted worker, which gains a slow goal and a second death for them.

## Capabilities

### New Capabilities

- `run-controls`: what a person can do to a run from its page, and what's refused.

### Modified Capabilities

None.

## Impact

`apps/web/components/run-controls.tsx`, `run-workspace.tsx`, `tests/web/fixture_worker.py` and a new browser suite. No API, contract or database change.
