# Tasks

## 1. Catalog (The catalog matches the registry)

- [x] 1.1 Add descriptive fields to tool definitions and set them on every registered tool
- [x] 1.2 Derive descriptors from the worker's registry, with flattened fields, limits, grant sites and the planned `browse_goal` as `disabled_by_policy`
- [x] 1.3 Add the three catalog routes with digest and filters, and regenerate OpenAPI and the TypeScript client

## 2. Boundaries (Discovery doesn't grant; No secret in the catalog)

- [x] 2.1 Compute availability per request from variable presence only
- [x] 2.2 Test parity, agent-view filtering, denial before effect, secret absence and the routes
