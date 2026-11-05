## Why

Fresh setup and upgrades must preserve user data, and SP-015, DH-07 and LM-05 require one ordered SQL history, repeatable reference seeds and a migration identity separate from runtime identity.

## What Changes

- `supabase/migrations/`: workspaces, memberships, runs and run events with RLS, column-level grants that keep lease and checkpoint columns private, `app_private` and `agent_runtime` schemas, and reference model profiles.
- `supabase/bootstrap/roles.sql`: `autobots_migrator`, the only DDL role, and `autobots_runtime`, which cannot run DDL.
- `supabase/seeds/reference.sql`: the two approved SP-006 profiles, repeatable, keeping a user's label.
- `scripts/app_db.py`: migrations in their own transactions with a checksum history, refused without the disposable marker, and a `qualify` run on the pinned image. It also generates public row types into `packages/db-types`, and detects drift. The `db` profile runs it.

**Limits:** no persistent apply; that needs a story that starts a persistent stack. Tables beyond this slice arrive with their stories. Authorization against real Auth and Storage is US-2.3's.

## Capabilities

### New Capabilities

- `application-migrations`: ordered migrations and reference seeds, with migration authority separate from runtime.

### Modified Capabilities

None.

## Impact

New `supabase/`, `scripts/app_db.py`, `tests/db/` fixtures, `tests/harness/test_app_db.py` and `packages/db-types` content. Updates `scripts/verify.py`, `scripts/harness_lib.py`, the Supabase runbook and `CODEBASE.md`. Disposable Docker only. No model call or persistent change.
