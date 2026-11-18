## Why

US-14.24, [Decision 0033](../../../docs/engineering/decisions/0033-google-toolkit-and-tool-switches.md) W1 to W5, and PRD-Tool-Catalog TW-01 to TW-03. The owner wants tools easy to turn on and off, a provider's subtools separately or as a group, without removing keys or editing every Expert.

## What Changes

- **Storage.** A private table, `app_private.tool_switches` (migration 64), holds per-workspace switches for Expert-grantable tools and for groups. Each switch has an expected version, and no row means on.
- **Availability.** The workspace view (`tool_keys.key_sources`) carries the switches. A tool that is off, or in a group that is off, reads `disabled_by_policy` with reason `turned_off` or `group_turned_off`. Admission and Expert saves therefore refuse it, as for any unavailable tool.
- **The gateway** refuses each call to a turned-off tool with `tool_turned_off` before any effect, for runs already in progress.
- **The contract:**
  - `ToolDescriptor.switch` and `ToolGroupDescriptor.switch` (`enabled`, `version`, `by`);
  - `ToolCatalog.viewer_can_switch`;
  - `PUT /v1/tools/{tool_id}/switch` and `PUT /v1/tools/groups/{group}/switch`, owner-only and versioned.

  OpenAPI and the client are regenerated.
- **The Tools page** shows an accessible on/off switch on each switchable tool and group for the owner. A member sees each state in words, and the repair text says how to turn a tool back on.

## Capabilities

### New Capabilities

- `tool-switches`: per-workspace on/off switches for tools and groups, their effect on availability, admission, Expert saves and calls in progress, who may change them, their storage and the Tools page controls.

### Modified Capabilities

None.

## Impact

- **Database:** `supabase/migrations/20261118000064_tool_switches.sql`, the schema snapshot and readiness.
- **Backend:**
  - `domain/tool_switches.py` and `application/tool_switches.py`, both new;
  - `application/tool_keys.py`, `application/tool_catalog.py`, `application/tool_gateway.py` and `domain/stops.py`;
  - `api/tool_routes.py` and `contracts/tool_catalog.py`.
- **Web:** `components/tools/*`, `lib/tools/text.ts`, the generated client, and the unit and browser suites.
- **Docs:** `CODEBASE.md` and the operations runbook. The owner applies migration 64 with `make migrate`.
