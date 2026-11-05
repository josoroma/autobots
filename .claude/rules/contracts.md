---
paths:
  - "contracts/**/*"
  - "packages/api-client/**/*"
  - "packages/db-types/**/*"
  - "services/agent/src/autobots/contracts/**/*"
  - "services/agent/src/autobots/domain/**/*"
---

# Contract and state compatibility

Read `autobots-contracts` and the mapped [Option B contract](../../docs/engineering/option-b-contract.md).

- Pydantic/OpenAPI owns public API definitions; generated TypeScript consumes them. SQL owns database schema. Keep domain, row, graph, DTO and UI types distinct.
- Canonical states/guards are shared; terminal runs cannot resume. Version event envelopes, workflow IR, graph state and immutable model-policy snapshots.
- Generate offline into temporary output and compare normalized artifacts. No key/service/network requirement for schema generation; missing generators fail prerequisites.
- Define compatibility and upgrade behavior. Shared validation fixtures cover both languages, unknown enums and private-field leakage; TypeScript types do not validate JSON.
- Coordinate generator ownership. A contract edit invalidates affected consumer checks and review, not just the source file's lint result.

## Check and review

Check: the `fast` profile of [`scripts/verify.py`](../../scripts/verify.py). Review: [`autobots-review-change`](../skills/autobots-review-change/SKILL.md).
