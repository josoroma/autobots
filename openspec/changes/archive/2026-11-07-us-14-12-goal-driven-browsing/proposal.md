## Why

US-14.12, PRD-Tool-Catalog "Autonomous browsing" (AB-01 to AB-03), and Decisions 0018 (B5, B6) and 0020 (L2, L5, L6). Now that the isolated executor (US-14.13) and the admitted browsing loop (US-14.14) exist, `browse_goal` can leave `disabled_by_policy`. It is read-only, granted only through an Expert, and approved by a person on every call.

## What Changes

- `browse_goal` v1 is `arbitrary_execution`, provider `autobots`, `metered_provider`, `approval: always`, Expert-only.
  - Input: `task`, `start_url`, `allowed_domains`, `max_steps`, `max_seconds`.
  - Output: `summary` (labelled third-party and cut to the shared text budget), `visited`, `visited_count`, `steps`, `model_calls` and `stopped`.
  - Public fields: `start_url`, `allowed_domains`, `max_steps`, `stopped`, `steps` and `visited_count`.
- The registry admits `arbitrary_execution` only for a tool whose executor reports qualified, and the gateway checks this again at dispatch. A run without an Expert behind it is refused `expert_grant_required`.
- Each call:
  - starts one isolated executor session whose egress allowlist is the call's domains;
  - attaches the request guard and opens a CDP page;
  - runs US-14.14's loop on the run's frozen `researcher` route through the current loop middleware;
  - removes the session at the end, or when the attempt ends.
- A navigation outside `allowed_domains`, or one the browser refuses, ends the call `refused_action`. An invalid answer ends it `invalid_action`. The limits end it `max_steps` or `max_seconds`.
- While the executor isn't qualified, the catalog keeps `browse_goal` `disabled_by_policy` with its repair, and an Expert naming it is refused.
- `browser_use` is removed as a provider value from the catalog, the contract, the generated client and the Tools screen.
- A live check on a disposable stack, `scripts/qualify_browse_goal.py`, uses the real executor, example.com and a scripted model. It runs in no verification profile.

## Capabilities

### New Capabilities

- `goal-driven-browsing`: the `browse_goal` tool.

### Modified Capabilities

None.

## Impact

Affected code:
- `domain/tools.py`, `domain/tool_catalog.py`, `contracts/tools.py`, and a new `contracts/browsing.py`
- `application/tool_gateway.py`, `application/tool_catalog.py`, `application/worker_inference.py`, and a new `application/browsing_tool.py`
- `adapters/loop_middleware.py`, `adapters/browser_page.py`, `application/browsing_loop.py`
- `operations/worker.py`
- the generated contract and client, and `apps/web/components/tool-catalog.tsx`
- tests

No migration and no package.
