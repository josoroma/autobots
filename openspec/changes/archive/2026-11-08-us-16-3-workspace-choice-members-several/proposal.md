## Why

US-16.3 implements [Decision 0023 E3](../../../docs/engineering/decisions/0023-install-current-and-real-examples.md#decision). The API already accepts a verified `X-Autobots-Workspace` header, but no client sends one, so a member of several workspaces gets `workspace_required`, "Choose a workspace.", on every member screen, with no way to choose.

## What Changes

- **`POST /api/workspace`** (same origin, CSRF-checked, signed in) stores a workspace the verified session belongs to in an HttpOnly, SameSite=Strict cookie, `autobots.workspace`. Anything else is refused and changes nothing. Signing out deletes it.
- **The BFF** (`forward` and `streamFrom`) and the server-side member reads send it as `X-Autobots-Workspace`. The API still checks membership on every request, so a stale or forged cookie gets `403 forbidden` and no data.
- **The sidebar** shows a workspace chooser above the account menu to a member of several workspaces, or one whose stored choice is stale. Until they choose, it says "Choose a workspace"; there's no implicit default. The page reloads after a choice. The account footer's role and Home's greeting zone follow the current workspace.
- A member of one workspace sees nothing new.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-shell`: workspace choice.

## Impact

- New `apps/web/lib/workspace-choice.ts`, `apps/web/app/api/workspace/route.ts`, `apps/web/components/workspace-chooser.tsx`.
- `lib/bff.ts`, `lib/service-status.ts`, `app/api/session/route.ts`, `components/account-footer.tsx`, `app/page.tsx`.
- New `tests/browser/workspace-choice.spec.ts`, with a two-workspace member arranged in `scripts/qualify_identity.py`.
