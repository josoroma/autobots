## Context

`run_regression` runs the evidence, self-citation and authority checks, then the reviewer's `must_contain` cases, and sets `regression_passed`. `decide` promotes from `regression_passed`. Skills reach a run through `active_skill_text` at admission, and memory through the `search_memory` tool's `memory.search`.

## Decisions

**Tables** (`app_private`, runtime-only):

| Table | Holds |
|---|---|
| `improvement_replays` | `id`, `workspace_id`, `candidate_id`, `requested_by`, `created_at` |
| `improvement_replay_runs` | `replay_id`, `run_id` (unique), `position`, `task` (goal and criteria) |

**Requesting a replay** (`request_replay`, `POST /v1/improvements/{id}/replay`, owner-only, with an `Idempotency-Key`):
- It needs a `regression_passed` candidate, from 1 to 10 tasks, and `limit_micro_usd` per task.
- A task whose normalized goal equals the goal of an evidence run or of the source run is refused with `task_drawn_from_proposal`.
- Each task is admitted with `admit_run` under the workspace's policy, `started_by` the owner, the default loop grants (`propose_improvement` excluded), and instructions holding the proposal when it's a skill.
- The route checks provider readiness as run admission does.

**Applying a memory proposal:** the `search_memory` tool looks up whether its run is a replay run. If it is, `memory.search` hides the active item for that key and adds the candidate as a hit when its text matches the query. Every other run searches as before.

**The replay's state** is derived on read from the latest replay's runs, never stored:

| State | When |
|---|---|
| `passed` | every run `succeeded` |
| `failed` | any run reached another terminal state |
| `running` | otherwise |

`decide` refuses promotion with `replay_required`, `replay_running` or `replay_failed` before changing anything. Reject needs no replay.

**Text cases** in `RegressionRun` become optional (`min_length=0`), and `regression_cases_required` goes. A case that fails still fails regression.

**Testing** uses the scripted model in `tests/db/goal_loop_script.py`, driving each replay run through `process_next`.

## Risks

- The tasks run with the default grants, not an Expert's.
- A run cancelled by a person reads as a failed replay, which is the intent.
