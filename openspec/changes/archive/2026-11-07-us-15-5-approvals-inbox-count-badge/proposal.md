## Why

US-15.5, [PRD-Studio SH-03 and AP-01 to AP-04](../../../../docs/PRD/PRD-Studio.md#approvals) and [Decision 0022 D3](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision). The approvals screen lists only pending requests, as separate cards. It has no history, counts, task link, request size, alternative views, keyboard path or sidebar badge.

## What Changes

- `GET /v1/approvals?status=decided` lists approved, rejected, expired and withdrawn requests. Every list returns `counts` (waiting and decided). Each request gains its run's goal, the plan task its tool use served, who decided it (you, or a member by display name), when, and the stored arguments' byte size.
- `GET /v1/approvals/count` returns the pending count, which feeds the sidebar badge: "N waiting".
- The screen has Waiting and Decided tabs with counts, and a list beside the selected request's detail. J and K move between requests. ⌘↵ approves and ⌘⌫ rejects, each needing a second press within 2 s, announced live, and never while a text field has focus.
- The exact request shows its hash and byte size, with a JSON view (the default, which never changes the text) and a Fields view. The Fields view lists the parsed keys in their stored order and shows markdown as raw text and also rendered from text nodes only. A request too long to show whole still can't be approved.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `approvals`: the inbox, its facts and views, shortcuts and the count.

## Impact

- `application/approvals.py`, `contracts/approvals.py` and `api/approval_routes.py`.
- The generated contract and client.
- `apps/web/components/approvals-panel.tsx`, `sidebar-nav.tsx`, `app-shell.tsx` and `lib/service-status.ts`.
- `tests/db/approval_check.py`, which arranges a markdown request and a task link.
- Specs: `approvals.spec.ts`, `slice-workflows.spec.ts` and `tools.spec.ts`.
