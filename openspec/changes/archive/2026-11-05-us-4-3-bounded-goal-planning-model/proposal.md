## Why

Work must progress with inspectable plans and finite limits. SP-008 and SP-011 require versioned plans that keep criteria and evidence without widening scope, and a root envelope that stops new work honestly.

## What Changes

- Admission stores a `GoalSpec` with the original request, criteria and grants. `RunRequest` gains optional `acceptance_criteria`.
- `application/plans.py`: `propose_plan` and `complete_task` tools. The model proposes, and code validates, versions and judges completion from recorded evidence.
- `application/run_usage.py`: SP-008's root limits, counted in the database so a replacement worker inherits them.
- `adapters/loop_middleware.py`: each dispatch checks ownership and limits and goes through `call_with_policy`. `AdmittedModel` refuses any model call outside that path.
- `application/goal_loop.py`: a Deep Agents stage with a fenced checkpointer, and a result that says what really happened.

**Limits:** scripted model only, with no real provider call. No worker process calls this. Context and output token limits, the 80% warning event and child execution aren't built, and `children` is only a counter. Worst-case cost comes from the caller until pricing is wired.

## Capabilities

### New Capabilities

- `goal-loop`: bounded planning and a model and tool loop with honest results.

### Modified Capabilities

None.

## Impact

A migration, new application and adapter modules, `RunRequest` and regenerated contracts, DB and unit tests, `scripts/app_db.py`, `CODEBASE.md`. No dependency or paid call.
