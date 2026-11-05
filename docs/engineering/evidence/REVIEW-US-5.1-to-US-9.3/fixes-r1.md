# Fixes for review round 1's blockers

Findings are in `review-r1.md` in this directory, from the review session. It was uncommitted in the main checkout when this was written. This covers its 10 blockers only: **the 33 majors and 41 minors are still open, and no story status changed.**

Branch `delivery/blocker-fixes`, cut from `dce9e19` in its own worktree, so it excludes the worker and operations sessions' uncommitted work. Scripted model, disposable stacks. No real credential or paid call. This doesn't establish H1 or product acceptance.

## What changed

| ID | Change | Observed in |
|---|---|---|
| B1 | Arguments up to 64,000 characters show whole, with no silent cut. Longer ones are marked and can be rejected but not approved (`approval_too_large`). | `blocker_check`, browser |
| B2 | An effect is admitted while holding the lease. A receipt only moves forward: a late failure can't overwrite a success, and a real late success outranks a ruling that it didn't happen, as repeating the effect would be the worse mistake. Re-admission won't send over a success that landed after its read. | `blocker_check` |
| B3 | A cancelled parent stays `cancelling` and is re-queued until its children are terminal, at any depth. Assignments stay open until then. Settlement also cancels a child the cascade missed, and a child can't be admitted under a parent that isn't running. | `assignment_check`, depth 2 arranged |
| B4 | A replay answers from a finished child instead of waiting on a lease. On replay only, a child waiting for a person pauses the parent rather than spinning. | `assignment_check` |
| B5 | A run left `verifying` needs only `COMPLETE`. Refusals go to `_finish`, which settles a cancelling run. | `workflow_run_check`, worker death arranged |
| B6 | `run_not_running`, `run_not_found`, `assignment_lost` and `assignment_busy` stop a node instead of failing it. On resume it gets its result from the receipt. | `blocker_check`, gateway level |
| B7 | Two foreach regions can't feed one join (`join_multiple_foreach`), and neither can a foreach plus an outside source (`join_mixed_sources`). A workflow nothing can move fails with `workflow_stalled`. A version the rules now reject fails with `workflow_invalid`. | `test_workflows`, `workflow_run_check` |
| B8 | Any stop code on a cancelling run settles the cancel, if this worker still holds the lease. What an old release left is classified first. | `blocker_check`, contract edit arranged |
| B9 | `read_offload` reads in pages of up to 4,000 characters. Pages aren't offloaded again, and only the latest two stay in view. | `blocker_check` |
| B10 | An owner can name `propose_improvement` on an Expert. Runs with no Expert and workflows don't get it. | `improvement_check` |

## Review of the fixes

There were two read-only rounds, each by a fresh reviewer. Each found real defects in the code under review, so neither alone was enough, and **the changes after round 2 have had no independent review.**

The first set was reviewed independently and read-only, without the author's conclusions. It found B2, B3 and B6 only partly fixed:

- **A dropped success:** a fresh attempt after a person's ruling left the receipt `started` for good, and retention could then never purge the run.
- **Depth 2:** B3's fix still stranded a child with a live grandchild.
- **Agent nodes:** a pause still failed them permanently.
- **Re-admission:** it ignored its own guard, so it could send twice.
- **Context:** pages could overrun the budget.
- **Smaller ones, also fixed:** a stale worker could start settlement, a replay spun on a child waiting for a person, "risk-free" displayed as `ri[redacted]`, a pre-existing bad graph still ran, and a child's stop reason could be stale.
- **Weak tests:** it named several checks that would pass on a wrong fix. These now assert the real outcome. The own tests had passed on the partly fixed code.

Round 2, on `3f758f2`, found:

- **A hot loop:** a child admitted as the cancel landed was never cancelled, so its parent re-queued forever.
- **Goal runs:** `assignment_busy` didn't stop them, so a model could start a duplicate child.
- **A mixed join:** a foreach plus an input feeding one join passed validation and dropped items.
- **A discarded success:** a late real success after a `not_delivered` ruling was lost, and the next replay sent again.
- **An overstated record:** this file claimed more for B4 than the code does.
- **Unproven code:** a test that couldn't fail, and code no test reached.

## Results

On the final code, from the worktree, each exit 0: `verify --profile db` (with 286 identity cases), `--profile fast`, `--profile harness`, `qualify_upgrade` (41), `qualify_operations` (70), `qualify_backup` (45).

## Limits

- A stall after a receipt commits and before the handler sends can still duplicate through a readback miss. A lease can't be held across a send, so this narrows the window but can't close it. Effects on a destination that doesn't dedupe still need US-7.2's readback.
- B6 was observed at gateway and `_tool` level, not through a full workflow pause and resume. `assignment_lost` and `assignment_busy` as stops were read, not exercised.
- The `workflow_stalled` and `workflow_invalid` cases force the condition by replacing a function, because no published graph can reach it now.
- A cancelled parent retries when its child's lease expires, so settling can take up to a lease.
- Nothing was exercised with a real model or the product worker.
- On a child's first drive, a request waiting for a person still closes the assignment, and a workflow agent node fails as `agent_waiting`. This is latent while Experts have no consequential tool (review M3).
- A stored result can only be read as far as the run's calls allow: one call per page of 4,000 characters, shared across the run's 24, so about 96K at most, though tools may return 300K.
- `_refuse_if_waiting` and the `children_settling` branch in `assignments.py` have no test.
- An execution already running when a graph shape became invalid fails midway.

## Decisions for the owner

- 64,000 characters as the most a reviewer is shown.
- Proposals granted per Expert, not by default.
