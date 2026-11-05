## Why

Learned material must not silently become policy. PRD 8.5 and SP-016 require evidence, regression, review and versioned promotion with rollback, and they treat retrieved and generated text as untrusted.

## What Changes

- `improvement_candidates`, immutable `knowledge_versions`, and `knowledge_heads` for what's active.
- `application/improvements.py`: propose, regression, an owner's decision, and rollback. A candidate has no field that could change a grant or a model. Regression refuses missing or foreign evidence and text that claims authority.
- A promoted memory joins search, and a promoted skill is added to a new run's instructions as reference, frozen at admission. This also loads the skills `US-5.1` only stored.
- A `propose_improvement` tool, which an Expert must be granted, and API routes.

**Limits:** regression is deterministic checks over the proposal, with no replay of held-out tasks, which is US-10.1. The authority check is a pattern list, so it catches common phrasings rather than all of them, and the real protection is that nothing here can reach a grant. No screen.

## Capabilities

### New Capabilities

- `improvements`: reviewed promotion and rollback of memory and skills.

### Modified Capabilities

None.

## Impact

A migration, new modules and routes, `experts.py`, `routines.py`, `memory.py`, `goal_loop.py`, contracts, row types, tests, `scripts/app_db.py`, `CODEBASE.md`. No dependency or paid call.
