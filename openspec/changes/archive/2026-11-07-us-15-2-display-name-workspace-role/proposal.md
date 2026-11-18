## Why

US-15.2, [PRD-Studio ID-01, ID-02, SH-05 and SE-04](../../../../docs/PRD/PRD-Studio.md#identity), and [Decision 0022 D10](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision). The shell, Home and Settings need a name for the person, their role and their workspaces' names. Today the session summary returns only a user ID and workspace IDs.

## What Changes

- Migration `user_profiles`. Each user has one optional display name of 1 to 60 trimmed characters. RLS lets a user insert and update their own row, and lets the user and members of a shared workspace read it. The runtime role keeps full access.
- `SessionSummary` gains `display_name`, `email` and `workspaces` (ID, name, role). `workspace_ids` stays. Without a saved name, the display name is the part of the token's email before `@`, and otherwise "Member".
- `GET /v1/profile` and `PUT /v1/profile`. An empty or overlong name is refused with `422 display_name_invalid`, and the saved name is left unchanged.
- The shell's footer shows the name, the role in the current workspace and "this Mac", with a menu offering Account and Sign out. A new `/settings/account` page shows the editable name, the read-only email, the role and Sign out.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-identity`: the display name and the richer session summary.

## Impact

- `supabase/migrations/20261107000042_user_profiles.sql`.
- `contracts/service.py`, `api/routes.py`, a new `api/profile_routes.py` and `application/profiles.py`.
- The generated contract and client.
- `apps/web/components/app-shell.tsx` and a new `account-*` component.
- `apps/web/app/settings/account/page.tsx`.
- Tests: `scripts/app_db.py` RLS cases, Python API tests, and `identity.spec.ts`.
