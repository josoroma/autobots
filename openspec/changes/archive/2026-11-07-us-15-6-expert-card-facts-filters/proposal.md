## Why

US-15.6, [PRD-Studio EX-01 to EX-03](../../../PRD-Studio.md#experts) and [Decision 0022 D14](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision). Expert cards show only a version and raw bindings. They have no usage, no way to start a run, no filters by effect, and no note when a tool needs approval on every call.

## What Changes

- `ExpertView` gains `run_count` and `last_run_at`, counted from the runs started with that Expert.
- Each card shows the executor's role and profile (or the workspace default), the first four tools and "+N", "N runs · last …", and Start run, which opens a direct session whose run creation shows the MP-07 disclosure. A tool that needs approval on every call is noted in words, such as "Approval on every issue".
- Filters with counts: All, Can change things outside (any consequential tool, from the catalog) and Read only (the complement, D14). There's also a search by name.
- Start run sits in the card's top row, so keyboard focus never moves up between cards.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `experts`: card facts, filters and Start run.

## Impact

- `contracts/experts.py` and `application/experts.py`.
- The generated contract and client.
- `apps/web/components/experts-panel.tsx`.
- `scripts/qualify_identity.py`, which arranges three Experts.
- `experts.spec.ts`.
