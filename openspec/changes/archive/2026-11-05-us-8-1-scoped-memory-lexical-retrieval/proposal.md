## Why

Long work must keep its criteria and citations within a bounded context, with no hidden inference service. PRD 8.4 and SP-016 require offloaded output, summaries using the snapshotted role, and local lexical retrieval scoped by workspace.

## What Changes

- `public.memory_items` and `run_files` get full-text search. `search_memory` is a gateway tool, and there's an API route.
- `run_offloads` keeps long tool output whole, and `read_offload` reads it back, for this run only.
- `application/compaction.py`, in the model call's path: long output becomes a pointer, and older turns become a summary under the run's frozen `summarizer` role, through admission. Goal, criteria, permissions and open waits are read fresh from records for every compacted view.
- Citations are worked out by code from what was offloaded. A truncated summary stops the run with `compaction_failed`.

**Limits:** a scripted model. Budget is in characters, since no tokenizer is pinned, and the 512-token output limit isn't sent to a provider. The SDK's own summarizer stays refused by `AdmittedModel`. A summarizer bound to a different profile than the executor stops with `route_not_bound`, since a worker has one route today.

## Capabilities

### New Capabilities

- `memory-compaction`: scoped retrieval and compaction that keeps critical state out of summaries.

### Modified Capabilities

None.

## Impact

A migration, new modules, `loop_middleware.py`, `goal_loop.py`, two more default tools, an API route, tests, `scripts/app_db.py`, `CODEBASE.md`. No dependency or paid call.
