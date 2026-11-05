---
paths:
  - "supabase/**/*"
  - "packages/db-types/**/*"
  - "services/agent/src/autobots/adapters/persistence/**/*"
---

# Database ownership

Follow [DH-07](../../PRD-Development-Harness.md#dh-07-supabase-migrations-seeds-and-database-quality) and `autobots-supabase`.

- SQL migrations own application schema; never edit applied migrations or introduce competing history. Document locks/backfills and forward recovery.
- Public domain tables require RLS. `app_private` and `agent_runtime` remain private direct-SQL schemas, outside PostgREST/Realtime/browser grants.
- Separate repeatable reference data, disposable fixtures and secure Auth bootstrap. No DDL, real credentials or pending inference jobs in seeds.
- Verify actual anonymous/owner/other-workspace roles and private Storage; service-role success does not prove RLS. Prove repeatable seeds and schema/type compatibility on a qualified disposable target.
- Persistent SQL apply is an explicit guarded operation. Normal checks/hooks do not reset, seed, migrate or delete persistent data. Dry-run is not execution evidence.

## Check and review

Check: the `db` profile of [`scripts/verify.py`](../../scripts/verify.py). Review: [`autobots-review-change`](../skills/autobots-review-change/SKILL.md).
