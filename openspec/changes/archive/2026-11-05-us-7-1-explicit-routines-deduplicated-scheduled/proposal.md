## Why

Recurring work must not duplicate or silently broaden. PRD 10.4 and SP-016 require frozen versions, unique occurrence keys, no overlap and one catch-up by default, and no job started by a key alone.

## What Changes

- `routines`, immutable `routine_versions`, and `routine_occurrences` keyed by routine and UTC instant.
- `domain/routines.py`: interval and daily triggers in an IANA timezone.
- `application/routines.py`: `evaluate_routines` records missed, skipped and blocked occurrences and admits the latest due one from its version's frozen configuration.
- API routes for routines, versions and enabling. Writes are owner-only.

**Limits:** no process calls `evaluate_routines` yet, which needs US-9.1's worker. No screen, since the story's tasks ask for the logic. Skip is the only overlap policy, the sources' default. Interval and daily are the only triggers, and the sources name no others.

## Capabilities

### New Capabilities

- `routines`: versioned routines and deduplicated occurrences.

### Modified Capabilities

None.

## Impact

A migration, new modules and routes, contracts, tests, `scripts/app_db.py`, `CODEBASE.md`. No dependency or model call.
