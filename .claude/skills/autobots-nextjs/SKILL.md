---
name: autobots-nextjs
description: Implement or review the Option B Next.js interface and BFF in apps/web, including Auth boundaries, generated API clients, accessible stateful flows and sanitized event streaming.
---

# Next.js interface and BFF

Read `.claude/autobots.json`, the mapped contract, selected story and [Next.js standards in DH-06](../../../docs/PRD/PRD-Development-Harness.md#nextjs-and-typescript). For behavior read the mapped Option B product PRD; the alternative Next.js-only runtime is outside scope.

- Prefer Server Components and add client boundaries only for interaction. Use strict TypeScript, `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`; document narrow exceptions.
- Consume generated public API types. Validate untrusted JSON; do not duplicate Python business-state enums or implement a second scheduler in browser state.
- Verify Auth and workspace access on each BFF read/write; guard Host/Origin/CSRF on sensitive writes. Keep server keys, private reasoning and cross-workspace data out of props, caches, errors and bundles. Only the intended Supabase public URL/key may be public under RLS.
- Handle loading, empty, denied, unavailable, retry and reconnect states. Preserve credential-setup drafts; Save & validate performs metadata checks and returns to the composer without starting paid work. UI submit guards complement server idempotency.
- Project sanitized durable application events into SSE; never expose raw LangGraph streams or treat browser disconnect as job cancellation.
- Verify keyboard access, labels and appropriate browser flows. Once tooling exists, lint separately, generate route types before standalone type checking, and run the production build where required. Do not rely on `next build` to lint or use `next lint` for Next.js 16.

Return changed UI/BFF behavior, contract dependencies and actual checks. Current harness availability does not imply web tooling is installed; missing checks remain pending. Use the work item's DH-W record and independent review.
