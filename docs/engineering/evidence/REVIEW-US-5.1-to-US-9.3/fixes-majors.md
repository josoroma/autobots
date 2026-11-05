# Fixes for review round 1's majors

Findings M1 to M33 are in `review-r1.md`. **The 41 minors are still open, and no story status changed.** Scripted or fake models on disposable stacks: no paid call, no real credential. This doesn't establish H1 or product acceptance.

## Outcomes

| ID | Outcome | Observed in |
|---|---|---|
| M1 | An effect is admitted only while the run is running, under a lock, and a readback has a time limit | `major_check` |
| M2 | An approval's time runs from the decision. An unused one past it asks a person again, and a confirmed failure uses it up. A person's `not_delivered` ruling grants one more try. An effect already sent is read from its receipt, whatever the date | `major_check` |
| M3 | A child waiting for a person pauses its parent, and its assignment stays open. The parent then needs a resume after the child's approval | `major_check`, with an arranged result from the child |
| M4 | Unknown effects count across the tree, and can be settled from the parent's page | `major_check` |
| M5 | A dispatch checks every ancestor, not only the direct parent | `major_check` |
| M6 | Already fixed with the blockers: `assignment_busy` stops a goal run | Read, not exercised |
| M7 | The prompt names the Experts a coordinator can assign, and tells a child where it may write | `major_check`, by reading the text. **No live model has used it** |
| M8 | Only an owner can choose an Expert version other than the session's pin. See decisions | Read, **not exercised** |
| M9 | Each purge commits before any bytes go, on the API's kind of connection too | `major_check` |
| M10 | A key lasts as long as its run's content, and through unresolved effects or calls. `receipt_days` needs `run_days` | `major_check`, unit |
| M11 | Cancelling closes open obligations, and refused runs can't block later ones | `major_check`, with 105 refused runs |
| M12 | A restore starts only the database, writes the hold, then starts the rest. The hold stays if a later service fails | `qualify_backup`, for the order's outcome |
| M13 | `local_backup.py verify` checks every manifest fact on a real restore: counts, users, credentials count, migrations, threads, provider key, hold, anonymous reads and artifact hashes | `qualify_backup`, including a wrong key |
| M14 | Routines wait while Storage, the disk or the adapter isn't ready. Retention doesn't, as it removes content and already tolerates Storage being down | `major_check` |
| M15 | The adapter's identity covers `langgraph-checkpoint-postgres`, `langgraph-checkpoint`, `langgraph`, `deepagents` and `langchain-core`, and a qualification names its evidence | Unit, `qualify_upgrade` |
| M16 | A snapshot records each profile's model, and the worker refuses a run whose mapping has since changed | Unit |
| M17 | The product worker runs a workflow to the end, once inference is enabled | `qualify_worker_inference` |
| M18 | Approval, condition and identity pass their input's type along, and transforms state theirs | Unit |
| M19 | Each node instance is its own operation, including two nodes with the same tool and arguments | Unit, on the operation identity |
| M20 | A workflow's run gets the workspace's model policy | `major_check` |
| M21 | The monitor says running, waiting for approval, stopped here or didn't run. A node that started is never reported as not run | `major_check`. **The new text isn't asserted in a browser** |
| M22 | A routine's limit and tools reach its workflow's run | `major_check` |
| M23 | After long away, the newest occurrences are kept and the rest are counted in history | Unit |
| M24 | The clock is read under the routine's lock, and an evaluated time never moves back | `major_check` |
| M25 | Intervals are bounded, and one routine raising can't stop the others | Unit, `major_check` |
| M26 | Traced: a budget refusal during compaction already became a clean stop through `_with_slot`. A `LimitReached` guard and test were added | Unit. **The finding's described failure wasn't reproduced** |
| M27 | A run's search covers its own files. Memory can belong to an Expert, set by an owner's note or from the run a promoted proposal came from. See limits | `major_check`. **The promotion path isn't exercised** |
| M28 | Summary input keeps everything up to the offload threshold | Unit |
| M29 | The SDK's summarizer is replaced by a no-op, so it can't call the model outside admission | Unit, on the graph's nodes |
| M30 | **Not fixed.** A different summarizer profile still pauses with `route_not_bound`. See limits | |
| M31 | Tool text is delimited as data in the summary request, and the summary comes back as the model's own message | Unit |
| M32 | `to_version: 0` undoes a first promotion, and every version stays | `improvement_check` |
| M33 | Regression uses the reviewer's cases, not the proposer's, and a run can't cite itself or its own artifact | `improvement_check`, for the run itself |

So 31 are fixed, M6 was already fixed and M30 isn't.

## Results

Each exit 0 on the final code, apart from a test-only type fix: `verify --profile db` (with `app_db` 445 cases and `qualify_identity` 317), `--profile operations` (operations 69, backup 48, upgrade 45), `--profile fast`, `--profile harness`, and `scripts/qualify_worker_inference.py` (36).

## Review of these fixes

One fresh read-only reviewer read `4b0e816`, and traced rather than ran it. It found these, all fixed afterwards in the commit holding this text:

- **A blocker:** the new expiry check ran before the receipt was read. A delivered effect replayed past its approval's time was reported as expired, and could fail its run.
- **An approval lapsing for good:** its time ran from the request, not the decision, and it could never be asked again.
- **Half of M27:** nothing but a test wrote `expert_id`.
- **The monitor:** a node mid-effect on a finished run said it hadn't run.
- **M14 overreaching:** it also stopped retention.
- **Tests that couldn't fail:** several, including the summarizer's, M1's and M19's.

**Those fixes have had no independent review.** Each review so far has found something real in the previous round, so expect this one to hold defects too.

## Limits

- **M30:** a run whose summarizer differs from its executor stops at its first compaction, with a clear reason. Fixing it needs a worker that holds two model routes.
- **M27:** the PRD also names an owner in memory's scope. A run records no owner, so that isn't enforced. Expert scope is, for memory that names one: existing notes stay shared.
- **M3:** after approving a child's request, someone has to resume the parent too.
- **M12:** the database's port is published for a moment before the hold. The port is new, and nothing has been told it.
- **M13:** `verify` can't test owner sign-in without their passwords, so that step stays with the operator, and credential decryption is compared by key fingerprint only. `qualify_backup` still tests both.
- **M24:** no test proves the clock is read under the lock, as they all pass a fixed time.
- **M11:** past about 2,000 refused runs, later ones can still wait, since each pass restarts at the oldest.
- **M33:** a reviewer's check is still only a text match.
- **Non-tool text in summaries:** a model's own text over 4,000 characters is cut with no pointer back.
- **M6:** a child can keep running under a parent whose lease moved. No duplicate starts.
- **Running workflows:** one running when M19 ships gets new operation identities, so a replayed step could repeat. No such executions exist on this machine.

## Decisions for the owner

1. **M8:** should members be able to pick an earlier Expert version at all? I chose owner-only, as the safest reading of an open question.
2. **M33:** the PRD asks for "regression tasks". This requires a reviewer's own text checks, and real held-out replay stays with US-10.1. Is that enough to gate promotion for now?
3. **M32:** `to_version: 0` as "no active version" is my choice of interface.
