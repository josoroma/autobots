## Why

US-16.4 carries out [Decision 0023 E4 and E5](../../../docs/engineering/decisions/0023-install-current-and-real-examples.md#decision). The owner asked for a real live qualification of `openai/gpt-6.1-sol-20260929`, shown at Settings → Models. Their persistent install had applied 35 of 49 migrations, so it lacked Sol's profile (migration 40) and its 2026-11-07 qualification row (migration 41), and Settings couldn't show Sol at all.

## What Changes

- **A live pass of US-3.4's corpus on Sol**, with the existing runner (`autobots.operations.route_qualification --profile openai_gpt_6_1_sol --paid`), in Sol's existing ledger so the cumulative spend stays inside Decision 0019 S4's US$1.20 cap. The 2026-11-07 report is kept beside today's.
- **Migration 50** records today's pass in `agent_runtime.route_qualifications` when it passes as the first did: today's date, its findings and `US-16.4` as evidence. `SHIPPED_MIGRATIONS` becomes 50.
- **The install:** backed up through the backup runbook, then brought current through the guarded `persistent_install.py apply`, the only path that changes it. No reset, no volume removal.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `route-qualification-status`: Sol's 2026-11-08 live qualification.

## Impact

- New `supabase/migrations/20261108000050_sol_route_requalified.sql`; `application/schema_release.py`.
- The persistent install's database: migrations 36 to 50 applied.
- Spend: within Sol's ledger, `.checks/route-qualification/sol/ledger.json`.
