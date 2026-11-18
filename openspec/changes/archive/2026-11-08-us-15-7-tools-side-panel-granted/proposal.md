## Why

US-15.7, [PRD-Studio TL-01 to TL-03](../../../../docs/PRD/PRD-Studio.md#tools). Tools opens each tool on its own page, has no text filter or group counts, and labels its grant *sites* as "Granted to". Nothing shows which Experts or workflows actually hold a tool, and the schema can't be copied.

## What Changes

- `GET /v1/tools/{tool_id}/grants`, member-readable. It returns the Experts whose latest version grants the tool, and the workflows whose published version has an agent step using one of those Experts. An older version's grant doesn't count.
- Tools adds a count beside each group heading and a text filter (`q`) kept in the URL. Selecting a row's title opens its detail in a side panel (`tool` in the URL), with "Open as a page". `/tools/{tool_id}` still opens the same detail.
- The detail lists Granted to (Experts and workflows, each linked) and offers Copy schema, which copies exactly the shown version's input schema. The grant sites are relabelled "Can be granted by".

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `tool-catalog`: the side panel, Granted to and Copy schema.

## Impact

- `application/tool_grants.py`, `contracts/tools.py` and `api/tool_routes.py`.
- The generated contract and client.
- `apps/web/components/tool-catalog.tsx`.
- `scripts/qualify_identity.py`, which arranges an older-version grant and a published workflow.
- Specs: `tools.spec.ts` and `experts.spec.ts`.
