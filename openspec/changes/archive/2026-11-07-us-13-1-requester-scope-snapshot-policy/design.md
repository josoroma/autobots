## Context

`approval_gate` stores a request with `argument_hash`, `scope_hash`, `policy_reason` and `resource_target`. A run doesn't record who started it. `admit_run` gets an `actor_id`, but that's a person from the API, a routine's ID from a routine, and the parent run's ID for a child.

## Decisions

**Who started the run.** A new nullable `runs.started_by` is set by an explicit `started_by` argument to `admit_run` and `create_execution`, never taken from `actor_id`. The run and workflow routes pass the signed-in user. A child run copies its parent's value. A routine passes nothing, so its run records no person.

**Columns on `approval_requests`, all nullable for older rows:**

| Column | Holds |
|---|---|
| `requested_by` | the run's `started_by` when the request was stored |
| `requested_by_agent` | `{"kind": "expert", "id", "version"}` from the run's Expert, or `{"kind": "coordinator"}` |
| `scope_snapshot` | `{"tools": {...}, "paths": [...]}`, the exact input of `scope_hash` |
| `policy_version` | `approval-policy/1`, a constant in `tool_gateway.py` |
| `policy_rule` | `consequential_external_write` or `tool_marked` |

`requested_by_agent` is set on every new request, so a request where it's null predates this change. Where it's set but `requested_by` is null, no person started the run, or the run predates `started_by`. The inbox says the person is not recorded for this run, and doesn't guess which.

**Immutability** is a `before update` trigger. It refuses a change to any of the five columns, null to value included, so nothing can fill in an old request. The gateway reads the run's `started_by`, `expert_id` and `expert_version` in the same transaction as the insert.

**The view** adds a `requester` object (person ID, whether it's the viewer, agent kind, and the Expert's ID, version and current name), `scope_snapshot`, `policy_version` and `policy_rule`, each null when not recorded. The Expert's name is read when the view loads. Only its ID and version are snapshots.

**The policy version is changed by hand.** It must change whenever `_approval_reason` or the gateway's approval condition changes. A unit test pins the current reason texts to `approval-policy/1`, so changing one fails until the version is bumped too.

## Risks

- A persistent install without this migration can't run this code. Applying it there is a separate persistent change.
- The legacy arrangement in the database check has to bypass the trigger. It does so with `session_replication_role = replica` in its own transaction, because that's what a row the migration finds looks like.
