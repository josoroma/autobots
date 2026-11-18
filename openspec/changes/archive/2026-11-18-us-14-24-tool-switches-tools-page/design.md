# Design

## Context

- Availability is computed from a per-workspace view, `tool_keys.key_sources`. It is a `KeySources` dict that also carries `.sources`, and every caller builds it: the catalog routes, run admission, Expert saves and the worker. `application/tool_catalog.describe` reads it.
- The gateway re-reads ownership and Expert grants on each call (`admission_refusal`).
- Owner-only settings use `OwnerWorkspace` and an expected version (Keys & vars).

## Goals / Non-Goals

**Goals:** one source of truth for a workspace's switches, read wherever availability is, and enforced again per call.

**Non-Goals:** per-Expert switches, an audit event or history beyond the version, and switching the plan, delegation or workflow approval tools.

## Decisions

- **Pure rules** (`domain/tool_switches.py`):
  - `switchable_tool(tool_id)` is membership in `EXPERT_TOOLS`.
  - `Switches` maps `(kind, target)` to `Switch(enabled, version)`.
  - `effective(tool_id, group, switches)` returns None when the tool is on, and otherwise `"group"` or `"tool"`. The group wins, so the reason says what to turn back on first.
- **Storage** (`application/tool_switches.py`):
  - `load(connection, workspace_id)` reads the table.
  - `change(connection, workspace_id, kind, target, enabled, expected)` checks the target and takes a row lock. It inserts at version 1 when the expected version is 0, or updates where the version matches. Otherwise it raises `StaleVersion`, reusing Keys & vars' class.
  - An unknown or unswitchable target is `switch_not_found` (404).
- **The view.** `key_sources` sets `view.switches = await tool_switches.load(...)`. A plain environment has no `switches`, and `getattr(environ, "switches", {})` reads it as everything on, so offline checks and the worker's process environment are unchanged.
- **The catalog.** `describe` applies the switch after the key check:
  - off means `disabled_by_policy` with `turned_off` or `group_turned_off`;
  - `switch = ToolSwitchView(enabled=<own>, version=<own>, by=<effective>)` for a switchable tool, and None otherwise.

  `tool_catalog` sets `switch` on each group that holds a switchable tool. The route sets `ToolCatalog.viewer_can_switch` from `is_owner`.
- **The gateway.** `admission_refusal` gains a fresh read of the tool's and its group's rows for the scope's workspace, which returns `GatewayCode.TOOL_TURNED_OFF`. It runs after ownership and before approval, so nothing waits for a person or is metered.
- **The API.** `PUT /v1/tools/{tool_id}/switch` and `PUT /v1/tools/groups/{group}/switch` take `ToolSwitchDraft {enabled, expected_version}` under `OwnerWorkspace`, and return `ToolSwitchView`. A stale version is 409 `stale_version`, matching Keys & vars.
- **The web.** A `ToolSwitch` client component is a `button` with `role="switch"`, `aria-checked` and a visible "On" or "Off" label, named "<title> for this workspace". Each switchable row and group header shows it while `viewer_can_switch`, and otherwise just the words. A change calls the generated client and reloads the catalog. `repairText` covers `turned_off` and `group_turned_off`.

## Risks / Trade-offs

- **One more read per call.** It is a single indexed primary-key lookup.
- **Group precedence can surprise.** A tool turned on under a group that is off stays off, and its words say "off with its group".
- **The persistent install needs `make migrate`** for migration 64, before the Tools page's switches work there.
