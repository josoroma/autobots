---
name: autobots-supabase
description: Author or review local Supabase migrations, RLS/grants, deterministic seeds and database contract tests. Use for SQL and storage authorization changes; persistent operational apply remains explicit and guarded.
---

# Local database and storage changes

Read `.claude/autobots.json`, the mapped contract/deployment and [DH-07](../../../PRD-Development-Harness.md#dh-07-supabase-migrations-seeds-and-database-quality). Inspect migration history and affected consumers before editing.

- `supabase/migrations/<timestamp>_<description>.sql` is the application schema history. Never edit an applied migration or add competing ORM migration ownership. Document transaction/lock/backfill/forward-recovery behavior; coordinate vendor checkpoint upgrades separately.
- Keep public domain tables under RLS. `app_private` credentials/ledgers and `agent_runtime` checkpoint/store remain private direct-SQL schemas excluded from PostgREST/Realtime/browser roles. Migration and runtime roles differ.
- Storage buckets are private and file-backed locally. Test actual owner/other-workspace/anonymous authorization; service-role success does not prove RLS. Use two fixture users/workspaces and supported Auth APIs.
- Separate repeatable reference upserts from disposable demo/test fixtures and owner credential bootstrap. No committed secrets, writes to Auth internals, DDL in seeds or seeded pending inference jobs. Run seeds twice in the qualified disposable target to prove repeatability.
- Regenerate exposed DB types only after the schema is qualified. Preserve separate Pydantic public API ownership.

This skill authors/reviews changes; it never implicitly applies them to the persistent stack. Explicit operational apply must use a qualified guarded wrapper checking instance/database/direct port/schema/target class. Reset and cleanup reject persistent targets. CLI cloud linking and ordinary-hook mutations are out of scope.

Return migration/seed impact, privilege matrix, recovery notes and actual replay/RLS/type-drift evidence. The `db` profile must report unavailable until implemented; a dry-run alone is not SQL correctness evidence.
