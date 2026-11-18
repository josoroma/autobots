---
paths:
  - "apps/web/**/*"
---

# Web boundaries

Use [DH-06 Next.js standards](../../docs/PRD/PRD-Development-Harness.md#nextjs-and-typescript) and `autobots-nextjs`. Next.js owns UI/BFF, not Python business-state transitions or durable scheduling.

- Strict TypeScript; generated API types plus runtime parsing at untrusted boundaries. Server Components by default; explicit interactive client boundaries.
- Use [DS-01–05](../../docs/PRD/PRD-Design-System.md) and the exact [Luma tokens](../../docs/design/luma.css): dark on first use regardless of OS preference; persist explicit light/dark choice. Use semantic shadcn variables throughout, including portals/sidebar/charts/workflow surfaces; verify first paint, keyboard focus and both themes when app tooling exists.
- Verify session/workspace per BFF operation. Protect mutations with Host/Origin/CSRF checks. Server keys/private reasoning never reach props, caches, bundles or public events.
- Only approved public Supabase URL/key is client-visible under RLS. OpenRouter credentials stay server-side.
- Render sanitized durable events; handle reconnect/deduplication and explicit error/empty/loading states. Browser disconnect does not cancel a run.
- Lint separately from Next.js 16 builds; generate route types before standalone type checks. Never suppress build type errors. Verify relevant accessible user flows once tooling exists.

## Check and review

Check: the `db` profile for screens, as most browser suites run there, and the `fast` and `full` profiles of [`scripts/verify.py`](../../scripts/verify.py). Review: [`autobots-review-change`](../skills/autobots-review-change/SKILL.md).
