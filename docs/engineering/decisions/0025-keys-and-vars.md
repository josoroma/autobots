# Decision 0025: Settings → Keys & vars

**Date:** 2026-11-08. **Authority:** the owner. Looking at `.env` beside Settings → Tool keys, they said: "these 3 are pending, so name it to keys & vars". The three are `GITHUB_REPOSITORY`, `GITHUB_TOKEN` and `AUTOBOTS_BROWSER_EXECUTOR`, which Tool keys didn't offer. The design choices are made under their standing delegation. This extends [Decision 0024](0024-tool-keys-from-env-and-settings.md) and amends [PRD-Tool-Catalog PK-04 to PK-06](../../../PRD-Tool-Catalog.md#provider-keys) and AB-02. It schedules US-14.18.

## Decision

| # | Choice |
|---|---|
| **V1. Name** | Settings → Tool keys becomes **Settings → Keys & vars**, at `/settings/keys-and-vars`. The `/v1/settings/tool-keys` routes are replaced by `/v1/settings/keys-and-vars`. They were delivered the same day, and nothing outside this repository uses them |
| **V2. Items** | <ul><li>Three secrets, sealed with the master key like the OpenRouter key: the Tavily key, the Jina key and the GitHub token.</li><li>Two values, which aren't secret: the GitHub repository and the browsing switch.</li></ul>Members see each item's source. They see a value's current value, and never a secret's value, prefix, length or hash |
| **V3. Order** | K1's order applies to all five, per workspace: the value saved in Settings, then the process environment, then the configuration root's `.env` files. The first non-blank value wins. Only the owner saves or removes, with an expected version, and removing falls back to the environment |
| **V4. Checks on save** | No check calls a provider (PK-03).<ul><li>The GitHub token gets the shape check the other keys use.</li><li>The repository must be `owner/name`, as the connector already requires.</li><li>The switch must be `enabled` or `disabled`. A saved `disabled` turns browsing off for that workspace even when `.env` enables it.</li></ul>Browsing still needs a passing executor qualification at the current code (AB-02) |
| **V5. `make start`** | It also passes `GITHUB_REPOSITORY` and `GITHUB_TOKEN` from the repository's `.env`, by K2's rules: parsed as data, never sourced, and blank passes nothing. The browsing switch keeps K7's rule |
| **V6. Per attempt, per workspace** | <ul><li>GitHub tools resolve their repository and token inside each attempt from the run's workspace.</li><li>The worker binds `browse_goal` for a job only when that workspace's switch resolves to `enabled`.</li><li>The Tools page, run admission, routine admission and Expert save follow the same resolution.</li></ul> |
| **V7. Approval binds the repository** | A GitHub write's approval records the repository resolved when the approval was requested. When the approved call runs, a different resolved repository refuses it with `approval_target_changed` before any request, and nothing is written. A changed setting can never redirect an approved effect |
| **V8. Approvals already pending** | The approval request already records its repository as its `resource_target`, so approvals requested before this change are bound the same way. An approved call runs only when the repository it resolves equals the recorded one. A recorded target that is empty or doesn't match is refused `approval_target_changed`, failing closed. A write that may already have been sent is left to its receipt, and its handler and readback use the recorded repository. No approval is requested for a destination that isn't configured: that call is refused `connector_not_configured` |
| **V9. Codes** | A workspace whose switch is off sees `browse_goal` as `disabled_by_policy`. An Expert save naming it is refused `expert_tool_unavailable`, and admission `tool_unavailable`. The former `/v1/settings/tool-keys` routes and `/settings/tool-keys` page answer 404 |

## Owner steps after delivery

Migration 52 changes the persistent database. Run `make migrate`, then `make stop && make start`.

## What this doesn't establish

No GitHub, Tavily or Jina request is made, and browsing isn't run on the install. Tests use fake transports and disposable databases.
