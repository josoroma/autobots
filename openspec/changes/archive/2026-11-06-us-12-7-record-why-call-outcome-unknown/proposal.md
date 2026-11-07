# Record why a call's outcome is unknown

## Why

US-12.4 paused a run as `uncertain_acceptance` with no recorded cause, and the owner chose to record it now, by Decision 0014.

## What Changes

Each path that ends a dispatched call as `uncertain_acceptance` or `partial_stream` writes one `worker.call_uncertain` log event, by type, status or reason, with no message text.

## Impact

`loop_middleware.py`, one optional field on `ProviderFailure`, tests and the operations runbook. No migration, screen, state or charge changes, and no paid call. It voids US-12.3's binding, which US-12.8 replaces.
