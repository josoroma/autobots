## Why

US-10.2's finding B3, and Decision 0009's revision of LC-01, LC-25 and MP-A08: an owner can only set the model policy through the API, and nothing says that role overrides don't take effect in this release.

## What Changes

- `GET /v1/settings/model-policy`, as only the write route exists, and the policy state gains its default and overrides.
- Settings lists the approved models with canonical and wire identity, and edits the workspace default and role overrides, with a stale save refused and a reload message.
- The screen states the effect of role overrides, as Decision 0009 revised them, for the saved policy.
- `RunWorkspace.role_map` exposes what a run froze, so the frozen choice can be observed. Its display is US-11.9's.

## Capabilities

### New Capabilities

- `model-policy-settings`: reading and saving the workspace's model policy, and saying what it does.

### Modified Capabilities

None.

## Impact

`contracts/settings.py`, `contracts/run_workspace.py`, `api/settings_routes.py`, `application/run_projection.py`, generated clients, `apps/web/components/model-policy-panel.tsx`, the Models page and a new browser suite. No schema change, and no model call.
