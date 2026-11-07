# Third real Mac sleep

## Why

US-11.10's proof ran before US-11.12 changed `_keep_lease`, the code that runs on wake. Decision 0013 has the owner sleep this Mac once more, on the code that ships.

## What Changes

The owner follows `docs/engineering/runbooks/mac-sleep.md`, on a disposable stack with a scripted model. The first real run failed, so `discount_sleep` changed, which voided US-12.3's binding. It was reviewed and bound again, and a further real sleep proved the fix.

## Impact

One source change, in `application/run_usage.py`, and a new case in `tests/db/wake_check.py`. No spending.
