## Why

US-15.10, [PRD-Studio HM-01 and HM-04](../../../PRD-Studio.md#home) and [Decision 0022 D9 and D14](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision). Home opens with a fixed "Local workbench" title. It doesn't greet the member, show what waits for them, or list recent runs.

## What Changes

- `SessionWorkspace` adds the workspace's IANA `timezone`, from `public.workspaces.timezone`.
- Home greets the member above the heading "What should we work on?", with "Good morning", "Good afternoon" or "Good evening" and the display name.
  - The greeting follows D14's boundaries in the first workspace's timezone.
  - It's read in the browser, so the server's clock never decides it.
- Under the composer, Needs you lists pending approvals, each linking to Review (`/approvals?approval=<id>`), and runs in `waiting_input`, each linking to Reply on the run (`/runs/<id>`). A paused run isn't listed, as it counts as Active (D9).
- Under the composer, Recent runs lists the five newest runs. Each shows its state, plan progress or spend ("≈" when estimated), and a relative time.
- The approvals screen opens with the request named in `approval` selected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-shell`: Home's greeting, Needs you and recent runs.

## Impact

- `contracts/service.py`, `application/profiles.py`, `api/routes.py` and the generated contract and client.
- `app/page.tsx` and new `home-greeting.tsx` and `home-activity.tsx`. `run-list.tsx` exports its state words.
- `approvals-panel.tsx` and `app/approvals/page.tsx`.
- `scripts/qualify_identity.py` and `home.spec.ts`.
