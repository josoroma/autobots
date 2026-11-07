## Why

US-14.1, [PRD-Tool-Catalog TC-01 to TC-05](../../../PRD-Tool-Catalog.md#catalog-contract) and [Decision 0017](../../../docs/engineering/decisions/0017-tool-catalog.md): tools can only be discovered by reading code today. The registry's scope-filtered catalog is for the model only.

## What Changes

- `ToolDefinition` gains descriptive fields: title, group, provider, network, cost class and note, key requirement by variable name, and public input and output fields. Every existing tool sets its title, group and public fields. `create_github_issue` names its provider and its `GITHUB_REPOSITORY` and `GITHUB_TOKEN` requirement.
- A catalog derived from the registry the worker builds, never a second list: descriptors with schemas, flattened fields, limits, where a grant may name the tool, and availability computed per request. `browse_goal` is catalogued as `disabled_by_policy` and never registered.
- `GET /v1/tools`, `GET /v1/tools/{tool_id}` and `GET /v1/tools/{tool_id}/versions/{version}`, member-readable, reached through the BFF's existing `/api/v1/*` forwarding. The catalog carries a digest that excludes availability.
- Regenerated OpenAPI and TypeScript client.

## Capabilities

### New Capabilities

- `tool-catalog`: the read-only tool catalog.

### Modified Capabilities

None. The agent view, `ToolRegistry.catalog(scope)`, is unchanged.

## Impact

`domain/tool_catalog.py`, `application/tool_catalog.py`, `application/tool_gateway.py`, `api/tool_routes.py`, `api/app.py`, `contracts/tools.py`, the tool definition modules, `application/workflows.py` (its workflow tool set made public), the generated contract and client, and `tests/test_tool_catalog.py`. No migration and no screen.
