## Why

US-14.2, [PRD-Tool-Catalog TS-01 to TS-04 and TC-06](../../../PRD-Tool-Catalog.md#tools-screen), Decision 0017 C9 and C10: the catalog from US-14.1 has no screen, and the Expert editor grants from a hard-coded list of seven tools, one at a time.

## What Changes

- A **Tools** sidebar entry directly before Settings, opening `/tools`: tools by group with ID and version, provider, class, network, cost and availability in words, with group, availability and provider filters kept in the URL.
- `/tools/{tool_id}`: description, every registered version, limits, approval, key requirement by variable name, an inputs table and an outputs table (path, type, required, constraints, whether it's shown on run screens) and the raw JSON Schema in a disclosure. An unavailable tool shows its reason and repair.
- `ExpertConfig.tool_groups`. Saving a version expands each group into the Expert-grantable tools it holds now and records both the explicit list and the groups. A group with no Expert tools is refused `expert_tool_group_empty`, a repeated group `expert_tool_group_duplicated`, and any named tool that is unavailable in this install `expert_tool_unavailable`.
- The Expert editor lists Expert-grantable tools from the catalog, offers whole groups, previews the expansion, and disables unavailable tools with their reason.
- The contract generator parenthesizes a union inside an array, which it had emitted as `"a" | "b"[]`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `tool-catalog`: the Tools screen and grants by group.

## Impact

`apps/web/components/{tool-catalog,expert-editor,sidebar-nav}.tsx`, `apps/web/app/tools/`, `contracts/experts.py`, `application/experts.py`, `application/tool_catalog.py`, `scripts/generate_contracts.py`, the generated contract and client, `scripts/qualify_web.py` (runs the new spec), `apps/web/tests/browser/{tools,experts}.spec.ts` and `tests/test_tool_catalog.py`. No migration: an Expert version's config is already JSON.
