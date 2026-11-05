# Verification — us-6-1-typed-immutable-workflow-definition

Change: us-6-1-typed-immutable-workflow-definition
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `990f0f0`, working tree with this change. Unit fixtures with no database, real Postgres through the runtime role, and the real API in Chromium on a disposable stack. `pytest`: 251 passed. `scripts/app_db.py types`: 350 cases passed. `scripts/qualify_identity.py` exit 0, 214 cases. `--profile full` passed.

## Scenarios

**Validate before publication: observed.**
- Graphs covering all ten documented blocks validate, including a foreach with its join and a condition's two branches.
- Typed errors, each with its fixture: duplicate node, unknown block, unknown version, unknown node, unknown port, a port linked twice, an unlinked required input, a type mismatch, a bad input type, an unknown transform, an unbounded or oversized foreach, a foreach with no join, a value crossing the iteration boundary, a join with no foreach, and a graph with no output.
- Through the API: validate returns those errors, an invalid graph gets 422 and publishes nothing, a valid one publishes as version 1 with its hash and block versions, a stale version conflicts, and the runtime role can't rewrite a published version.

**Preserve exact execution bindings: observed.**
- An execution stores the exact version, hash and block versions, and a repeat with its key returns the same one. A later version is a different binding.
- A model's proposal is validated the same way, an invalid one is refused, and a valid one is marked `model_proposal`.
- An arbitrary cycle is `cycle_not_supported`.
- Inputs of the wrong type, a missing version and another workspace are refused. In the browser another workspace gets 404, and a member can't publish (403).

## Findings

- **`nested_foreach` isn't reachable from a typed graph today.** A foreach's item is `json` and its input is `list`, so a nested one fails first as `link_type_mismatch`. The result is the same refusal with a less specific code, and the fixture accepts either.
- **Nothing runs an execution yet.** That's US-6.2, and `workflow_executions` only records the binding.
- **Judgment calls the sources don't fix:** the 100-item foreach cap, five port types, the transform and predicate lists, owner-only publishing, and any member creating an execution.
- **No generator exists yet,** so "a model-generated proposal" here means a graph submitted with `source: model_proposal`. No model wrote one.
- **No independent review.**
