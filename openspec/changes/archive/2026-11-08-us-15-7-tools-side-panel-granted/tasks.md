# Tasks

## 1. API (Granted to)

- [x] 1.1 Add `tool_grants` (latest Expert versions, and published workflows through agent steps), `ToolGrants` and `GET /v1/tools/{tool_id}/grants`, then regenerate the contract and client

## 2. Web (Group list and side panel; Granted to; Copy schema)

- [x] 2.1 Add group counts, the `q` text filter, the `tool` side panel with "Open as a page", Granted to and Copy schema, and relabel grant sites
- [x] 2.3 Make tool-detail scroll regions focusable (axe in the narrower panel), and make `runs.spec.ts` wait for each filtered response, so a stale row can't satisfy a count under load
- [x] 2.2 Cover the panel, filters and Copy schema in `tools.spec.ts`, and Granted to in `experts.spec.ts` against an arranged older-version grant and published workflow
