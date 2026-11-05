# Verification — us-2-4-application-migrations-deterministic-seeds

Change: us-2-4-application-migrations-deterministic-seeds
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `c895e82`, working tree with this change. Real disposable database on the pinned `supabase/postgres:17.6.1.136` image. No persistent target or model call.

## Scenarios

**Replay and upgrade application schema: observed on a disposable target.** `scripts/app_db.py qualify`, through `--profile db`, 38 of 38 cases, about 13 seconds:
- Fresh replay of 3 migrations as `autobots_migrator`, which then owns the tables. Repeated apply changes nothing. A failing migration rolls back. An edited applied migration is refused by checksum.
- Prior fixture: through migration 2, with rows, then migration 3: the row stays and the new column takes its default.
- Reference seeds: two runs give the same row hash. Rows are exactly the two SP-006 profiles. A label edited by the runtime role survives a repeat.
- Constraints refuse an unknown workspace, a status outside SP-010, negative money, a duplicate event sequence and an unapproved profile.
- Real `anon` and `authenticated` roles: anonymous denied, lease columns and private schemas denied, writes denied. A member reads 1 run, another workspace reads 0.
- `packages/db-types/src/generated.ts` matches the schema, holding `public` tables only.

**Separate migration authority: observed.**
- `autobots_runtime` is refused creating or altering a table, dropping one, creating a schema and writing migration history, and still does its own update.
- Framework tables: the runtime role's real `PostgresSaver.setup()` is refused. The migration identity's creates the checkpoint tables in `agent_runtime`. The runtime role can then use them, and cannot create there.
- A wrong disposable marker refuses migration.
- No `alembic`, `create_all`, `.setup()` or DDL text in `services/agent/src`, also a harness test.
- Afterwards no project containers or volumes remain, and other Docker resources are unchanged.

## Findings

- **No persistent apply exists.** The story's Given is a marked disposable database. The persistent path, with its identity and baseline checks, is unbuilt, and whichever story first starts a persistent stack owns it. The source lists the persistent checks; the disposable marker is what is enforced now.
- **The framework step is exercised only during qualification.** There is no separate operator command for it yet. Its coordinated version record, which SP-015 asks for, is not implemented.
- **`autobots_migrator` holds `anon` and `authenticated` memberships** with `noinherit`, so it can grant to them. A membership still allows `set role`. Migration credentials must stay out of runtime configuration, which no runtime yet tests.
- **Runtime policies use `using (true)`,** so workspace scoping for the runtime role is application logic. That matches LM-05's warning that a service client is not RLS-enforced.
- **`workspace_members.user_id` has no foreign key to `auth.users`.** US-2.3 owns identity on the real Auth service.
- **`packages/db-types` was not separately typechecked** in a profile.
- **Runbook:** the added section's `qualify`, `types` and `jq` commands were run.
- This is not H1 or product acceptance.
