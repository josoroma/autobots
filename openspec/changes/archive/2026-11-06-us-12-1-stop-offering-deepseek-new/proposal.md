# Stop offering DeepSeek for new runs

## Why

DeepSeek can be chosen today with no task qualification, and none of its goals succeeded. Decision 0013 takes it out of new work until it qualifies.

## What Changes

- One list in `domain/models.py` says what new work can choose.
- The API, workflows and routines refuse anything else with `model_not_offered` and no substitute. Saved choices aren't rewritten.
- Pickers leave it out. Settings still lists it as approved, with its record, and shows a saved choice that names it.
- Runs already admitted keep their frozen route, and the qualification runner still runs it.

## Impact

`ModelAvailability.offered` is a new required field, so clients regenerate. No migration, and no paid call.
