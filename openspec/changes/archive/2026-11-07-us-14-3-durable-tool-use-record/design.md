## Recording around the gateway

`execute` wraps the existing pipeline, renamed `_dispatch`: `begin_use` → `_dispatch` → `complete_use`. Every caller of the gateway, the goal loop, workflow nodes and assignments, is covered without changes. A `None` connection, as in unit tests that check refusal before any effect, records nothing.

`begin_use` holds the lease (share lock) and an advisory lock per run for the sequence, inserts the row and appends the started event. `complete_use` holds the lease, updates only its own open row at its own generation, and appends the completed event with a database-measured duration. A lease lost in between leaves the row open, shown as not finished, and the effect's receipt remains the effect ledger.

## Attribution

The served task is computed, not written by the model: `complete_task` names its task; otherwise the first open, unblocked task of the latest plan that lists the tool. A call no task lists, such as `propose_plan`, has no task.

## Metering

Admission is a separate short transaction: lease held, advisory lock on the root run, count of `metered` rows, then this row marked `metered`. It runs after ownership is checked and before approval or any handler, so a refused call sends nothing.

## Compatibility

New event members keep `schema_version: 1` (Q13). The web consumer parses events one at a time and skips one it can't parse, so a future type can't break the page.
