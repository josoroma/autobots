# Verification — us-6-2-workflow-readiness-emissions-restart

Change: us-6-2-workflow-readiness-emissions-restart
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `9a0fb39`, working tree with this change. Golden unit fixtures with no database, then real Postgres and Storage on a disposable stack, with a real killed process and a scripted model behind the agent step. `pytest`: 265 passed. `scripts/qualify_identity.py` exit 0, 236 cases. `scripts/app_db.py types`: 350 cases passed. `--profile full` passed.

## Scenarios

**Separate node instances and emissions: observed.**
- A foreach over three items gave instances `up#0`, `up#1` and `up#2`, with emissions `A`, `B` and `C` under their own keys, and the join gathered them in order.
- A branch not taken is `skipped`, a list past the bound is `failed` with `foreach_over_bound`, and what follows it is `blocked`. An instance with no row yet is waiting. A failed iteration blocks the join and leaves the good iteration's emission in place.
- A unit fixture filters inside an iteration, so a skipped iteration contributes nothing. An empty list joins to `[]`.
- Reads and artifacts go through the gateway, an approval step waits with nothing after it and replays on the decision, and a rejection fails the step. An agent step runs one assignment, and its honest failure fails the step.

**Restart inside iteration: observed, with a real killed process.**
- A worker process was killed by SIGKILL right after the second iteration committed, exit -9, with `save#0` and `save#1` saved.
- After an arranged lease expiry, a replacement under generation 2 kept all 6 earlier emissions identical, including their timestamps, and went from 2 artifacts to 3, repeating no known effect. The execution finished with 3 artifact IDs.
- A stale worker commits nothing, and a cancelled execution doesn't run.

## Findings

- **The foreach item needed a declared type.** It was `json`, which can't feed a typed port like `string`, so a loop couldn't reach an artifact. `item_type` is now optional config, checked across links. That also makes `nested_foreach` reachable, and the US-6.1 fixture now asserts it.
- **A crash between an effect and its commit relies on receipts,** which the killed worker shows for the artifact path. A failure in `publish` after `save`, and a kill inside an approval step, aren't separate cases.
- **The PRD's "HTTP/read connector" is only a run-file read here,** since no connector exists. An agent step has no iteration-specific test.
- **No credential check on execution yet.** A workflow with no agent step needs no model. US-6.3 adds the check for agent steps at the route.
- **Limits:** no product worker process, and no screens, which is US-6.3. `running` is defined but not yet written.
- **No independent review.**
