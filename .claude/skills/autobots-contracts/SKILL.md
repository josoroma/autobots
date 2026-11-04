---
name: autobots-contracts
description: Evolve and verify Autobots public API, event, database and state contracts with Pydantic/OpenAPI ownership, generated TypeScript consumers and explicit compatibility checks.
---

# Contract ownership and compatibility

Read `.claude/autobots.json`, the mapped contract, selected source requirements and [DH-06 contract standards](../../../PRD-Development-Harness.md#models-contracts-and-state). Inspect producers and consumers before editing.

- Pydantic/OpenAPI owns public API DTOs; generate TypeScript consumers instead of parallel handwritten interfaces. SQL owns persistent schema; generated Supabase types cover intended exposed schemas only.
- Keep domain objects, rows, graph checkpoint state, public events and UI projections distinct. Use the canonical state/transition contract; do not create a second UI enum or resume terminal runs.
- Version event envelopes, workflow IR, checkpoint-compatible state and immutable model-policy snapshots. Specify compatibility for removed/renamed fields and unknown values, plus upgrade/recovery behavior.
- Generate schemas through the offline pure app factory, to a temporary destination; compare normalized artifacts and update intended outputs together. Generation must not require services, credentials or paid inference.
- Use shared fixtures to test both Python validation and TypeScript boundary parsing. Compile-time types do not validate received JSON. Test unauthorized/private fields and event projection leakage.

Return source-to-contract mapping, changed producers/consumers, compatibility decision and actual drift/behavior evidence. Coordinate ownership before shared generation; don't let concurrent writers overwrite generated outputs. Record missing generator tooling as not implemented, not a clean drift check.
