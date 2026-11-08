## Context

RN-05 says the worker records each task's start and finish, but the plan model has no action that starts a task. A task's finish is already explicit: `complete_task` records its evidence. Every tool use is already attributed to a task by `served_task`: `complete_task`'s own task, or else the first open task whose dependencies are done and that lists the tool.

## Decisions

- **Start = the first tool use that serves the task.** It is recorded in `begin_use`'s transaction, after `hold_lease`, so the same fencing that refuses a stale use refuses its start. A `complete_task` call serves its own task, so a task finished with no other use still starts first. The finish is an upsert in `complete_task`'s leased transaction, which keeps the first finish.
- **Database time:** `now()` in the writing transaction. Wall time is computed by the database too, from start to finish, or to `now()` for the current task.
- **One row per run and task ID**, kept across plan revisions, because a revision can't change or drop a completed task.
- **Current task:** the open task with the earliest start, then by plan order. Other started open tasks show "To do" with no wall time, since RN-04 has only three markers.
- **A task's tools** are the tools its uses served, in first-use order, with the planning tools left out. They are not the tools the plan declared.
- **Metered calls:** counted the way admission counts them, over the run's root tree (`coalesce(root_run_id, id)`).
- **The panel goes under the list**, like the Workflows preview, so Tab never climbs. It is selected by `?run=<id>`, so a page reload keeps it open.
- **Expected version:** commands send the version the panel loaded, never a fresh one. The existing `RunControls` re-reads the version on each press, so the panel doesn't reuse it.

## Risks

- A task that isn't served by any tool use until its `complete_task` gets a wall time of zero.
