## Why

US-10.2's finding B6: Settings says "not qualified" for routes US-3.4 tested, and the goal composer still says no worker runs a goal. Decision 0009 chose to correct the message and store each route's qualification with its date and limits.

## What Changes

- A durable per-route qualification record, holding the route's identity, status, date, configuration and limits, read by the API and never inferred from a key or the catalog.
- The provider status contract replaces its one fixed `not_qualified` value with one entry per approved route, and the clients are regenerated.
- A migration records each route's current result from the US-3.4 evidence. A record for a different canonical model doesn't count.
- Settings shows each route's record apart from authentication and catalog status.
- The goal composer says the goal is queued and links the run.

## Capabilities

### New Capabilities

- `route-qualification-status`: what Settings and the API say about each route's qualification, and the goal composer's admission message.

### Modified Capabilities

None.

## Impact

`supabase/migrations`, `contracts/settings.py`, `application/provider_settings.py`, generated clients, `provider-settings-panel.tsx`, `goal-composer.tsx`, browser tests and `scripts/qualify_identity.py`. No model call, and no change to what a route may request.
