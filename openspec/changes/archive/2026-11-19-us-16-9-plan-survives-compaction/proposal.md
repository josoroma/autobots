# Proposal: The plan survives compaction

Story: **US-16.9**, by [Decision 0034](../../../docs/engineering/decisions/0034-deep-research-like-content-writer.md) C1.

## Why

The second live Deep research writer run read and saved its sources, then proposed a new plan at its first compaction, first with no reason and then rewriting a completed task. The plan guard refused both, and the run failed at its repair limit. A compacted call's state block pins the goal, criteria, tools, paths, open waits and approvals, but not the plan, so the model no longer knew it had one.

## What Changes

- `state_block` adds the run's current plan: its version, and each task's ID, title and criteria, marked done or open. It says to continue that plan with `complete_task`, and to revise it only with a reason that keeps completed tasks.
- A run with no plan yet says so.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `memory-compaction`: the pinned state also holds the plan.

## Impact

`application/compaction.py`, a unit test, `tests/db/checks/memory_check.py` and `CODEBASE.md`. No contract, migration or limit change.
