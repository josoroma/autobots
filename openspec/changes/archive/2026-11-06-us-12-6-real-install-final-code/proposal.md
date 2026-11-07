# The real install at the final code

## Why

The real install is stopped at migration 32 of 35, so the code released has never run on it. Decision 0013 authorizes bringing it up to date and running one goal.

## What Changes

The upgrade runbook on the install: back up, restore to an isolated copy, try the pending migrations there first, apply them, start it, and run one goal on Terra under the shared ledger.

## Impact

Persistent changes to the real install, and paid calls, as Decision 0013 authorizes for this story alone. No source change.
